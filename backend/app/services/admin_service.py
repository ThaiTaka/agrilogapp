"""Administration queries — the one part of the system that is not
household-scoped.

Every other service takes a `household_id` and filters by it. These
deliberately do not, which is why the routes above them sit behind
`get_current_admin` and why that check reads the database rather than a token
claim.

Soft-deleted rows are excluded everywhere a count is produced. A dashboard
that counts tombstones reports a system busier than it is, and the number
would drift further from reality with every deletion.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.timeutils import UTC
from app.models import AppSetting, DiaryEntry, Household, Season, User
from app.services.errors import NotFound, ValidationFailed


def _now():
    from datetime import datetime

    return datetime.now(UTC)


# ═══════════════════════════════════════════════════════════════════════════
#  Settings
# ═══════════════════════════════════════════════════════════════════════════


def get_settings(db: Session) -> AppSetting:
    """The single settings row.

    Migration 0003 inserts it, so a missing row means the database was built
    some other way. Raising beats silently inventing defaults: a maintenance
    flag that reads "off" because the row vanished is exactly the failure the
    flag exists to prevent.
    """
    row = db.get(AppSetting, 1)
    if row is None:
        raise NotFound(
            "Chưa có bản ghi cấu hình hệ thống (app_settings id=1). "
            "Hãy chạy `alembic upgrade head`."
        )
    return row


def set_maintenance(
    db: Session, *, enabled: bool, message: str | None = None
) -> AppSetting:
    row = get_settings(db)
    row.maintenance_enabled = enabled
    row.maintenance_message = (message or None) if enabled else None
    db.flush()
    return row


# ═══════════════════════════════════════════════════════════════════════════
#  Users
# ═══════════════════════════════════════════════════════════════════════════


def list_users(
    db: Session,
    *,
    search: str | None = None,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Users across every household, newest first.

    Returns dicts rather than ORM objects because the row the dashboard wants
    is a join of user and household, which is not any single mapped entity.
    """
    base = select(User, Household.name.label("household_name")).join(
        Household, User.household_id == Household.id
    )
    count_q = select(func.count()).select_from(User).join(
        Household, User.household_id == Household.id
    )

    if search:
        # Case-insensitive on both columns: an operator looking someone up has
        # either their email or their name, and rarely the exact casing.
        needle = f"%{search.strip().lower()}%"
        clause = or_(
            func.lower(User.email).like(needle),
            func.lower(User.full_name).like(needle),
            func.lower(Household.name).like(needle),
        )
        base = base.where(clause)
        count_q = count_q.where(clause)

    if is_active is not None:
        base = base.where(User.is_active == is_active)
        count_q = count_q.where(User.is_active == is_active)

    total = db.execute(count_q).scalar_one()
    rows = db.execute(
        base.order_by(User.created_at.desc()).limit(limit).offset(offset)
    ).all()

    return (
        [
            {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "is_admin": user.is_admin,
                "household_id": user.household_id,
                "household_name": household_name,
                "created_at": user.created_at,
            }
            for user, household_name in rows
        ],
        total,
    )


def set_user_active(
    db: Session, user_id: uuid.UUID, *, is_active: bool, acting_admin: User
) -> dict:
    """Lock or unlock an account.

    Two refusals, both about not letting an operator strand the system:

      * locking yourself out — the request would succeed and the next one
        would 403, with no way back through the UI;
      * locking the last admin — nobody could unlock anyone afterwards, and
        recovery would mean editing PostgreSQL by hand.

    Locking takes effect immediately rather than at token expiry: login,
    refresh and `get_current_user` all read `is_active` on the live row.
    """
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("Không tìm thấy tài khoản.")

    if not is_active:
        if user.id == acting_admin.id:
            raise ValidationFailed(
                "Không thể tự khoá tài khoản của chính mình — sẽ không đăng nhập lại được."
            )
        if user.is_admin:
            remaining = db.execute(
                select(func.count())
                .select_from(User)
                .where(User.is_admin.is_(True), User.is_active.is_(True), User.id != user.id)
            ).scalar_one()
            if remaining == 0:
                raise ValidationFailed(
                    "Đây là tài khoản quản trị đang hoạt động cuối cùng. "
                    "Khoá nó thì không ai mở lại được nữa."
                )

    user.is_active = is_active
    db.flush()

    household_name = db.execute(
        select(Household.name).where(Household.id == user.household_id)
    ).scalar_one()

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "household_id": user.household_id,
        "household_name": household_name,
        "created_at": user.created_at,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Households
# ═══════════════════════════════════════════════════════════════════════════


def list_households(
    db: Session, *, search: str | None = None, limit: int = 50, offset: int = 0
) -> tuple[list[dict], int]:
    user_count = (
        select(func.count(User.id))
        .where(User.household_id == Household.id)
        .correlate(Household)
        .scalar_subquery()
    )

    base = select(Household, user_count.label("user_count"))
    count_q = select(func.count()).select_from(Household)

    if search:
        needle = f"%{search.strip().lower()}%"
        clause = func.lower(Household.name).like(needle)
        base = base.where(clause)
        count_q = count_q.where(clause)

    total = db.execute(count_q).scalar_one()
    rows = db.execute(
        base.order_by(Household.created_at.desc()).limit(limit).offset(offset)
    ).all()

    return (
        [
            {
                "id": h.id,
                "name": h.name,
                "phone": h.phone,
                "province": h.province,
                "commune": h.commune,
                "user_count": count,
                "created_at": h.created_at,
            }
            for h, count in rows
        ],
        total,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Overview
# ═══════════════════════════════════════════════════════════════════════════


def overview(db: Session) -> dict:
    now = _now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    def count(stmt) -> int:
        return db.execute(stmt).scalar_one()

    live_seasons = select(func.count()).select_from(Season).where(Season.deleted_at.is_(None))
    live_entries = (
        select(func.count()).select_from(DiaryEntry).where(DiaryEntry.deleted_at.is_(None))
    )

    return {
        "total_households": count(select(func.count()).select_from(Household)),
        "total_users": count(select(func.count()).select_from(User)),
        "active_users": count(
            select(func.count()).select_from(User).where(User.is_active.is_(True))
        ),
        "locked_users": count(
            select(func.count()).select_from(User).where(User.is_active.is_(False))
        ),
        "total_seasons": count(live_seasons),
        "total_diary_entries": count(live_entries),
        # `server_updated_at`, not the device clock: `updated_at` comes from a
        # phone whose time can be wrong by days, and a wrong clock would move
        # rows in and out of this window for reasons that have nothing to do
        # with when the work happened.
        "diary_entries_last_7_days": count(
            select(func.count())
            .select_from(DiaryEntry)
            .where(
                DiaryEntry.deleted_at.is_(None),
                DiaryEntry.server_updated_at >= week_ago,
            )
        ),
        "new_users_last_30_days": count(
            select(func.count()).select_from(User).where(User.created_at >= month_ago)
        ),
        "maintenance_enabled": get_settings(db).maintenance_enabled,
    }
