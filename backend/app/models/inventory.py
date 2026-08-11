"""Supplies and the append-only stock ledger."""

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
from app.models.enums import SupplyCategory, TxnType, sql_in_list

if TYPE_CHECKING:  # forward refs; resolved at mapper-configuration time
    from app.models.diary import DiaryEntry
    from app.models.finance import Expense
    from app.models.season import Season


class Supply(Base, SyncMixin):
    """An agricultural input the household keeps in stock.

    NOTE the column that is deliberately absent: `current_stock`.

    On-hand quantity is never stored. It is always derived from the ledger:
        SUM(in) + SUM(adjust) - SUM(out)

    A stored counter has to be mutated by the server *and* by every offline
    device. Two devices each decrementing a cached counter while offline
    produce a number that is simply wrong after sync, with no way to detect
    it. Deriving from an append-only ledger means those two devices contribute
    two independent rows, both sync cleanly, and the total is correct by
    construction. This is the central data-modelling decision of the inventory
    module (Data_Requirements_Database.md D1).
    """

    __tablename__ = "supplies"

    __extra_table_args__ = (
        CheckConstraint(
            f"category IN ({sql_in_list(SupplyCategory.values())})", name="category_valid"
        ),
        CheckConstraint("unit_cost >= 0", name="unit_cost_non_negative"),
        CheckConstraint("low_stock_threshold >= 0", name="low_stock_non_negative"),
        CheckConstraint("length(name) BETWEEN 1 AND 120", name="name_length"),
        # Stops "Đạm Urê" becoming two inventory lines on one device. It is
        # NOT bulletproof across a network partition -- two offline devices can
        # each create it and both will sync. That case is resolved manually;
        # see Data_Requirements_Database.md section 8.3 / D5.
        Index(
            "uq_supply_name_unit",
            "household_id",
            text("lower(name)"),
            "unit",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_supplies_household_cat",
            "household_id",
            "category",
            "name",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    # Current reference price, VND per `unit`. Snapshotted onto each
    # transaction at movement time -- see StockTransaction.unit_cost.
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, server_default=text("0")
    )
    low_stock_threshold: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, server_default=text("0")
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    transactions: Mapped[list["StockTransaction"]] = relationship(
        back_populates="supply", passive_deletes=True
    )


class StockTransaction(Base, SyncMixin):
    """One movement in the inventory ledger.

    `diary_entry_id` is what unifies "supply consumption logged from a diary
    entry" and "stock-out recorded from the inventory screen" into a single
    ledger, rather than a separate usage table that has to be kept consistent
    with it. That is what makes "hoàn kho" (Issues #25, #26) a bounded,
    testable operation: reconcile the set of child rows for one parent.
    """

    __tablename__ = "stock_transactions"

    __extra_table_args__ = (
        CheckConstraint(f"txn_type IN ({sql_in_list(TxnType.values())})", name="txn_type_valid"),
        # `in` and `out` carry a positive magnitude and take their direction
        # from txn_type. `adjust` is a stock-take correction and may go either
        # way, but must not be a no-op.
        CheckConstraint(
            "(txn_type IN ('in','out') AND quantity > 0) "
            "OR (txn_type = 'adjust' AND quantity <> 0)",
            name="quantity_sign_valid",
        ),
        CheckConstraint("unit_cost >= 0", name="unit_cost_non_negative"),
        CheckConstraint("total_cost >= 0", name="total_cost_non_negative"),
        Index(
            "ix_stock_supply_date",
            "supply_id",
            text("txn_date DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_stock_diary",
            "diary_entry_id",
            postgresql_where=text("deleted_at IS NULL AND diary_entry_id IS NOT NULL"),
        ),
        Index(
            "ix_stock_season_type",
            "season_id",
            "txn_type",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    # DEFERRABLE: a single sync batch can contain a transaction whose diary
    # entry is in the same batch. Ordering handles the common case; deferring
    # the check to COMMIT means the batch is validated as a whole, which is the
    # correct semantics since the batch *is* the unit of atomicity.
    supply_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supplies.id", ondelete="RESTRICT", deferrable=True, initially="DEFERRED"),
        nullable=False,
    )
    season_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("seasons.id", ondelete="SET NULL", deferrable=True, initially="DEFERRED"),
        nullable=True,
    )
    diary_entry_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("diary_entries.id", ondelete="SET NULL", deferrable=True, initially="DEFERRED"),
        nullable=True,
    )

    txn_type: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)

    # Snapshot of supplies.unit_cost at movement time, NOT a live join.
    # Fertiliser bought in March at 12,000đ/kg and used in September must be
    # costed at what it actually cost. Joining live would silently rewrite the
    # financial history of every past season each time a price is updated.
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, server_default=text("0")
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, server_default=text("0")
    )

    txn_date: Mapped[int] = mapped_column(BigInteger, nullable=False)
    txn_day_local: Mapped[int] = mapped_column(
        Integer, Computed(local_day_expr("txn_date"), persisted=True), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    supply: Mapped["Supply"] = relationship(back_populates="transactions")
    season: Mapped[Optional["Season"]] = relationship(back_populates="stock_transactions")
    diary_entry: Mapped[Optional["DiaryEntry"]] = relationship(
        back_populates="stock_transactions"
    )
    expense: Mapped[Optional["Expense"]] = relationship(
        back_populates="stock_transaction", uselist=False
    )

    @property
    def signed_quantity(self) -> Decimal:
        """Effect on inventory: positive adds, negative removes."""
        if self.txn_type == TxnType.OUT:
            return -self.quantity
        return self.quantity
