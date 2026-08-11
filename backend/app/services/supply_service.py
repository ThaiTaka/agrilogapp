"""Supply catalogue and inventory ledger (Issue #23).

The central rule, and the reason this module looks the way it does:

    on_hand is NEVER stored. It is always Σin + Σadjust − Σout over the
    live ledger.

A stored counter has to be mutated by the server *and* by every offline
device. Two devices each decrementing a cached counter while offline produce a
number that is simply wrong after sync, with no way to detect it. Deriving
from an append-only ledger means those two devices contribute two independent
rows, both sync cleanly, and the total is correct by construction (D1).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from app.core.numeric import ZERO_QUANTITY, line_total, quantize_money, quantize_quantity
from app.core.text import normalise_key
from app.core.timeutils import now_ms
from app.models import Season, StockTransaction, Supply
from app.models.enums import SupplyCategory, TxnType
from app.schemas.supply import (
    StockAdjustCreate,
    StockMovementCreate,
    SupplyCreate,
    SupplyUpdate,
)
from app.services.errors import Conflict, NotFound, ValidationFailed

UTC = timezone.utc


def _scoped(household_id: uuid.UUID) -> Select:
    return select(Supply).where(
        Supply.household_id == household_id, Supply.deleted_at.is_(None)
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Stock levels — the derived quantity
# ═══════════════════════════════════════════════════════════════════════════

# in and adjust add; out subtracts. `adjust` carries a signed delta, so it is
# added as-is rather than having its own branch.
_SIGNED_QUANTITY = case(
    (StockTransaction.txn_type == TxnType.OUT.value, -StockTransaction.quantity),
    else_=StockTransaction.quantity,
)


def stock_levels(
    db: Session, household_id: uuid.UUID, supply_ids: list[str] | None = None
) -> dict[str, Decimal]:
    """On-hand quantity per supply, in ONE query.

    Batched deliberately: computing this per row would turn a 40-item
    inventory screen into 41 round-trips, which is exactly the kind of thing
    that makes an app feel broken on a slow connection.
    """
    stmt = (
        select(StockTransaction.supply_id, func.sum(_SIGNED_QUANTITY))
        .where(
            StockTransaction.household_id == household_id,
            StockTransaction.deleted_at.is_(None),
        )
        .group_by(StockTransaction.supply_id)
    )
    if supply_ids is not None:
        if not supply_ids:
            return {}
        stmt = stmt.where(StockTransaction.supply_id.in_(supply_ids))

    return {
        sid: quantize_quantity(total or 0) for sid, total in db.execute(stmt).all()
    }


def stock_level(db: Session, household_id: uuid.UUID, supply_id: str) -> Decimal:
    return stock_levels(db, household_id, [supply_id]).get(supply_id, ZERO_QUANTITY)


# ═══════════════════════════════════════════════════════════════════════════
#  Supply CRUD
# ═══════════════════════════════════════════════════════════════════════════


def list_supplies(
    db: Session,
    household_id: uuid.UUID,
    *,
    category: SupplyCategory | None = None,
    search: str | None = None,
    include_archived: bool = False,
    low_stock_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Supply, Decimal]], int]:
    """Return `(supply, on_hand)` pairs plus the unpaginated total."""
    stmt = _scoped(household_id)
    if not include_archived:
        stmt = stmt.where(Supply.is_archived.is_(False))
    if category is not None:
        stmt = stmt.where(Supply.category == category.value)
    if search:
        stmt = stmt.where(Supply.name.ilike(f"%{search.strip()}%"))

    if low_stock_only:
        # Filtered in Python rather than SQL: the comparison is against a
        # derived aggregate, and pushing it into SQL means a correlated
        # subquery per row. Household inventories are tens of items, not
        # thousands, so the simpler code wins. Revisit under Issue #49 if a
        # real dataset ever says otherwise.
        rows = db.execute(stmt.order_by(Supply.category, Supply.name)).scalars().all()
        levels = stock_levels(db, household_id, [s.id for s in rows])
        pairs = [
            (s, levels.get(s.id, ZERO_QUANTITY))
            for s in rows
            if s.low_stock_threshold > 0
            and levels.get(s.id, ZERO_QUANTITY) <= s.low_stock_threshold
        ]
        return pairs[offset : offset + limit], len(pairs)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(Supply.category, Supply.name).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )
    levels = stock_levels(db, household_id, [s.id for s in rows])
    return [(s, levels.get(s.id, ZERO_QUANTITY)) for s in rows], total


def get_supply(db: Session, household_id: uuid.UUID, supply_id: str) -> Supply:
    supply = db.execute(_scoped(household_id).where(Supply.id == supply_id)).scalar_one_or_none()
    if supply is None:
        raise NotFound("Không tìm thấy vật tư.")
    return supply


def create_supply(
    db: Session,
    household_id: uuid.UUID,
    payload: SupplyCreate,
    *,
    device_id: str | None = None,
) -> Supply:
    supply_id = payload.id or str(uuid.uuid4())

    if db.execute(select(Supply.id).where(Supply.id == supply_id)).scalar_one_or_none():
        raise Conflict(f"Vật tư với id {supply_id} đã tồn tại.")

    # Checked here as well as by uq_supply_key_unit so the farmer gets a
    # readable message instead of a constraint name. The index remains the
    # authority — this check races, that one does not.
    #
    # Compared on `name_key`, never `func.lower(name)`: PostgreSQL's lower()
    # folds per the database collation and leaves Vietnamese characters alone
    # under `C`, so a lower()-based comparison silently matches nothing.
    name_key = normalise_key(payload.name)
    duplicate = db.execute(
        _scoped(household_id).where(
            Supply.name_key == name_key, Supply.unit == payload.unit
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise Conflict(
            f"Vật tư '{payload.name}' ({payload.unit}) đã có trong danh mục."
        )

    ts = now_ms()
    supply = Supply(
        id=supply_id,
        household_id=household_id,
        name=payload.name,
        name_key=name_key,
        category=payload.category.value,
        unit=payload.unit,
        unit_cost=quantize_money(payload.unit_cost),
        low_stock_threshold=quantize_quantity(payload.low_stock_threshold),
        note=payload.note,
        is_archived=False,
        created_at=payload.created_at or ts,
        updated_at=payload.updated_at or ts,
        last_device_id=device_id,
    )
    db.add(supply)
    db.flush()
    return supply


def update_supply(
    db: Session,
    household_id: uuid.UUID,
    supply_id: str,
    payload: SupplyUpdate,
    *,
    device_id: str | None = None,
) -> Supply:
    """Update the catalogue entry.

    Changing `unit_cost` affects only FUTURE movements. Past transactions keep
    the price snapshotted at the time they happened, so updating today's price
    cannot rewrite the financial history of a season that already closed.
    """
    supply = get_supply(db, household_id, supply_id)
    changes = payload.model_dump(exclude_unset=True, exclude={"updated_at"})

    if "category" in changes and changes["category"] is not None:
        changes["category"] = changes["category"].value
    if "unit_cost" in changes and changes["unit_cost"] is not None:
        changes["unit_cost"] = quantize_money(changes["unit_cost"])
    if "low_stock_threshold" in changes and changes["low_stock_threshold"] is not None:
        changes["low_stock_threshold"] = quantize_quantity(changes["low_stock_threshold"])

    new_name = changes.get("name", supply.name)
    new_unit = changes.get("unit", supply.unit)
    new_key = normalise_key(str(new_name))
    if (new_key, new_unit) != (supply.name_key, supply.unit):
        clash = db.execute(
            _scoped(household_id).where(
                Supply.name_key == new_key,
                Supply.unit == new_unit,
                Supply.id != supply_id,
            )
        ).scalar_one_or_none()
        if clash is not None:
            raise Conflict(f"Vật tư '{new_name}' ({new_unit}) đã có trong danh mục.")

    for field, value in changes.items():
        setattr(supply, field, value)
    supply.name_key = new_key

    supply.updated_at = payload.updated_at or now_ms()
    supply.last_device_id = device_id
    db.flush()
    return supply


def delete_supply(
    db: Session,
    household_id: uuid.UUID,
    supply_id: str,
    *,
    device_id: str | None = None,
) -> None:
    """Tombstone a supply — only if it has never moved.

    A supply with movement history must be archived instead. Two reasons, and
    both are about other devices rather than this one:

      * a tombstone makes WatermelonDB drop the row locally, so last season's
        diary entries would render a blank supply name on every device;
      * the ledger is append-only (D1) and its rows carry the prices that
        past seasons were costed at. Removing the catalogue entry they point
        at rewrites that history.
    """
    supply = get_supply(db, household_id, supply_id)

    movements = db.execute(
        select(func.count())
        .select_from(StockTransaction)
        .where(
            StockTransaction.supply_id == supply_id,
            StockTransaction.deleted_at.is_(None),
        )
    ).scalar_one()

    if movements:
        raise Conflict(
            f"Vật tư này đã có {movements} giao dịch kho nên không thể xoá. "
            "Hãy lưu trữ (archive) để ẩn khỏi danh sách mà vẫn giữ lịch sử."
        )

    supply.deleted_at = datetime.now(UTC)
    supply.updated_at = now_ms()
    supply.last_device_id = device_id
    db.flush()


# ═══════════════════════════════════════════════════════════════════════════
#  Ledger
# ═══════════════════════════════════════════════════════════════════════════


def list_transactions(
    db: Session,
    household_id: uuid.UUID,
    *,
    supply_id: str | None = None,
    season_id: str | None = None,
    txn_type: TxnType | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[StockTransaction], int]:
    stmt = select(StockTransaction).where(
        StockTransaction.household_id == household_id,
        StockTransaction.deleted_at.is_(None),
    )
    if supply_id:
        stmt = stmt.where(StockTransaction.supply_id == supply_id)
    if season_id:
        stmt = stmt.where(StockTransaction.season_id == season_id)
    if txn_type is not None:
        stmt = stmt.where(StockTransaction.txn_type == txn_type.value)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(StockTransaction.txn_date.desc(), StockTransaction.id)
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return list(rows), total


def _validate_season(db: Session, household_id: uuid.UUID, season_id: str | None) -> None:
    if season_id is None:
        return
    exists = db.execute(
        select(Season.id).where(
            Season.id == season_id,
            Season.household_id == household_id,
            Season.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if exists is None:
        raise NotFound("Không tìm thấy mùa vụ được chỉ định.")


def record_movement(
    db: Session,
    household_id: uuid.UUID,
    supply_id: str,
    payload: StockMovementCreate,
    *,
    txn_type: TxnType,
    diary_entry_id: str | None = None,
    device_id: str | None = None,
) -> StockTransaction:
    """Append one movement to the ledger.

    Note what is deliberately absent: any update to a stock counter. The
    ledger row IS the state change.
    """
    supply = get_supply(db, household_id, supply_id)
    _validate_season(db, household_id, payload.season_id)

    txn_id = payload.id or str(uuid.uuid4())
    if db.execute(
        select(StockTransaction.id).where(StockTransaction.id == txn_id)
    ).scalar_one_or_none():
        raise Conflict(f"Giao dịch với id {txn_id} đã tồn tại.")

    quantity = quantize_quantity(payload.quantity)
    if quantity <= 0:
        raise ValidationFailed("Số lượng phải lớn hơn 0.")

    # Snapshot, not a live join: fertiliser bought in March at 12,000đ/kg and
    # used in September must stay costed at what it actually cost.
    unit_cost = quantize_money(
        payload.unit_cost if payload.unit_cost is not None else supply.unit_cost
    )

    ts = now_ms()
    txn = StockTransaction(
        id=txn_id,
        household_id=household_id,
        supply_id=supply_id,
        season_id=payload.season_id,
        diary_entry_id=diary_entry_id,
        txn_type=txn_type.value,
        quantity=quantity,
        unit_cost=unit_cost,
        total_cost=line_total(quantity, unit_cost),
        txn_date=payload.txn_date or ts,
        note=payload.note,
        created_at=payload.created_at or ts,
        updated_at=payload.updated_at or ts,
        last_device_id=device_id,
    )
    db.add(txn)
    db.flush()
    return txn


def record_stock_take(
    db: Session,
    household_id: uuid.UUID,
    supply_id: str,
    payload: StockAdjustCreate,
    *,
    device_id: str | None = None,
) -> tuple[StockTransaction | None, Decimal]:
    """Reconcile the ledger against a physical count.

    Returns `(transaction_or_None, delta)`. A count matching the ledger writes
    nothing: the CHECK constraint forbids a zero-quantity adjustment, and more
    importantly a no-op row would bump `updated_at` and manufacture a phantom
    conflict for another device that is editing the same supply.
    """
    get_supply(db, household_id, supply_id)

    counted = quantize_quantity(payload.counted_quantity)
    current = stock_level(db, household_id, supply_id)
    delta = quantize_quantity(counted - current)

    if delta == 0:
        return None, delta

    txn_id = payload.id or str(uuid.uuid4())
    ts = now_ms()
    txn = StockTransaction(
        id=txn_id,
        household_id=household_id,
        supply_id=supply_id,
        txn_type=TxnType.ADJUST.value,
        quantity=delta,          # signed; the CHECK permits either direction
        unit_cost=quantize_money(0),
        total_cost=quantize_money(0),
        txn_date=payload.txn_date or ts,
        note=payload.note or f"Kiểm kê: {current} → {counted}",
        created_at=ts,
        updated_at=ts,
        last_device_id=device_id,
    )
    db.add(txn)
    db.flush()
    return txn, delta


def void_transaction(
    db: Session,
    household_id: uuid.UUID,
    txn_id: str,
    *,
    device_id: str | None = None,
) -> StockTransaction:
    """Tombstone a movement, which returns its effect to the derived balance.

    Refused for movements owned by a diary entry: those are reconciled by
    editing the diary entry (Issue #25), and voiding one here would leave the
    entry claiming a consumption that no longer exists in the ledger.
    """
    txn = db.execute(
        select(StockTransaction).where(
            StockTransaction.id == txn_id,
            StockTransaction.household_id == household_id,
            StockTransaction.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if txn is None:
        raise NotFound("Không tìm thấy giao dịch kho.")

    if txn.diary_entry_id is not None:
        raise Conflict(
            "Giao dịch này được sinh từ nhật ký canh tác. "
            "Hãy sửa hoặc xoá nhật ký tương ứng để hoàn kho."
        )

    txn.deleted_at = datetime.now(UTC)
    txn.updated_at = now_ms()
    txn.last_device_id = device_id
    db.flush()
    return txn
