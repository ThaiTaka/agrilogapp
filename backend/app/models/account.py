"""Server-only account tables: Household, User, RefreshToken.

These never cross the sync boundary. A household is created at registration,
which is inherently an online operation, so its ID is server-generated.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Household(Base, TimestampMixin):
    """The tenant. Every synced row in the system hangs off exactly one."""

    __tablename__ = "households"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    province: Mapped[str | None] = mapped_column(Text, nullable=True)
    commune: Mapped[str | None] = mapped_column(Text, nullable=True)

    users: Mapped[list[User]] = relationship(
        back_populates="household", cascade="all, delete-orphan", lazy="selectin"
    )


class User(Base, TimestampMixin):
    """A login account.

    More than one user may belong to a household -- a farmer and an adult child
    logging work from separate phones. That is exactly the scenario the
    two-device conflict test (Issue #40) exercises, so the schema permits it
    from day one.
    """

    __tablename__ = "users"
    __table_args__ = (
        # Case-insensitive uniqueness without depending on the citext
        # extension. Emails are also lowercased by the auth service before
        # insert, so the index and the stored value always agree.
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    # bcrypt cost 12. Never serialised — no Pydantic response schema exposes it.
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    # Grants access to /admin/*, which is the ONE part of this API that is not
    # scoped to a household. It is deliberately not settable through any
    # endpoint -- not registration, not the admin user PATCH -- because an
    # endpoint that can grant this is an endpoint that can be tricked into
    # granting it. Promotion happens out of band: scripts/make_admin.py.
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    household: Mapped[Household] = relationship(back_populates="users")
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    """A revocable, long-lived credential.

    Only the SHA-256 hash is stored, so a database leak does not hand out
    working sessions. 90-day lifetime: a device that has been in a field with
    no signal for three weeks must still be able to sync when it reconnects,
    rather than bouncing the farmer to a login screen while holding three
    weeks of unsynced work.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_active", "user_id", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    device_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")

    @property
    def is_usable(self) -> bool:
        from app.core.timeutils import UTC

        return self.revoked_at is None and self.expires_at > datetime.now(UTC)
