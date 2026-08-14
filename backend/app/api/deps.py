"""Shared FastAPI dependencies.

`get_current_user` is the single place a request is turned into an identity.
Every household-scoped route depends on it, directly or through
`HouseholdId`, so there is exactly one code path that decides who is asking.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TokenError, decode_token
from app.db.session import get_db
from app.models import User

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="Bearer",
    description="JWT access token issued by /auth/login",
)

DbSession = Annotated[Session, Depends(get_db)]

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Không xác thực được. Vui lòng đăng nhập lại.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise _UNAUTHENTICATED

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token không hợp lệ: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except (ValueError, TypeError) as exc:
        raise _UNAUTHENTICATED from exc

    user = db.get(User, user_id)
    if user is None:
        raise _UNAUTHENTICATED
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản đã bị vô hiệu hoá."
        )

    # Defence in depth: the token asserts a household, the database records
    # one. If they disagree the token predates a change we do not model yet,
    # and continuing would scope the request to the wrong tenant -- the single
    # worst failure this API can have.
    if str(user.household_id) != str(payload.get("hid")):
        raise _UNAUTHENTICATED

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_admin(user: CurrentUser) -> User:
    """The identity behind /admin/*, which is NOT household-scoped.

    Layered on `get_current_user` rather than decoding the token itself, so
    admin requests still pass every check ordinary requests do — signature,
    account still active, token/database household agreement — and there is
    still exactly one code path that turns a request into an identity.

    `is_admin` is read from the DATABASE row, never from a token claim. A
    claim is fixed at login and would keep working for the life of the access
    token after the flag is revoked; the row is checked on every request, so
    revoking takes effect immediately.

    403, not 404: the caller is authenticated and we are refusing them, which
    is a different fact from the route not existing. The tenant-boundary
    reasoning that makes NotFound the right answer elsewhere does not apply —
    nothing about /admin/* is a secret whose existence leaks another
    household's data.
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này không có quyền quản trị.",
        )
    return user


CurrentAdmin = Annotated[User, Depends(get_current_admin)]


def get_current_household_id(user: CurrentUser) -> uuid.UUID:
    """The tenant for this request.

    Sync and every CRUD route derive the household from the token, never from
    the request body. A client therefore cannot write into another household
    by forging a field, because the field is not read.
    """
    return user.household_id


HouseholdId = Annotated[uuid.UUID, Depends(get_current_household_id)]


def get_device_id(
    x_device_id: Annotated[str | None, Header(alias="X-Device-Id")] = None,
) -> str | None:
    """Stable per-installation identifier, used for sync auditing.

    Optional: a request without it still works, it just cannot be attributed
    to a device in `sync_sessions`.
    """
    if x_device_id is not None:
        x_device_id = x_device_id.strip()[:128] or None
    return x_device_id


DeviceId = Annotated[str | None, Depends(get_device_id)]
