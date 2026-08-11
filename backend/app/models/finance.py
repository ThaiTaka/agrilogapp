"""Expenses and revenues -- the money side of a season."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

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
from app.models.enums import ExpenseCategory, ExpenseSource, sql_in_list

if TYPE_CHECKING:  # forward refs; resolved at mapper-configuration time
    from app.models.inventory import StockTransaction
    from app.models.season import Season


class Expense(Base, SyncMixin):
    """A cost attributed to a season.

    Rows with `source = 'diary_auto'` are generated from supply consumption
    and are READ-ONLY in the UI. Letting a farmer hand-edit a derived number
    would make the generator and the stored value diverge, with no way to
    reconcile them at sync time (Data_Requirements_Database.md D7).
    """

    __tablename__ = "expenses"

    __extra_table_args__ = (
        CheckConstraint(
            f"category IN ({sql_in_list(ExpenseCategory.values())})", name="category_valid"
        ),
        CheckConstraint(
            f"source IN ({sql_in_list(ExpenseSource.values())})", name="source_valid"
        ),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        # The two fields cannot disagree about where this expense came from.
        CheckConstraint(
            "(source = 'diary_auto') = (stock_transaction_id IS NOT NULL)",
            name="source_matches_link",
        ),
        # THE idempotency guarantee for Issue #29. A sync retry cannot
        # double-count the farmer's costs, because the database refuses the
        # second row -- the invariant holds even against a buggy service layer.
        Index(
            "uq_expense_per_stock_txn",
            "stock_transaction_id",
            unique=True,
            postgresql_where=text("stock_transaction_id IS NOT NULL"),
        ),
        Index(
            "ix_expenses_season_date",
            "season_id",
            "expense_date",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    season_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("seasons.id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"),
        nullable=False,
    )
    stock_transaction_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "stock_transactions.id",
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=True,
    )

    category: Mapped[str] = mapped_column(String(24), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)

    expense_date: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expense_day_local: Mapped[int] = mapped_column(
        Integer, Computed(local_day_expr("expense_date"), persisted=True), nullable=False
    )

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'manual'")
    )

    season: Mapped["Season"] = relationship(back_populates="expenses")
    stock_transaction: Mapped[Optional["StockTransaction"]] = relationship(
        back_populates="expense"
    )

    @property
    def is_auto_generated(self) -> bool:
        return self.source == ExpenseSource.DIARY_AUTO


class Revenue(Base, SyncMixin):
    """Income from selling harvest.

    `amount` is authoritative and always stored, even when quantity and
    unit_price are also present. The UI pre-fills amount from the product but
    lets the farmer override it -- real sales get rounded, discounted, or
    partially paid. Deriving amount on read would silently discard that.
    """

    __tablename__ = "revenues"

    __extra_table_args__ = (
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        CheckConstraint("quantity IS NULL OR quantity >= 0", name="quantity_non_negative"),
        CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="unit_price_non_negative"),
        Index(
            "ix_revenues_season_date",
            "season_id",
            "revenue_date",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    season_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("seasons.id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"),
        nullable=False,
    )

    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)

    revenue_date: Mapped[int] = mapped_column(BigInteger, nullable=False)
    revenue_day_local: Mapped[int] = mapped_column(
        Integer, Computed(local_day_expr("revenue_date"), persisted=True), nullable=False
    )

    buyer: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    season: Mapped["Season"] = relationship(back_populates="revenues")
