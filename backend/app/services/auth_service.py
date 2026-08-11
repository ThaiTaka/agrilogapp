"""Authentication business logic (Issue #14).

Kept out of the router so the rules are testable without HTTP, and so the
seed script can create accounts through the same code path the API uses.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import Household, RefreshToken, User

UTC = timezone.utc

# Compared against when the email does not exist, so a login attempt costs the
# same whether or not the account is real. Without it, response time alone
# tells an attacker which emails are registered.
_DUMMY_HASH = hash_password("timing-attack-placeholder")


class AuthError(Exception):
    """Authentication failed. The message is safe to show a user."""


class EmailAlreadyRegistered(AuthError):
    pass


def normalise_email(email: str) -> str:
    """Lowercase and trim.

    The `uq_users_email_lower` index is on `lower(email)`, so storing a
    lowercase value keeps the stored data and the index in agreement and makes
    `WHERE email = :x` usable without a function call.
    """
    return email.strip().lower()


# ═══════════════════════════════════════════════════════════════════════════
#  Registration
# ═══════════════════════════════════════════════════════════════════════════


def register_household(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    household_name: str,
    phone: str | None = None,
    province: str | None = None,
    commune: str | None = None,
) -> tuple[User, Household]:
    """Create a household and its first user atomically.

    A user without a household cannot own a single row in this system (rule
    R4), so a partial creation would be an account that can log in and do
    nothing.
    """
    email = normalise_email(email)

    household = Household(
        name=household_name.strip(),
        phone=phone,
        province=province,
        commune=commune,
    )
    db.add(household)
    db.flush()   # assigns household.id without committing

    user = User(
        household_id=household.id,
        email=email,
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        if "uq_users_email_lower" in str(exc.orig):
            raise EmailAlreadyRegistered("Email này đã được đăng ký.") from exc
        raise

    return user, household


# ═══════════════════════════════════════════════════════════════════════════
#  Login
# ═══════════════════════════════════════════════════════════════════════════


def authenticate(db: Session, *, email: str, password: str) -> User:
    """Verify credentials.

    Every failure mode returns the *same* message. Distinguishing "no such
    email" from "wrong password" turns the login form into an account
    enumeration oracle.
    """
    user = db.execute(
        select(User).where(func.lower(User.email) == normalise_email(email))
    ).scalar_one_or_none()

    if user is None:
        verify_password(password, _DUMMY_HASH)   # constant-ish time
        raise AuthError("Email hoặc mật khẩu không đúng.")

    if not verify_password(password, user.password_hash):
        raise AuthError("Email hoặc mật khẩu không đúng.")

    if not user.is_active:
        raise AuthError("Tài khoản đã bị vô hiệu hoá.")

    return user


# ═══════════════════════════════════════════════════════════════════════════
#  Tokens
# ═══════════════════════════════════════════════════════════════════════════


def issue_tokens(db: Session, user: User, *, device_id: str | None = None) -> tuple[str, str]:
    """Mint an access/refresh pair and persist the refresh token's hash.

    Returns ``(access_token, refresh_token)``. Only the SHA-256 hash of the
    refresh token is stored, so a database leak does not hand out live
    sessions.
    """
    access = create_access_token(user.id, user.household_id)
    raw_refresh, token_hash, expires_at = create_refresh_token(user.id)

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            device_id=device_id,
            expires_at=expires_at,
        )
    )
    db.flush()
    return access, raw_refresh


def rotate_refresh_token(
    db: Session, raw_token: str, *, device_id: str | None = None
) -> tuple[User, str, str]:
    """Exchange a refresh token for a new pair, invalidating the old one.

    Rotation with reuse detection: a refresh token is single-use. If one that
    has already been rotated is presented again, the only two explanations are
    a stolen token or a client bug -- and we cannot tell which. Every session
    for that user is therefore revoked, forcing a fresh login. Losing a
    session is recoverable; an attacker holding a 90-day credential is not.
    """
    try:
        payload = decode_token(raw_token, expected_type="refresh")
    except Exception as exc:   # noqa: BLE001 - any decode failure is a 401
        raise AuthError("Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.") from exc

    stored = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
    ).scalar_one_or_none()

    if stored is None:
        raise AuthError("Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.")

    if stored.revoked_at is not None:
        revoke_all_for_user(db, stored.user_id)
        raise AuthError(
            "Phát hiện phiên đăng nhập bị dùng lại. Tất cả phiên đã bị thu hồi, "
            "vui lòng đăng nhập lại."
        )

    if stored.expires_at <= datetime.now(UTC):
        raise AuthError("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")

    user = db.get(User, uuid.UUID(str(payload["sub"])))
    if user is None or not user.is_active:
        raise AuthError("Tài khoản không khả dụng.")

    stored.revoked_at = datetime.now(UTC)
    db.flush()

    access, refresh = issue_tokens(db, user, device_id=device_id or stored.device_id)
    return user, access, refresh


def revoke_refresh_token(db: Session, raw_token: str) -> bool:
    """Log out one session. Idempotent: revoking twice is not an error."""
    stored = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
    ).scalar_one_or_none()

    if stored is None or stored.revoked_at is not None:
        return False

    stored.revoked_at = datetime.now(UTC)
    db.flush()
    return True


def revoke_all_for_user(db: Session, user_id: uuid.UUID) -> int:
    """Revoke every live session for a user. Returns how many were revoked."""
    now = datetime.now(UTC)
    rows = db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    ).scalars().all()
    for row in rows:
        row.revoked_at = now
    db.flush()
    return len(rows)


def access_token_ttl_seconds() -> int:
    return settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
