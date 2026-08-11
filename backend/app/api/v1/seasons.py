"""Season CRUD endpoints (Issue #19).

    GET    /api/v1/seasons
    POST   /api/v1/seasons
    GET    /api/v1/seasons/{season_id}
    PATCH  /api/v1/seasons/{season_id}
    DELETE /api/v1/seasons/{season_id}

Every route is scoped to the household in the JWT. There is no code path that
can return another household's row.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession, DeviceId, HouseholdId
from app.models.enums import SeasonStatus
from app.schemas.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.schemas.season import (
    SeasonCreate,
    SeasonDeleteResult,
    SeasonOut,
    SeasonUpdate,
)
from app.services import season_service
from app.services.errors import Conflict, NotFound

router = APIRouter(prefix="/seasons", tags=["seasons"])


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, Conflict):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    raise exc


@router.get("", response_model=Page[SeasonOut], summary="Danh sách mùa vụ")
def list_seasons(
    db: DbSession,
    household_id: HouseholdId,
    status_filter: Annotated[SeasonStatus | None, Query(alias="status")] = None,
    crop_type: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[SeasonOut]:
    rows, total = season_service.list_seasons(
        db,
        household_id,
        status=status_filter,
        crop_type=crop_type,
        limit=limit,
        offset=offset,
    )
    return Page[SeasonOut](
        items=[SeasonOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=SeasonOut,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo mùa vụ",
)
def create_season(
    payload: SeasonCreate,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
) -> SeasonOut:
    try:
        season = season_service.create_season(db, household_id, payload, device_id=device_id)
    except (NotFound, Conflict) as exc:
        raise _http(exc) from exc
    result = SeasonOut.model_validate(season)
    db.commit()
    return result


@router.get("/{season_id}", response_model=SeasonOut, summary="Chi tiết mùa vụ")
def get_season(season_id: str, db: DbSession, household_id: HouseholdId) -> SeasonOut:
    try:
        return SeasonOut.model_validate(season_service.get_season(db, household_id, season_id))
    except NotFound as exc:
        raise _http(exc) from exc


@router.patch("/{season_id}", response_model=SeasonOut, summary="Cập nhật mùa vụ")
def update_season(
    season_id: str,
    payload: SeasonUpdate,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
) -> SeasonOut:
    try:
        season = season_service.update_season(
            db, household_id, season_id, payload, device_id=device_id
        )
    except (NotFound, Conflict) as exc:
        raise _http(exc) from exc
    result = SeasonOut.model_validate(season)
    db.commit()
    return result


@router.delete(
    "/{season_id}",
    response_model=SeasonDeleteResult,
    summary="Xoá mùa vụ (soft delete, kèm dữ liệu con)",
)
def delete_season(
    season_id: str,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
) -> SeasonDeleteResult:
    """Soft delete. Returns what the cascade removed.

    A body rather than 204: deleting a season takes its diary entries,
    expenses and revenues with it, and a farmer tapping "xoá" deserves to be
    told that 40 entries went too.
    """
    try:
        counts = season_service.soft_delete_season(
            db, household_id, season_id, device_id=device_id
        )
    except NotFound as exc:
        raise _http(exc) from exc
    db.commit()
    return SeasonDeleteResult(id=season_id, **counts)
