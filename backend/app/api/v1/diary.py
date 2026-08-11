"""Farming diary endpoints (Issues #21, #25, #29).

    GET    /api/v1/seasons/{season_id}/diary-entries
    POST   /api/v1/seasons/{season_id}/diary-entries
    GET    /api/v1/diary-entries          (across all seasons)
    GET    /api/v1/diary-entries/{id}
    PATCH  /api/v1/diary-entries/{id}
    DELETE /api/v1/diary-entries/{id}
    POST   /api/v1/diary-entries/{id}/restore
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession, DeviceId, HouseholdId
from app.models.enums import WorkType
from app.schemas.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.schemas.diary import (
    DiaryDeleteResult,
    DiaryEntryCreate,
    DiaryEntryOut,
    DiaryEntryUpdate,
    SupplyUsageOut,
)
from app.services import diary_service
from app.services.errors import Conflict, NotFound, ValidationFailed

router = APIRouter(tags=["diary"])

_STATUS = {NotFound: 404, Conflict: 409, ValidationFailed: 422}


def _http(exc: Exception) -> HTTPException:
    for kind, code in _STATUS.items():
        if isinstance(exc, kind):
            return HTTPException(status_code=code, detail=str(exc))
    raise exc


def _serialise(db, entries: list) -> list[DiaryEntryOut]:
    """Attach consumptions to a page of entries with one extra query."""
    usages = diary_service.usages_for(db, [e.id for e in entries])
    out: list[DiaryEntryOut] = []
    for entry in entries:
        lines = [
            SupplyUsageOut(
                transaction_id=txn.id,
                supply_id=supply.id,
                supply_name=supply.name,
                unit=supply.unit,
                quantity=txn.quantity,
                unit_cost=txn.unit_cost,
                total_cost=txn.total_cost,
                note=txn.note,
            )
            for txn, supply in usages.get(entry.id, [])
        ]
        model = DiaryEntryOut.model_validate(entry)
        model.supply_usages = lines
        model.total_supply_cost = sum(
            (line.total_cost for line in lines), start=model.total_supply_cost
        )
        out.append(model)
    return out


def _one(db, entry) -> DiaryEntryOut:
    return _serialise(db, [entry])[0]


# ═══════════════════════════════════════════════════════════════════════════
#  Season-scoped
# ═══════════════════════════════════════════════════════════════════════════

season_router = APIRouter(prefix="/seasons/{season_id}/diary-entries", tags=["diary"])


@season_router.get("", response_model=Page[DiaryEntryOut], summary="Nhật ký của một mùa vụ")
def list_for_season(
    season_id: str,
    db: DbSession,
    household_id: HouseholdId,
    work_type: Annotated[WorkType | None, Query()] = None,
    date_from: Annotated[int | None, Query(description="Epoch ms")] = None,
    date_to: Annotated[int | None, Query(description="Epoch ms")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[DiaryEntryOut]:
    rows, total = diary_service.list_entries(
        db,
        household_id,
        season_id=season_id,
        work_type=work_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return Page[DiaryEntryOut](
        items=_serialise(db, rows), total=total, limit=limit, offset=offset
    )


@season_router.post(
    "",
    response_model=DiaryEntryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ghi nhật ký (kèm vật tư sử dụng)",
)
def create_entry(
    season_id: str,
    payload: DiaryEntryCreate,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
) -> DiaryEntryOut:
    """Recording supply usage here does three things in one transaction:
    writes the diary entry, appends a stock-out per supply, and generates the
    matching expense. The farmer enters the fertiliser once."""
    try:
        diary_service.validate_usage_supplies(db, household_id, payload.supply_usages)
        entry = diary_service.create_entry(
            db, household_id, season_id, payload, device_id=device_id
        )
        result = _one(db, entry)
    except (NotFound, Conflict, ValidationFailed) as exc:
        raise _http(exc) from exc
    db.commit()
    return result


# ═══════════════════════════════════════════════════════════════════════════
#  Entry-scoped
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/diary-entries", response_model=Page[DiaryEntryOut], summary="Nhật ký (mọi mùa vụ)"
)
def list_all(
    db: DbSession,
    household_id: HouseholdId,
    season_id: Annotated[str | None, Query()] = None,
    work_type: Annotated[WorkType | None, Query()] = None,
    date_from: Annotated[int | None, Query()] = None,
    date_to: Annotated[int | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[DiaryEntryOut]:
    rows, total = diary_service.list_entries(
        db,
        household_id,
        season_id=season_id,
        work_type=work_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return Page[DiaryEntryOut](
        items=_serialise(db, rows), total=total, limit=limit, offset=offset
    )


@router.get("/diary-entries/{entry_id}", response_model=DiaryEntryOut, summary="Chi tiết nhật ký")
def get_entry(entry_id: str, db: DbSession, household_id: HouseholdId) -> DiaryEntryOut:
    try:
        entry = diary_service.get_entry(db, household_id, entry_id)
    except NotFound as exc:
        raise _http(exc) from exc
    return _one(db, entry)


@router.patch("/diary-entries/{entry_id}", response_model=DiaryEntryOut, summary="Sửa nhật ký")
def update_entry(
    entry_id: str,
    payload: DiaryEntryUpdate,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
) -> DiaryEntryOut:
    """Editing supply usage adjusts inventory automatically (hoàn kho, #25).

    `supply_usages` omitted leaves consumption untouched; `[]` reverses all of
    it. The two are deliberately different — collapsing them would make
    "I only fixed a typo in the note" silently wipe the fertiliser record.
    """
    try:
        if payload.supply_usages is not None:
            diary_service.validate_usage_supplies(db, household_id, payload.supply_usages)
        entry = diary_service.update_entry(
            db, household_id, entry_id, payload, device_id=device_id
        )
        result = _one(db, entry)
    except (NotFound, Conflict, ValidationFailed) as exc:
        raise _http(exc) from exc
    db.commit()
    return result


@router.delete(
    "/diary-entries/{entry_id}",
    response_model=DiaryDeleteResult,
    summary="Xoá nhật ký (tự động hoàn kho)",
)
def delete_entry(
    entry_id: str, db: DbSession, household_id: HouseholdId, device_id: DeviceId
) -> DiaryDeleteResult:
    """Returns what was reversed, so the UI can say "3 khoản vật tư đã hoàn kho"
    rather than leaving the farmer to check the inventory screen."""
    try:
        counts = diary_service.soft_delete_entry(
            db, household_id, entry_id, device_id=device_id
        )
    except NotFound as exc:
        raise _http(exc) from exc
    db.commit()
    return DiaryDeleteResult(id=entry_id, **counts)


@router.post(
    "/diary-entries/{entry_id}/restore",
    response_model=DiaryEntryOut,
    summary="Khôi phục nhật ký đã xoá",
)
def restore_entry(
    entry_id: str, db: DbSession, household_id: HouseholdId, device_id: DeviceId
) -> DiaryEntryOut:
    """"Xoá nhầm" is the most common mistake in a field app operated with
    muddy hands."""
    try:
        entry = diary_service.restore_entry(db, household_id, entry_id, device_id=device_id)
        result = _one(db, entry)
    except (NotFound, Conflict) as exc:
        raise _http(exc) from exc
    db.commit()
    return result
