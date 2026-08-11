"""Sync audit log -- server-only, never synced.

This table is how "sync latency" and "conflict rate" stop being adjectives in
the thesis report and become measured numbers (Issues #39, #48, #52).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import SyncDirection, SyncStatus, sql_in_list


class SyncSession(Base):
    __tablename__ = "sync_sessions"
    __table_args__ = (
        CheckConstraint(
            f"direction IN ({sql_in_list(SyncDirection.values())})", name="direction_valid"
        ),
        CheckConstraint(f"status IN ({sql_in_list(SyncStatus.values())})", name="status_valid"),
        Index("ix_sync_sessions_household_started", "household_id", text("started_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    device_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_pulled_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    records_pulled: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    records_pushed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # Losers of a last-write-wins comparison. A non-zero value here is the
    # signal that a real conflict happened in the field, which is precisely
    # the data Issue #40 needs.
    records_rejected: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    status: Mapped[str] = mapped_column(String(8), nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def duration_ms(self) -> int | None:
        if self.finished_at is None:
            return None
        return int((self.finished_at - self.started_at).total_seconds() * 1000)
