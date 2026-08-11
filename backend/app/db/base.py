"""Declarative base, naming conventions, and the SyncMixin.

Every table that crosses the sync boundary inherits `SyncMixin`, so the five
sync columns cannot drift apart between tables. See
Data_Requirements_Database.md section 6.1.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from app.core.timeutils import now_ms

# Explicit naming so Alembic autogenerate produces stable, diffable names
# instead of anonymous constraint identifiers that churn between runs.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        pk = getattr(self, "id", None)
        return f"<{type(self).__name__} id={pk!r}>"


def new_uuid_str() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    """Server-clock timestamps for tables that never leave the server."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SyncMixin:
    """The five columns every synced table carries, plus its household scope.

    Two clocks, two jobs (Data_Requirements_Database.md section 6.2):

      * `updated_at`        -- DEVICE clock, epoch ms. Drives last-write-wins.
      * `server_updated_at` -- SERVER clock. Drives the pull cursor, and is
                               maintained by a database TRIGGER, never by the
                               ORM. A write that escapes the ORM without
                               bumping the cursor becomes a row that is
                               permanently invisible to every device -- the
                               worst class of sync bug, because the data is
                               present and simply never arrives.
    """

    # R1: the ID is generated on the device, before the network is consulted.
    # The default here only serves server-originated rows (the seed script).
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid_str)

    @declared_attr
    @classmethod
    def household_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            PGUUID(as_uuid=True),
            ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        )

    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ms)
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=now_ms, onupdate=now_ms
    )

    server_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    last_device_id: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> tuple:
        # The sole index the pull query uses -- the hottest, most
        # latency-sensitive query in the system. Equality column first.
        base = (
            Index(
                f"ix_{cls.__tablename__}_sync",
                "household_id",
                "server_updated_at",
            ),
        )
        extra = getattr(cls, "__extra_table_args__", ())
        return (*extra, *base)

    # ─── Convenience ───────────────────────────────────────────────────────

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


def local_day_expr(date_column: str) -> str:
    """SQL for the immutable, indexable 'local calendar day' of an epoch-ms column.

    Vietnam is UTC+7 with no DST, so the local day is exact integer
    arithmetic -- which is what lets PostgreSQL accept it as a STORED
    generated column and index it. A `timezone()` call would be merely STABLE
    and therefore rejected. See Data_Requirements_Database.md section 7.2.
    """
    from app.core.config import settings

    return f"(({date_column} + {settings.APP_TZ_OFFSET_MS}) / 86400000)::INTEGER"


# Registry of every synced table, in dependency order. Both the push handler
# and the pull handler iterate this list, so adding a table in one place is
# enough. Deletes are applied in reverse.
# See Data_Requirements_Database.md section 8.1.
SYNC_TABLE_ORDER: tuple[str, ...] = (
    "seasons",
    "supplies",
    "diary_entries",
    "stock_transactions",
    "expenses",
    "revenues",
)
