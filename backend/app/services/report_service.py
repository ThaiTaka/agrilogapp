"""Report aggregation (Issue #42).

Aggregation happens in SQL; bucketing and gap-filling happen in Python.

That split is deliberate. SQL groups by the STORED `*_day_local` columns —
already indexed, already carrying the fixed UTC+7 offset — which keeps the
"what calendar day is this?" rule in exactly one place. Rolling days up into
weeks and months, and inventing the empty buckets in between, is calendar
arithmetic that SQL expresses badly and Python expresses clearly. A season is
at most a few hundred days, so the row count reaching Python is trivial.

The same rule must hold on the mobile client, which computes these charts
from local WatermelonDB data while offline (Issue #47). `mobile/src/utils/`
mirrors `local_day_index`, and a shared golden fixture asserts both sides
produce identical numbers (§11.4).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.numeric import ZERO_MONEY, quantize_money, quantize_quantity
from app.core.timeutils import local_day_index, now_ms
from app.models import Expense, Revenue, Season, StockTransaction, Supply
from app.models.enums import SUPPLY_CATEGORY_LABELS_VI, TxnType
from app.schemas.report import Granularity, GroupBy
from app.services.errors import NotFound

UTC = timezone.utc

# A guard, not a business rule: a season with a corrupt start_date could
# otherwise ask Python to materialise millions of empty buckets.
MAX_DENSE_DAYS = 2000


def _require_season(db: Session, household_id: uuid.UUID, season_id: str) -> Season:
    season = db.execute(
        select(Season).where(
            Season.id == season_id,
            Season.household_id == household_id,
            Season.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if season is None:
        raise NotFound("Không tìm thấy mùa vụ.")
    return season


def _day_to_date(day_index: int) -> datetime:
    """Inverse of `local_day_index` — the local calendar date it names."""
    return datetime.fromtimestamp(day_index * 86_400, tz=UTC)


def _bucket_key(day_index: int, granularity: Granularity) -> str:
    d = _day_to_date(day_index)
    if granularity is Granularity.DAY:
        return d.strftime("%Y-%m-%d")
    if granularity is Granularity.WEEK:
        iso = d.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return d.strftime("%Y-%m")


def _dense_keys(first_day: int, last_day: int, granularity: Granularity) -> list[str]:
    """Every bucket in the range, in order, including the empty ones.

    Walks day by day and collects distinct keys rather than trying to step in
    weeks or months. Month lengths and ISO week boundaries are exactly the
    arithmetic that goes wrong when done cleverly, and a few hundred
    iterations costs nothing.
    """
    if last_day < first_day:
        return []
    span = min(last_day - first_day, MAX_DENSE_DAYS)

    keys: list[str] = []
    seen: set[str] = set()
    cursor = _day_to_date(first_day)
    for _ in range(span + 1):
        key = _bucket_key(local_day_index(int(cursor.timestamp() * 1000)), granularity)
        if key not in seen:
            seen.add(key)
            keys.append(key)
        cursor += timedelta(days=1)
    return keys


# ═══════════════════════════════════════════════════════════════════════════
#  1. Income vs Expense over time
# ═══════════════════════════════════════════════════════════════════════════


def income_expense(
    db: Session,
    household_id: uuid.UUID,
    season_id: str,
    *,
    granularity: Granularity = Granularity.MONTH,
) -> dict:
    season = _require_season(db, household_id, season_id)

    expense_rows = db.execute(
        select(Expense.expense_day_local, func.sum(Expense.amount))
        .where(
            Expense.household_id == household_id,
            Expense.season_id == season_id,
            Expense.deleted_at.is_(None),
        )
        .group_by(Expense.expense_day_local)
    ).all()

    revenue_rows = db.execute(
        select(Revenue.revenue_day_local, func.sum(Revenue.amount))
        .where(
            Revenue.household_id == household_id,
            Revenue.season_id == season_id,
            Revenue.deleted_at.is_(None),
        )
        .group_by(Revenue.revenue_day_local)
    ).all()

    expense_by_bucket: dict[str, Decimal] = {}
    revenue_by_bucket: dict[str, Decimal] = {}
    for day, amount in expense_rows:
        key = _bucket_key(day, granularity)
        expense_by_bucket[key] = expense_by_bucket.get(key, ZERO_MONEY) + quantize_money(amount)
    for day, amount in revenue_rows:
        key = _bucket_key(day, granularity)
        revenue_by_bucket[key] = revenue_by_bucket.get(key, ZERO_MONEY) + quantize_money(amount)

    # The range is the SEASON's window, not the range of recorded activity.
    # A season that starts in December and has its first cost in February
    # should show two empty months first — that gap is information.
    first_day = local_day_index(season.start_date)
    end_ms = season.end_date if season.end_date is not None else now_ms()
    last_day = max(local_day_index(end_ms), first_day)

    # Activity outside the declared window still has to appear, or the chart
    # totals would not match the season summary.
    observed = [d for d, _ in expense_rows] + [d for d, _ in revenue_rows]
    if observed:
        first_day = min(first_day, min(observed))
        last_day = max(last_day, max(observed))

    buckets = []
    for key in _dense_keys(first_day, last_day, granularity):
        expense = expense_by_bucket.get(key, ZERO_MONEY)
        revenue = revenue_by_bucket.get(key, ZERO_MONEY)
        buckets.append(
            {
                "period": key,
                "revenue": revenue,
                "expense": expense,
                "profit": quantize_money(revenue - expense),
            }
        )

    total_expense = quantize_money(sum(expense_by_bucket.values(), ZERO_MONEY))
    total_revenue = quantize_money(sum(revenue_by_bucket.values(), ZERO_MONEY))

    return {
        "season_id": season.id,
        "season_name": season.name,
        "granularity": granularity,
        "buckets": buckets,
        "totals": {
            "revenue": total_revenue,
            "expense": total_expense,
            "profit": quantize_money(total_revenue - total_expense),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
#  2. Supply consumption
# ═══════════════════════════════════════════════════════════════════════════


def supply_consumption(
    db: Session,
    household_id: uuid.UUID,
    *,
    season_id: str | None = None,
    group_by: GroupBy = GroupBy.CATEGORY,
) -> dict:
    """What the household actually used, and what it cost.

    Only `out` movements count. A stock-in is a purchase, not consumption;
    including it would double the apparent usage of everything.
    """
    season = _require_season(db, household_id, season_id) if season_id else None

    grouping = Supply.category if group_by is GroupBy.CATEGORY else Supply.id

    stmt = (
        select(
            grouping,
            func.sum(StockTransaction.quantity),
            func.sum(StockTransaction.total_cost),
            func.count(),
            func.count(func.distinct(Supply.unit)),
            func.min(Supply.unit),
            func.min(Supply.name),
        )
        .join(Supply, Supply.id == StockTransaction.supply_id)
        .where(
            StockTransaction.household_id == household_id,
            StockTransaction.txn_type == TxnType.OUT.value,
            StockTransaction.deleted_at.is_(None),
        )
        .group_by(grouping)
        .order_by(func.sum(StockTransaction.total_cost).desc())
    )
    if season_id:
        stmt = stmt.where(StockTransaction.season_id == season_id)

    rows = db.execute(stmt).all()
    total_cost = quantize_money(sum((r[2] or 0) for r in rows))

    items = []
    for key, quantity, cost, count, distinct_units, a_unit, supply_name in rows:
        cost = quantize_money(cost or 0)
        mixed = (distinct_units or 0) > 1
        items.append(
            {
                "key": str(key),
                "label": (
                    SUPPLY_CATEGORY_LABELS_VI.get(key, str(key))
                    if group_by is GroupBy.CATEGORY
                    else supply_name
                ),
                "quantity": quantize_quantity(quantity or 0),
                # Suppressed when the group mixes units: reporting "340.5" for
                # a category holding both kg and litres is a number with no
                # meaning, and the chart must fall back to cost.
                "unit": None if mixed else a_unit,
                "unit_mixed": mixed,
                "total_cost": cost,
                "share_pct": (
                    (cost / total_cost * 100).quantize(Decimal("0.1"))
                    if total_cost > 0
                    else Decimal("0.0")
                ),
                "transaction_count": count,
            }
        )

    return {
        "season_id": season.id if season else None,
        "season_name": season.name if season else None,
        "group_by": group_by,
        "items": items,
        "total_cost": total_cost,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  3. Season comparison
# ═══════════════════════════════════════════════════════════════════════════


def season_comparison(
    db: Session,
    household_id: uuid.UUID,
    *,
    limit: int = 10,
    status: str | None = None,
) -> dict:
    """Profit per season, newest first.

    LEFT JOINs so a season with no records yet still appears, at zero. A
    farmer comparing seasons needs to see the one they just started sitting at
    zero, not silently missing from the chart.
    """
    expense_totals = (
        select(Expense.season_id.label("sid"), func.sum(Expense.amount).label("total"))
        .where(Expense.household_id == household_id, Expense.deleted_at.is_(None))
        .group_by(Expense.season_id)
        .subquery()
    )
    revenue_totals = (
        select(Revenue.season_id.label("sid"), func.sum(Revenue.amount).label("total"))
        .where(Revenue.household_id == household_id, Revenue.deleted_at.is_(None))
        .group_by(Revenue.season_id)
        .subquery()
    )

    stmt = (
        select(
            Season,
            func.coalesce(expense_totals.c.total, 0),
            func.coalesce(revenue_totals.c.total, 0),
        )
        .outerjoin(expense_totals, expense_totals.c.sid == Season.id)
        .outerjoin(revenue_totals, revenue_totals.c.sid == Season.id)
        .where(Season.household_id == household_id, Season.deleted_at.is_(None))
        .order_by(Season.start_date.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(Season.status == status)

    seasons = []
    for season, expense, revenue in db.execute(stmt).all():
        expense = quantize_money(expense)
        revenue = quantize_money(revenue)
        profit = quantize_money(revenue - expense)
        seasons.append(
            {
                "season_id": season.id,
                "name": season.name,
                "crop_type": season.crop_type,
                "status": season.status,
                "start_date": season.start_date,
                "end_date": season.end_date,
                "revenue": revenue,
                "expense": expense,
                "profit": profit,
                "margin_pct": (
                    (profit / revenue * 100).quantize(Decimal("0.1"))
                    if revenue > 0
                    else None
                ),
            }
        )

    best = max(seasons, key=lambda s: s["profit"], default=None)
    worst = min(seasons, key=lambda s: s["profit"], default=None)

    return {
        "seasons": seasons,
        "best_season_id": best["season_id"] if best else None,
        "worst_season_id": worst["season_id"] if worst else None,
    }
