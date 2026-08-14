"""Web Admin Dashboard schemas (Phase 2, Bước 0)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ═══════════════════════════════════════════════════════════════════════════
#  Users
# ═══════════════════════════════════════════════════════════════════════════


class AdminUserOut(BaseModel):
    """A user as an administrator sees them.

    Carries `household_name` alongside the id because the dashboard's user
    table shows it in every row, and resolving it client-side would be one
    request per row.

    `password_hash` is absent, as it is from every schema in this file. That
    is not an oversight to be corrected later: an admin listing is precisely
    the endpoint where a leaked hash would be most valuable.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_admin: bool
    household_id: uuid.UUID
    household_name: str
    created_at: datetime


class AdminUserUpdate(BaseModel):
    """Lock or unlock an account.

    Only `is_active`. `is_admin` is deliberately NOT here — see
    models/account.py — and neither are email, name or password: this endpoint
    exists to suspend an account, not to become a second, weaker account-editing
    surface next to /auth.
    """

    is_active: bool


# ═══════════════════════════════════════════════════════════════════════════
#  Households
# ═══════════════════════════════════════════════════════════════════════════


class AdminHouseholdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str | None = None
    province: str | None = None
    commune: str | None = None
    user_count: int = Field(description="Số tài khoản thuộc nông hộ này")
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
#  Overview
# ═══════════════════════════════════════════════════════════════════════════


class AdminOverview(BaseModel):
    """Headline counts for the dashboard landing page.

    Deliberately not built on /reports/*, which is scoped to one household and
    answers a farmer's questions ("am I making money on this season?"). These
    are an operator's questions ("how many households are actually using it?"),
    and reusing the household-scoped reducers would have meant either removing
    their scope — the single most dangerous edit possible in this codebase — or
    calling them once per household.
    """

    total_households: int
    total_users: int
    active_users: int
    locked_users: int
    total_seasons: int
    total_diary_entries: int
    # Row counts alone cannot distinguish a live system from a dead one that
    # was busy in March, so recent activity is reported separately.
    diary_entries_last_7_days: int
    new_users_last_30_days: int
    maintenance_enabled: bool


# ═══════════════════════════════════════════════════════════════════════════
#  Maintenance
# ═══════════════════════════════════════════════════════════════════════════


class MaintenanceStatus(BaseModel):
    """Also served unauthenticated at /api/v1/maintenance for the mobile app."""

    model_config = ConfigDict(from_attributes=True)

    maintenance_enabled: bool
    maintenance_message: str | None = None


class MaintenanceUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    maintenance_enabled: bool
    maintenance_message: str | None = Field(default=None, max_length=500)
