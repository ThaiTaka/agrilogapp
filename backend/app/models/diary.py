"""Farming diary entries -- the core of the app."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SyncMixin, local_day_expr
from app.models.enums import WorkType, sql_in_list

if TYPE_CHECKING:  # forward refs; resolved at mapper-configuration time
    from app.models.inventory import StockTransaction
    from app.models.season import Season


class DiaryEntry(Base, SyncMixin):
    """One logged piece of field work: bón phân, phun thuốc, thu hoạch...

    Supply consumption is deliberately NOT stored on this table. It lives in
    `stock_transactions` rows pointing back via `diary_entry_id`. The mobile
    form presents them as one screen; the data model keeps them as a parent
    plus ledger children, which is what makes the stock-restore operation
    (Issue #25/#26) well defined.
    """

    __tablename__ = "diary_entries"

    __extra_table_args__ = (
        CheckConstraint(
            f"work_type IN ({sql_in_list(WorkType.values())})", name="work_type_valid"
        ),
        CheckConstraint("labor_hours IS NULL OR labor_hours >= 0", name="labor_hours_valid"),
        CheckConstraint("title IS NULL OR length(title) <= 160", name="title_length"),
        Index(
            "ix_diary_season_date",
            "season_id",
            text("entry_date DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_diary_worktype",
            "household_id",
            "work_type",
            text("entry_date DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    season_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("seasons.id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"),
        nullable=False,
    )
    work_type: Mapped[str] = mapped_column(String(24), nullable=False)

    entry_date: Mapped[int] = mapped_column(BigInteger, nullable=False)
    entry_day_local: Mapped[int] = mapped_column(
        Integer, Computed(local_day_expr("entry_date"), persisted=True), nullable=False
    )

    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    weather: Mapped[str | None] = mapped_column(String(32), nullable=True)
    labor_hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)

    season: Mapped["Season"] = relationship(back_populates="diary_entries")
    stock_transactions: Mapped[list["StockTransaction"]] = relationship(
        back_populates="diary_entry", passive_deletes=True
    )
