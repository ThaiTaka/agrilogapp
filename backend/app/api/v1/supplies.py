"""Supply catalogue and inventory endpoints (Issue #23).

    GET    /api/v1/supplies
    POST   /api/v1/supplies
    GET    /api/v1/supplies/{supply_id}
    PATCH  /api/v1/supplies/{supply_id}
    DELETE /api/v1/supplies/{supply_id}
    GET    /api/v1/supplies/{supply_id}/transactions
    POST   /api/v1/supplies/{supply_id}/stock-in
    POST   /api/v1/supplies/{supply_id}/stock-out
    POST   /api/v1/supplies/{supply_id}/stock-take
    DELETE /api/v1/supplies/{supply_id}/transactions/{txn_id}
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession, DeviceId, HouseholdId
from app.models.enums import SupplyCategory, TxnType
from app.schemas.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.schemas.supply import (
    StockAdjustCreate,
    StockAdjustResult,
    StockMovementCreate,
    StockMovementResult,
    StockTransactionOut,
    SupplyCreate,
    SupplyOut,
    SupplyUpdate,
)
from app.services import supply_service
from app.services.errors import Conflict, NotFound, ValidationFailed

router = APIRouter(prefix="/supplies", tags=["supplies"])

_STATUS = {NotFound: 404, Conflict: 409, ValidationFailed: 422}


def _http(exc: Exception) -> HTTPException:
    for kind, code in _STATUS.items():
        if isinstance(exc, kind):
            return HTTPException(status_code=code, detail=str(exc))
    raise exc


def _out(supply, on_hand) -> SupplyOut:
    return SupplyOut.model_validate({**supply.__dict__, "on_hand": on_hand})


def _with_level(db, household_id, supply) -> SupplyOut:
    return _out(supply, supply_service.stock_level(db, household_id, supply.id))


# ═══════════════════════════════════════════════════════════════════════════
#  Catalogue
# ═══════════════════════════════════════════════════════════════════════════


@router.get("", response_model=Page[SupplyOut], summary="Danh sách vật tư và tồn kho")
def list_supplies(
    db: DbSession,
    household_id: HouseholdId,
    category: Annotated[SupplyCategory | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    include_archived: Annotated[bool, Query()] = False,
    low_stock_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[SupplyOut]:
    pairs, total = supply_service.list_supplies(
        db,
        household_id,
        category=category,
        search=search,
        include_archived=include_archived,
        low_stock_only=low_stock_only,
        limit=limit,
        offset=offset,
    )
    return Page[SupplyOut](
        items=[_out(s, level) for s, level in pairs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "", response_model=SupplyOut, status_code=status.HTTP_201_CREATED, summary="Thêm vật tư"
)
def create_supply(
    payload: SupplyCreate,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
) -> SupplyOut:
    try:
        supply = supply_service.create_supply(db, household_id, payload, device_id=device_id)
    except (NotFound, Conflict, ValidationFailed) as exc:
        raise _http(exc) from exc
    result = _out(supply, supply_service.ZERO_QUANTITY)
    db.commit()
    return result


@router.get("/{supply_id}", response_model=SupplyOut, summary="Chi tiết vật tư")
def get_supply(supply_id: str, db: DbSession, household_id: HouseholdId) -> SupplyOut:
    try:
        supply = supply_service.get_supply(db, household_id, supply_id)
    except NotFound as exc:
        raise _http(exc) from exc
    return _with_level(db, household_id, supply)


@router.patch("/{supply_id}", response_model=SupplyOut, summary="Cập nhật vật tư")
def update_supply(
    supply_id: str,
    payload: SupplyUpdate,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
) -> SupplyOut:
    """Changing `unit_cost` affects future movements only.

    Past transactions keep the price snapshotted when they happened, so
    updating today's price cannot rewrite a closed season's costs.
    """
    try:
        supply = supply_service.update_supply(
            db, household_id, supply_id, payload, device_id=device_id
        )
    except (NotFound, Conflict, ValidationFailed) as exc:
        raise _http(exc) from exc
    result = _with_level(db, household_id, supply)
    db.commit()
    return result


@router.delete(
    "/{supply_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xoá vật tư (chỉ khi chưa có giao dịch kho)",
)
def delete_supply(
    supply_id: str, db: DbSession, household_id: HouseholdId, device_id: DeviceId
):
    """409 if the supply has movement history — archive it instead.

    Tombstoning it would make every device drop the row locally, leaving last
    season's diary entries showing a blank supply name.
    """
    try:
        supply_service.delete_supply(db, household_id, supply_id, device_id=device_id)
    except (NotFound, Conflict) as exc:
        raise _http(exc) from exc
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  Ledger
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/{supply_id}/transactions",
    response_model=Page[StockTransactionOut],
    summary="Lịch sử nhập/xuất của một vật tư",
)
def list_transactions(
    supply_id: str,
    db: DbSession,
    household_id: HouseholdId,
    txn_type: Annotated[TxnType | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[StockTransactionOut]:
    try:
        supply_service.get_supply(db, household_id, supply_id)
    except NotFound as exc:
        raise _http(exc) from exc

    rows, total = supply_service.list_transactions(
        db, household_id, supply_id=supply_id, txn_type=txn_type, limit=limit, offset=offset
    )
    return Page[StockTransactionOut](
        items=[StockTransactionOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def _movement(db, household_id, supply_id, payload, txn_type, device_id) -> StockMovementResult:
    try:
        txn = supply_service.record_movement(
            db, household_id, supply_id, payload, txn_type=txn_type, device_id=device_id
        )
    except (NotFound, Conflict, ValidationFailed) as exc:
        raise _http(exc) from exc

    supply = supply_service.get_supply(db, household_id, supply_id)
    result = StockMovementResult(
        transaction=StockTransactionOut.model_validate(txn),
        supply=_with_level(db, household_id, supply),
    )
    db.commit()
    return result


@router.post(
    "/{supply_id}/stock-in",
    response_model=StockMovementResult,
    status_code=status.HTTP_201_CREATED,
    summary="Nhập kho",
)
def stock_in(
    supply_id: str,
    payload: StockMovementCreate,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
) -> StockMovementResult:
    return _movement(db, household_id, supply_id, payload, TxnType.IN, device_id)


@router.post(
    "/{supply_id}/stock-out",
    response_model=StockMovementResult,
    status_code=status.HTTP_201_CREATED,
    summary="Xuất kho",
)
def stock_out(
    supply_id: str,
    payload: StockMovementCreate,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
) -> StockMovementResult:
    """Recording more than is on hand is allowed, and produces a negative balance.

    Blocking it would force a farmer who forgot to log a purchase to abandon
    the usage entry entirely — and a missing log is worse than a number they
    can correct later (invariant I2). The response flags `is_negative` so the
    UI can prompt for the missing stock-in.
    """
    return _movement(db, household_id, supply_id, payload, TxnType.OUT, device_id)


@router.post(
    "/{supply_id}/stock-take",
    response_model=StockAdjustResult,
    summary="Kiểm kê (nhập số đếm thực tế)",
)
def stock_take(
    supply_id: str,
    payload: StockAdjustCreate,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
) -> StockAdjustResult:
    """The farmer enters what they counted; the server records the delta."""
    try:
        txn, delta = supply_service.record_stock_take(
            db, household_id, supply_id, payload, device_id=device_id
        )
    except (NotFound, Conflict, ValidationFailed) as exc:
        raise _http(exc) from exc

    supply = supply_service.get_supply(db, household_id, supply_id)
    result = StockAdjustResult(
        transaction=StockTransactionOut.model_validate(txn) if txn else None,
        supply=_with_level(db, household_id, supply),
        delta=delta,
        no_change=txn is None,
    )
    db.commit()
    return result


@router.delete(
    "/{supply_id}/transactions/{txn_id}",
    response_model=SupplyOut,
    summary="Huỷ một giao dịch kho",
)
def void_transaction(
    supply_id: str,
    txn_id: str,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
) -> SupplyOut:
    """Returns the supply with its recalculated balance."""
    try:
        supply_service.void_transaction(db, household_id, txn_id, device_id=device_id)
        supply = supply_service.get_supply(db, household_id, supply_id)
    except (NotFound, Conflict) as exc:
        raise _http(exc) from exc
    result = _with_level(db, household_id, supply)
    db.commit()
    return result
