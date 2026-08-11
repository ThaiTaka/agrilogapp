"""Crop season business logic (Issue #19).

Every function takes `household_id` explicitly rather than reading it from a
request context. The tenant is then impossible to forget: a query that should
be scoped but is not fails to compile rather than quietly returning another
household's rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Select, func, select, update
from sqlalchemy.orm import Session

from app.core.timeutils import now_ms
from app.models import DiaryEntry, Expense, Revenue, Season, StockTransaction
from app.models.enums import SeasonStatus
from app.schemas.season import SeasonCreate, SeasonUpdate
from app.services.errors import Conflict, NotFound

UTC = timezone.utc


def _scoped(household_id: uuid.UUID, *, include_deleted: bool = False) -> Select:
    stmt = select(Season).where(Season.household_id == household_id)
    if not include_deleted:
        stmt = stmt.where(Season.deleted_at.is_(None))
    return stmt


# ═══════════════════════════════════════════════════════════════════════════
#  Read
# ═══════════════════════════════════════════════════════════════════════════


def list_seasons(
    db: Session,
    household_id: uuid.UUID,
    *,
    status: SeasonStatus | None = None,
    crop_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Season], int]:
    """Return one page of seasons plus the unpaginated total."""
    stmt = _scoped(household_id)
    if status is not None:
        stmt = stmt.where(Season.status == status.value)
    if crop_type:
        stmt = stmt.where(func.lower(Season.crop_type) == crop_type.strip().lower())

    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()

    rows = db.execute(
        stmt.order_by(Season.start_date.desc(), Season.id).limit(limit).offset(offset)
    ).scalars().all()

    return list(rows), total


def get_season(db: Session, household_id: uuid.UUID, season_id: str) -> Season:
    season = db.execute(
        _scoped(household_id).where(Season.id == season_id)
    ).scalar_one_or_none()
    if season is None:
        # 404 rather than 403 even when the row exists under another
        # household: distinguishing the two confirms an ID exists somewhere in
        # the system, which leaks across the tenant boundary.
        raise NotFound("Không tìm thấy mùa vụ.")
    return season


# ═══════════════════════════════════════════════════════════════════════════
#  Write
# ═══════════════════════════════════════════════════════════════════════════


def create_season(
    db: Session,
    household_id: uuid.UUID,
    payload: SeasonCreate,
    *,
    device_id: str | None = None,
) -> Season:
    """Create a season, honouring a client-supplied ID (rule R1).

    Re-posting an ID that already exists is a **conflict**, not an update. The
    REST endpoint is for a human filling in a form; a repeated create there is
    a mistake worth surfacing. The sync push endpoint is where an idempotent
    upsert belongs, because there a repeat is a retry.
    """
    season_id = payload.id or str(uuid.uuid4())

    clash = db.execute(select(Season.id).where(Season.id == season_id)).scalar_one_or_none()
    if clash is not None:
        raise Conflict(f"Mùa vụ với id {season_id} đã tồn tại.")

    ts = now_ms()
    season = Season(
        id=season_id,
        household_id=household_id,
        name=payload.name,
        crop_type=payload.crop_type,
        area_size=payload.area_size,
        area_unit=payload.area_unit,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=payload.status.value,
        note=payload.note,
        created_at=payload.created_at or ts,
        updated_at=payload.updated_at or ts,
        last_device_id=device_id,
    )
    db.add(season)
    db.flush()
    return season


def update_season(
    db: Session,
    household_id: uuid.UUID,
    season_id: str,
    payload: SeasonUpdate,
    *,
    device_id: str | None = None,
) -> Season:
    season = get_season(db, household_id, season_id)

    changes = payload.model_dump(exclude_unset=True, exclude={"updated_at"})
    if "status" in changes and changes["status"] is not None:
        changes["status"] = changes["status"].value

    for field, value in changes.items():
        setattr(season, field, value)

    # Validate the range against the merged result, not the payload alone --
    # sending only `end_date` must still be checked against the stored
    # `start_date`.
    if season.end_date is not None and season.end_date < season.start_date:
        raise Conflict("Ngày kết thúc không được trước ngày bắt đầu.")

    season.updated_at = payload.updated_at or now_ms()
    season.last_device_id = device_id
    db.flush()
    return season


def soft_delete_season(
    db: Session,
    household_id: uuid.UUID,
    season_id: str,
    *,
    device_id: str | None = None,
) -> dict[str, int]:
    """Tombstone a season and everything that hangs off it.

    Never a hard DELETE: a hard delete is invisible to a device that was
    offline when it happened, and the pull endpoint has to be able to answer
    "what was destroyed since your cursor?" (rule R3).

    The cascade is deliberately asymmetric, and this is the interesting part:

      * diary entries, expenses and revenues are season-scoped by definition
        and are tombstoned.
      * stock movements **generated by this season's diary work**
        (`diary_entry_id IS NOT NULL`) are tombstoned too, which returns the
        consumed quantity to inventory. That is the same "hoàn kho" rule as
        deleting a single diary entry (invariant I3) — if the work never
        happened, the fertiliser was never used.
      * standalone stock movements that merely *reference* the season
        (a purchase booked against it, `diary_entry_id IS NULL`) are
        **de-allocated, not deleted**. Their `season_id` is set to NULL and
        the row survives. Deleting them would erase a purchase that really
        happened and silently change the on-hand quantity of a supply the
        farmer still physically has. The inventory ledger is append-only
        (D1); a season being deleted is not a reason to rewrite it.
    """
    season = get_season(db, household_id, season_id)
    now = datetime.now(UTC)
    ts = now_ms()

    def _tombstone(model, *extra_where) -> int:
        result = db.execute(
            update(model)
            .where(
                model.season_id == season_id,
                model.household_id == household_id,
                model.deleted_at.is_(None),
                *extra_where,
            )
            .values(deleted_at=now, updated_at=ts, last_device_id=device_id)
        )
        return result.rowcount or 0

    # Children first, so a crash mid-way never leaves a live child pointing at
    # a tombstoned parent.
    stock_deleted = _tombstone(StockTransaction, StockTransaction.diary_entry_id.is_not(None))
    expenses_deleted = _tombstone(Expense)
    revenues_deleted = _tombstone(Revenue)
    diary_deleted = _tombstone(DiaryEntry)

    unlinked = db.execute(
        update(StockTransaction)
        .where(
            StockTransaction.season_id == season_id,
            StockTransaction.household_id == household_id,
            StockTransaction.deleted_at.is_(None),
            StockTransaction.diary_entry_id.is_(None),
        )
        .values(season_id=None, updated_at=ts, last_device_id=device_id)
    ).rowcount or 0

    season.deleted_at = now
    season.updated_at = ts
    season.last_device_id = device_id
    db.flush()

    return {
        "diary_entries_deleted": diary_deleted,
        "expenses_deleted": expenses_deleted,
        "revenues_deleted": revenues_deleted,
        "stock_transactions_deleted": stock_deleted,
        "stock_transactions_unlinked": unlinked,
    }
