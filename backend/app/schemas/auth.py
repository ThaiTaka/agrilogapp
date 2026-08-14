"""Authentication request/response schemas (Issue #14)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import BCRYPT_MAX_BYTES

MIN_PASSWORD_LENGTH = 8


def _validate_password(value: str) -> str:
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự")
    encoded = len(value.encode("utf-8"))
    if encoded > BCRYPT_MAX_BYTES:
        # Rejected rather than truncated: bcrypt silently ignores everything
        # past 72 bytes, which would let two different long passwords
        # authenticate each other. Vietnamese diacritics cost 2-3 bytes each,
        # so a 40-character password can trip this.
        raise ValueError(
            f"Mật khẩu quá dài ({encoded} byte, tối đa {BCRYPT_MAX_BYTES}). "
            "Lưu ý dấu tiếng Việt chiếm 2-3 byte mỗi ký tự."
        )
    return value


# ═══════════════════════════════════════════════════════════════════════════
#  Requests
# ═══════════════════════════════════════════════════════════════════════════


class RegisterRequest(BaseModel):
    """Creates a household and its first user in one step.

    A user without a household is meaningless in this system -- every synced
    row is household-scoped (rule R4) -- so the two are never created
    separately.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
    full_name: str = Field(min_length=1, max_length=120)
    household_name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    province: str | None = Field(default=None, max_length=80)
    commune: str | None = Field(default=None, max_length=80)

    _check_password = field_validator("password")(_validate_password)


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


# ═══════════════════════════════════════════════════════════════════════════
#  Responses
# ═══════════════════════════════════════════════════════════════════════════


class HouseholdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str | None = None
    province: str | None = None
    commune: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    # The caller's OWN flag, so it discloses nothing about anyone else. The web
    # dashboard reads it to avoid signing someone in to a console where every
    # panel would 403. It is NOT the access check: that stays server-side in
    # `get_current_admin`, on every request, against the live database row.
    is_admin: bool = False


class TokenPair(BaseModel):
    """Login/register/refresh response.

    `user` and `household` are embedded deliberately. The mobile client needs
    both immediately after login, and on a rural connection every avoided
    round-trip is a request that cannot fail halfway.
    """

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")
    user: UserOut
    household: HouseholdOut
