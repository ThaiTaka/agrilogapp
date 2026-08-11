"""Crop season -- the organising unit for every other record."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SyncMixin
from app.models.enums import SeasonStatus, sql_in_list

if TYPE_CHECKING:  # forward refs; resolved at mapper-configuration time
    from app.models.diary import DiaryEntry
    from app.models.finance import Expense, Revenue
    from app.models.inventory import StockTransaction


class Season(Base, SyncMixin):
    """e.g. "Vụ Đông Xuân 2026" -- rice, 5 sào, Dec 2026 to Apr 2027."""

    __tablename__ = "seasons"

    __extra_table_args__ = (
        CheckConstraint(
            f"status IN ({sql_in_list(SeasonStatus.values())})",
            name="status_valid",
        ),
        # Enforced in three layers -- table, Pydantic, and the mobile form.
        # A bad range silently breaks every report that filters by the season
        # window, and a silent report bug is far more expensive to find than a
        # loud validation error.
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="date_range_valid",
        ),
        CheckConstraint("area_size IS NULL OR area_size >= 0", name="area_non_negative"),
        CheckConstraint("length(name) BETWEEN 1 AND 120", name="name_length"),
        CheckConstraint("length(crop_type) BETWEEN 1 AND 80", name="crop_type_length"),
        Index(
            "ix_seasons_household_start",
            "household_id",
            text("start_date DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    crop_type: Mapped[str] = mapped_column(Text, nullable=False)
    area_size: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    area_unit: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'sao'"))

    start_date: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # NULL means the season is still running -- the farmer has not yet decided
    # when it ends, which is normal mid-season.
    end_date: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'active'")
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    diary_entries: Mapped[list["DiaryEntry"]] = relationship(
        back_populates="season", passive_deletes=True
    )
    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="season", passive_deletes=True
    )
    revenues: Mapped[list["Revenue"]] = relationship(
        back_populates="season", passive_deletes=True
    )
    stock_transactions: Mapped[list["StockTransaction"]] = relationship(
        back_populates="season", passive_deletes=True
    )
