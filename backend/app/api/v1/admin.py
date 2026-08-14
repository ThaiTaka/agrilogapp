"""Web Admin Dashboard endpoints (Phase 2, Bước 0).

    GET   /api/v1/admin/overview
    GET   /api/v1/admin/users
    PATCH /api/v1/admin/users/{user_id}
    GET   /api/v1/admin/households
    GET   /api/v1/admin/maintenance
    PUT   /api/v1/admin/maintenance

    GET   /api/v1/maintenance          <- public, for the mobile app

Everything under /admin requires `is_admin` on the caller's database row and
is NOT limited to one household. That is the opposite of every other router
here, so the dependency is declared once on the router rather than repeated
per route — a route added later inherits the guard instead of relying on
whoever writes it to remember.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentAdmin, DbSession, get_current_admin
from app.schemas.admin import (
    AdminHouseholdOut,
    AdminOverview,
    AdminUserOut,
    AdminUserUpdate,
    MaintenanceStatus,
    MaintenanceUpdate,
)
from app.schemas.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.services import admin_service
from app.services.errors import NotFound, ValidationFailed

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_admin)],
    responses={403: {"description": "Tài khoản không có quyền quản trị"}},
)

# Separate router: the mobile app must be able to read the maintenance flag,
# and it is not an administrator.
public_router = APIRouter(tags=["meta"])


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationFailed):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    raise exc


# ═══════════════════════════════════════════════════════════════════════════
#  Overview
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/overview", response_model=AdminOverview, summary="Số liệu tổng quan")
def get_overview(db: DbSession) -> AdminOverview:
    try:
        return AdminOverview(**admin_service.overview(db))
    except NotFound as exc:
        raise _http(exc) from exc


# ═══════════════════════════════════════════════════════════════════════════
#  Users
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/users", response_model=Page[AdminUserOut], summary="Danh sách tài khoản")
def list_users(
    db: DbSession,
    search: Annotated[str | None, Query(max_length=120)] = None,
    is_active: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AdminUserOut]:
    rows, total = admin_service.list_users(
        db, search=search, is_active=is_active, limit=limit, offset=offset
    )
    return Page[AdminUserOut](
        items=[AdminUserOut(**r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserOut,
    summary="Khoá / mở tài khoản",
)
def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    db: DbSession,
    admin: CurrentAdmin,
) -> AdminUserOut:
    """Takes effect on the next request, not at token expiry.

    Login, refresh and `get_current_user` all read `is_active` from the live
    row, so a locked user is refused immediately even while holding an access
    token that has not expired.
    """
    try:
        row = admin_service.set_user_active(
            db, user_id, is_active=payload.is_active, acting_admin=admin
        )
    except (NotFound, ValidationFailed) as exc:
        raise _http(exc) from exc
    result = AdminUserOut(**row)
    db.commit()
    return result


# ═══════════════════════════════════════════════════════════════════════════
#  Households
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/households",
    response_model=Page[AdminHouseholdOut],
    summary="Danh sách nông hộ",
)
def list_households(
    db: DbSession,
    search: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AdminHouseholdOut]:
    rows, total = admin_service.list_households(
        db, search=search, limit=limit, offset=offset
    )
    return Page[AdminHouseholdOut](
        items=[AdminHouseholdOut(**r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Maintenance
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/maintenance",
    response_model=MaintenanceStatus,
    summary="Trạng thái chế độ bảo trì",
)
def get_maintenance(db: DbSession) -> MaintenanceStatus:
    try:
        return MaintenanceStatus.model_validate(admin_service.get_settings(db))
    except NotFound as exc:
        raise _http(exc) from exc


@router.put(
    "/maintenance",
    response_model=MaintenanceStatus,
    summary="Bật / tắt chế độ bảo trì",
)
def set_maintenance(
    payload: MaintenanceUpdate, db: DbSession
) -> MaintenanceStatus:
    try:
        row = admin_service.set_maintenance(
            db,
            enabled=payload.maintenance_enabled,
            message=payload.maintenance_message,
        )
    except NotFound as exc:
        raise _http(exc) from exc
    result = MaintenanceStatus.model_validate(row)
    db.commit()
    return result


@public_router.get(
    "/maintenance",
    response_model=MaintenanceStatus,
    summary="Trạng thái bảo trì (công khai, cho ứng dụng di động)",
)
def public_maintenance(db: DbSession) -> MaintenanceStatus:
    """Unauthenticated on purpose.

    The app has to be able to say "hệ thống đang bảo trì" to a user whose
    token has expired — that is the moment they most need an explanation, and
    requiring auth to read the notice would show them a login failure instead.
    It discloses one boolean and a message written for the public.
    """
    try:
        return MaintenanceStatus.model_validate(admin_service.get_settings(db))
    except NotFound:
        # Never fail the app's startup check over a missing settings row: a
        # system that cannot report its maintenance state is not in
        # maintenance, and blocking the app would be a self-inflicted outage.
        return MaintenanceStatus(maintenance_enabled=False, maintenance_message=None)
