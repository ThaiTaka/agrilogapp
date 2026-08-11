"""Authentication endpoints (Issue #14).

    POST /api/v1/auth/register
    POST /api/v1/auth/login
    POST /api/v1/auth/refresh
    POST /api/v1/auth/logout
    GET  /api/v1/auth/me
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUser, DbSession, DeviceId
from app.models import Household
from app.schemas.auth import (
    HouseholdOut,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_pair(db, user, access: str, refresh: str) -> TokenPair:
    household = db.get(Household, user.household_id)
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=auth_service.access_token_ttl_seconds(),
        user=UserOut.model_validate(user),
        household=HouseholdOut.model_validate(household),
    )


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    summary="Đăng ký nông hộ mới",
)
def register(payload: RegisterRequest, db: DbSession, device_id: DeviceId) -> TokenPair:
    """Create a household and its first user, then log straight in.

    Returning tokens here rather than forcing a separate login saves the app a
    second network round-trip during onboarding — which, on a rural
    connection, is a second chance to fail.
    """
    try:
        user, _ = auth_service.register_household(
            db,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            household_name=payload.household_name,
            phone=payload.phone,
            province=payload.province,
            commune=payload.commune,
        )
    except auth_service.EmailAlreadyRegistered as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    access, refresh = auth_service.issue_tokens(db, user, device_id=device_id)
    result = _token_pair(db, user, access, refresh)
    db.commit()
    return result


@router.post("/login", response_model=TokenPair, summary="Đăng nhập")
def login(payload: LoginRequest, db: DbSession, device_id: DeviceId) -> TokenPair:
    try:
        user = auth_service.authenticate(db, email=payload.email, password=payload.password)
    except auth_service.AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    access, refresh = auth_service.issue_tokens(db, user, device_id=device_id)
    result = _token_pair(db, user, access, refresh)
    db.commit()
    return result


@router.post("/refresh", response_model=TokenPair, summary="Làm mới phiên đăng nhập")
def refresh(payload: RefreshRequest, db: DbSession, device_id: DeviceId) -> TokenPair:
    """Exchange a refresh token for a new pair.

    Refresh tokens are single-use. Presenting one that has already been
    rotated revokes every session for that user — see
    `auth_service.rotate_refresh_token`.
    """
    try:
        user, access, new_refresh = auth_service.rotate_refresh_token(
            db, payload.refresh_token, device_id=device_id
        )
    except auth_service.AuthError as exc:
        db.commit()   # persist any revocations the reuse check performed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    result = _token_pair(db, user, access, new_refresh)
    db.commit()
    return result


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Đăng xuất (thu hồi refresh token)",
)
def logout(payload: LogoutRequest, db: DbSession) -> Response:
    """Revoke one session.

    Deliberately returns 204 whether or not the token was live. A caller
    logging out should never be told "that token was already invalid" — it is
    not actionable, and it confirms token validity to anyone probing.
    """
    auth_service.revoke_refresh_token(db, payload.refresh_token)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut, summary="Thông tin tài khoản hiện tại")
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
