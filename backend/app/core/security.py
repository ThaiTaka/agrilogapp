"""Password hashing and JWT issue/verify.

bcrypt is called directly rather than through passlib (see requirements.txt for
why). PyJWT is used rather than python-jose, which has been effectively
unmaintained since 2021.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings

UTC = timezone.utc  # `datetime.UTC` is 3.11+; this keeps the stated 3.10 floor

# bcrypt silently truncates anything past 72 bytes. Silent truncation means
# two different long passwords can authenticate each other, so it is rejected
# rather than absorbed.
BCRYPT_MAX_BYTES = 72
BCRYPT_ROUNDS = 12

TokenType = Literal["access", "refresh"]


class TokenError(Exception):
    """Raised when a token is malformed, expired, or of the wrong type."""


# ═══════════════════════════════════════════════════════════════════════════
#  Passwords
# ═══════════════════════════════════════════════════════════════════════════


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_BYTES:
        raise ValueError(
            f"Password exceeds bcrypt's {BCRYPT_MAX_BYTES}-byte limit "
            f"(got {len(encoded)} bytes). Note that Vietnamese diacritics cost "
            "2-3 bytes per character in UTF-8."
        )
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(encoded, password_hash.encode("utf-8"))
    except ValueError:
        # Malformed hash in the database — treat as a failed login, never a 500.
        return False


# ═══════════════════════════════════════════════════════════════════════════
#  JWT
# ═══════════════════════════════════════════════════════════════════════════


def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "typ": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(
    user_id: str | uuid.UUID,
    household_id: str | uuid.UUID,
    expires_minutes: int | None = None,
) -> str:
    """Issue an access token.

    `household_id` is embedded so that every request can be scoped to a
    household without a database round-trip, and — more importantly — so the
    sync endpoints derive the tenant from the token rather than from the
    payload. A client cannot write into another household by forging a field
    that is never read.
    """
    minutes = expires_minutes if expires_minutes is not None else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    return _create_token(
        subject=str(user_id),
        token_type="access",
        expires_delta=timedelta(minutes=minutes),
        extra_claims={"hid": str(household_id)},
    )


def create_refresh_token(user_id: str | uuid.UUID) -> tuple[str, str, datetime]:
    """Issue a refresh token.

    Returns ``(raw_token, sha256_hash, expires_at)``. Only the hash is stored,
    so a database leak does not hand out working sessions.
    """
    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    raw = _create_token(
        subject=str(user_id),
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return raw, hash_token(raw), expires_at


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except InvalidTokenError as exc:
        raise TokenError(str(exc)) from exc

    if expected_type is not None and payload.get("typ") != expected_type:
        # Without this check a refresh token would be accepted as an access
        # token, quietly turning a 90-day credential into a 90-day session.
        raise TokenError(
            f"Expected a '{expected_type}' token, got '{payload.get('typ')}'"
        )
    return payload


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_device_id() -> str:
    """Fallback device identifier when a client omits the X-Device-Id header."""
    return secrets.token_hex(16)
