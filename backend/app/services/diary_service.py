"""Farming diary, with automatic stock restore and expense generation.

Implements Issues #21 (CRUD), #25 (hoàn kho) and #29 (auto expense) together,
because they are one behaviour rather than three: a diary entry that consumes
supplies owns a set of ledger rows, and every edit to the entry has to leave
that set — and the inventory and cost totals derived from it — exactly right.

The invariants this module must uphold (Data_Requirements_Database.md §9):

  I3  create -> edit -> delete returns on_hand for every touched supply to
      EXACTLY its pre-create value. Decimal equality, not approximate.
  I4  the restore is idempotent; applying it twice equals applying it once.
  I6  exactly one expense per supply-consuming movement.
  I7  a bare stock-out (no diary entry) generates no expense.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Select, func, select, update
from sqlalchemy.orm import Session

from app.core.numeric import line_total, quantize_money, quantize_quantity
from app.core.timeutils import now_ms
from app.models import DiaryEntry, Expense, Season, StockTransaction, Supply
from app.models.enums import TxnType, WorkType
from app.schemas.diary import DiaryEntryCreate, DiaryEntryUpdate, SupplyUsageIn
from app.services import finance_service
from app.services.errors import Conflict, NotFound, ValidationFailed

UTC = timezone.utc


def _scoped(household_id: uuid.UUID) -> Select:
    return select(DiaryEntry).where(
        DiaryEntry.household_id == household_id, DiaryEntry.deleted_at.is_(None)
    )


def _live_usages(db: Session, entry_id: str) -> list[StockTransaction]:
    return list(
        db.execute(
            select(StockTransaction)
            .where(
                StockTransaction.diary_entry_id == entry_id,
                StockTransaction.deleted_at.is_(None),
            )
            .order_by(StockTransaction.id)
        )
        .scalars()
        .all()
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Read
# ═══════════════════════════════════════════════════════════════════════════


def get_entry(db: Session, household_id: uuid.UUID, entry_id: str) -> DiaryEntry:
    entry = db.execute(_scoped(household_id).where(DiaryEntry.id == entry_id)).scalar_one_or_none()
    if entry is None:
        raise NotFound("Không tìm thấy nhật ký canh tác.")
    return entry


def list_entries(
    db: Session,
    household_id: uuid.UUID,
    *,
    season_id: str | None = None,
    work_type: WorkType | None = None,
    date_from: int | None = None,
    date_to: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[DiaryEntry], int]:
    stmt = _scoped(household_id)
    if season_id:
        stmt = stmt.where(DiaryEntry.season_id == season_id)
    if work_type is not None:
        stmt = stmt.where(DiaryEntry.work_type == work_type.value)
    if date_from is not None:
        stmt = stmt.where(DiaryEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(DiaryEntry.entry_date <= date_to)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(DiaryEntry.entry_date.desc(), DiaryEntry.id).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )
    return list(rows), total


def usages_for(
    db: Session, entry_ids: list[str]
) -> dict[str, list[tuple[StockTransaction, Supply]]]:
    """Consumptions for many entries in ONE query.

    Per-entry lookups would turn a 50-row diary list into 51 round-trips,
    which on a rural connection is the difference between a usable screen and
    an unusable one.
    """
    if not entry_ids:
        return {}

    rows = db.execute(
        select(StockTransaction, Supply)
        .join(Supply, Supply.id == StockTransaction.supply_id)
        .where(
            StockTransaction.diary_entry_id.in_(entry_ids),
            StockTransaction.deleted_at.is_(None),
        )
        .order_by(StockTransaction.id)
    ).all()

    grouped: dict[str, list[tuple[StockTransaction, Supply]]] = {eid: [] for eid in entry_ids}
    for txn, supply in rows:
        grouped[txn.diary_entry_id].append((txn, supply))
    return grouped


# ═══════════════════════════════════════════════════════════════════════════
#  Consumption reconciliation — the heart of #25 and #29
# ═══════════════════════════════════════════════════════════════════════════


def _load_supplies(
    db: Session, household_id: uuid.UUID, supply_ids: list[str]
) -> dict[str, Supply]:
    if not supply_ids:
        return {}
    found = (
        db.execute(
            select(Supply).where(
                Supply.id.in_(supply_ids),
                Supply.household_id == household_id,
                Supply.deleted_at.is_(None),
            )
        )
        .scalars()
        .all()
    )
    by_id = {s.id: s for s in found}
    missing = set(supply_ids) - set(by_id)
    if missing:
        raise NotFound(f"Không tìm thấy vật tư: {', '.join(sorted(missing))}")
    return by_id


def _apply_usages(
    db: Session,
    household_id: uuid.UUID,
    entry: DiaryEntry,
    usages: list[SupplyUsageIn],
    *,
    device_id: str | None,
) -> None:
    """Reconcile the entry's ledger rows against the submitted list.

    Matched by `supply_id`, which is why duplicate supplies in one entry are
    rejected at the schema edge — otherwise "which line changed?" has no
    answer.

    Four cases, and the third one matters more than it looks:

      added    -> new stock-out + its auto expense
      changed  -> update quantity and total_cost in place, expense follows
      SAME     -> write NOTHING
      removed  -> tombstone the movement and its expense; stock returns

    The no-op case is not an optimisation. Touching a row bumps `updated_at`,
    and `updated_at` is what drives last-write-wins. Rewriting an unchanged
    row would manufacture a conflict against another device that legitimately
    edited it, and that device's edit would lose.
    """
    supplies = _load_usage_supplies(db, household_id, usages)
    existing = {t.supply_id: t for t in _live_usages(db, entry.id)}
    submitted = {u.supply_id: u for u in usages}
    ts = now_ms()

    # ── removed ────────────────────────────────────────────────────────────
    for supply_id, txn in existing.items():
        if supply_id in submitted:
            continue
        txn.deleted_at = datetime.now(UTC)
        txn.updated_at = ts
        txn.last_device_id = device_id
        finance_service.void_auto_expense(db, txn.id, device_id=device_id)

    # ── added / changed / unchanged ────────────────────────────────────────
    for supply_id, usage in submitted.items():
        supply = supplies[supply_id]
        quantity = quantize_quantity(usage.quantity)
        unit_cost = quantize_money(
            usage.unit_cost if usage.unit_cost is not None else supply.unit_cost
        )
        total = line_total(quantity, unit_cost)

        txn = existing.get(supply_id)
        if txn is None:
            txn = StockTransaction(
                id=usage.id or str(uuid.uuid4()),
                household_id=household_id,
                supply_id=supply_id,
                season_id=entry.season_id,
                diary_entry_id=entry.id,
                txn_type=TxnType.OUT.value,
                quantity=quantity,
                unit_cost=unit_cost,
                total_cost=total,
                txn_date=entry.entry_date,
                note=usage.note,
                created_at=ts,
                updated_at=ts,
                last_device_id=device_id,
            )
            db.add(txn)
            db.flush()
        elif (
            txn.quantity != quantity
            or txn.unit_cost != unit_cost
            or txn.txn_date != entry.entry_date
            or txn.season_id != entry.season_id
            or txn.note != usage.note
        ):
            txn.quantity = quantity
            txn.unit_cost = unit_cost
            txn.total_cost = total
            txn.txn_date = entry.entry_date
            txn.season_id = entry.season_id
            txn.note = usage.note
            txn.updated_at = ts
            txn.last_device_id = device_id
            db.flush()
        # else: identical -> deliberately no write

        finance_service.sync_auto_expense(
            db, txn, season_id=entry.season_id, device_id=device_id
        )

    db.flush()


def _load_usage_supplies(
    db: Session, household_id: uuid.UUID, usages: list[SupplyUsageIn]
) -> dict[str, Supply]:
    return _load_supplies(db, household_id, [u.supply_id for u in usages])


# ═══════════════════════════════════════════════════════════════════════════
#  Write
# ═══════════════════════════════════════════════════════════════════════════


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


def create_entry(
    db: Session,
    household_id: uuid.UUID,
    season_id: str,
    payload: DiaryEntryCreate,
    *,
    device_id: str | None = None,
) -> DiaryEntry:
    _require_season(db, household_id, season_id)

    entry_id = payload.id or str(uuid.uuid4())
    if db.execute(
        select(DiaryEntry.id).where(DiaryEntry.id == entry_id)
    ).scalar_one_or_none():
        raise Conflict(f"Nhật ký với id {entry_id} đã tồn tại.")

    ts = now_ms()
    entry = DiaryEntry(
        id=entry_id,
        household_id=household_id,
        season_id=season_id,
        work_type=payload.work_type.value,
        entry_date=payload.entry_date or ts,
        title=payload.title,
        note=payload.note,
        weather=payload.weather,
        labor_hours=payload.labor_hours,
        created_at=payload.created_at or ts,
        updated_at=payload.updated_at or ts,
        last_device_id=device_id,
    )
    db.add(entry)
    db.flush()

    if payload.supply_usages:
        _apply_usages(db, household_id, entry, payload.supply_usages, device_id=device_id)

    return entry


def update_entry(
    db: Session,
    household_id: uuid.UUID,
    entry_id: str,
    payload: DiaryEntryUpdate,
    *,
    device_id: str | None = None,
) -> DiaryEntry:
    entry = get_entry(db, household_id, entry_id)
    changes = payload.model_dump(exclude_unset=True, exclude={"updated_at", "supply_usages"})

    if changes.get("season_id") is not None:
        _require_season(db, household_id, changes["season_id"])
    if changes.get("work_type") is not None:
        changes["work_type"] = changes["work_type"].value

    for field, value in changes.items():
        setattr(entry, field, value)

    entry.updated_at = payload.updated_at or now_ms()
    entry.last_device_id = device_id
    db.flush()

    if payload.supply_usages is not None:
        # `[]` means "reverse everything"; omitted means "leave it alone".
        _apply_usages(db, household_id, entry, payload.supply_usages, device_id=device_id)
    elif "entry_date" in changes or "season_id" in changes:
        # The entry moved, so its child movements must move with it — a
        # consumption dated differently from the work that caused it would
        # land in the wrong report bucket and the wrong season's cost total.
        _apply_usages(
            db,
            household_id,
            entry,
            [
                SupplyUsageIn(
                    id=t.id,
                    supply_id=t.supply_id,
                    quantity=t.quantity,
                    unit_cost=t.unit_cost,
                    note=t.note,
                )
                for t in _live_usages(db, entry.id)
            ],
            device_id=device_id,
        )

    return entry


def soft_delete_entry(
    db: Session,
    household_id: uuid.UUID,
    entry_id: str,
    *,
    device_id: str | None = None,
) -> dict:
    """Tombstone the entry and reverse every consumption it caused.

    This is "hoàn kho" in its simplest form: the work did not happen, so the
    fertiliser was not used, so it goes back on the shelf.
    """
    entry = get_entry(db, household_id, entry_id)
    usages = _live_usages(db, entry_id)

    now = datetime.now(UTC)
    ts = now_ms()
    restored: dict[str, Decimal] = {}
    expenses_removed = 0

    for txn in usages:
        restored[txn.supply_id] = quantize_quantity(
            restored.get(txn.supply_id, Decimal("0")) + txn.quantity
        )
        txn.deleted_at = now
        txn.updated_at = ts
        txn.last_device_id = device_id
        if finance_service.void_auto_expense(db, txn.id, device_id=device_id):
            expenses_removed += 1

    entry.deleted_at = now
    entry.updated_at = ts
    entry.last_device_id = device_id
    db.flush()

    return {
        "stock_transactions_reversed": len(usages),
        "expenses_removed": expenses_removed,
        "quantity_restored": restored,
    }


def restore_entry(
    db: Session, household_id: uuid.UUID, entry_id: str, *, device_id: str | None = None
) -> DiaryEntry:
    """Undo a soft delete, re-consuming the supplies.

    Exists because "xoá nhầm" is the single most common mistake in a field app
    operated with muddy hands, and because it exercises the revive path in
    `sync_auto_expense` that a sync retry also takes.
    """
    entry = db.execute(
        select(DiaryEntry).where(
            DiaryEntry.id == entry_id,
            DiaryEntry.household_id == household_id,
            DiaryEntry.deleted_at.is_not(None),
        )
    ).scalar_one_or_none()
    if entry is None:
        raise NotFound("Không tìm thấy nhật ký đã xoá.")

    ts = now_ms()
    entry.deleted_at = None
    entry.updated_at = ts
    entry.last_device_id = device_id

    db.execute(
        update(StockTransaction)
        .where(
            StockTransaction.diary_entry_id == entry_id,
            StockTransaction.deleted_at.is_not(None),
        )
        .values(deleted_at=None, updated_at=ts, last_device_id=device_id)
    )
    db.flush()

    for txn in _live_usages(db, entry_id):
        finance_service.sync_auto_expense(
            db, txn, season_id=entry.season_id, device_id=device_id
        )

    return entry


def entry_supply_cost(db: Session, entry_id: str) -> Decimal:
    total = db.execute(
        select(func.coalesce(func.sum(StockTransaction.total_cost), 0)).where(
            StockTransaction.diary_entry_id == entry_id,
            StockTransaction.deleted_at.is_(None),
        )
    ).scalar_one()
    return quantize_money(total)


def auto_expense_count(db: Session, entry_id: str) -> int:
    """Live `diary_auto` expenses attributable to an entry. Used by tests."""
    return db.execute(
        select(func.count())
        .select_from(Expense)
        .join(StockTransaction, StockTransaction.id == Expense.stock_transaction_id)
        .where(
            StockTransaction.diary_entry_id == entry_id,
            Expense.deleted_at.is_(None),
        )
    ).scalar_one()


def validate_usage_supplies(
    db: Session, household_id: uuid.UUID, usages: list[SupplyUsageIn]
) -> None:
    """Fail fast with a readable message before any write happens."""
    if not usages:
        return
    _load_usage_supplies(db, household_id, usages)
    for usage in usages:
        if quantize_quantity(usage.quantity) <= 0:
            raise ValidationFailed("Số lượng vật tư phải lớn hơn 0.")
