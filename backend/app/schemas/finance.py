"""Expense, revenue and season-summary schemas (Issue #27)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    EXPENSE_CATEGORY_LABELS_VI,
    SEASON_STATUS_LABELS_VI,
    ExpenseCategory,
    ExpenseSource,
    SeasonStatus,
)

REVENUE_UNITS = ("kg", "tạ", "tấn", "bao", "thùng", "quả", "bó")


def _uuid_or_none(v: str | None) -> str | None:
    if v is None:
        return None
    try:
        return str(uuid.UUID(v))
    except ValueError as exc:
        raise ValueError("id phải là UUID hợp lệ") from exc


# ═══════════════════════════════════════════════════════════════════════════
#  Expense
# ═══════════════════════════════════════════════════════════════════════════


class ExpenseCreate(BaseModel):
    """A manually recorded cost.

    `source` is not accepted from the client. Only the diary→expense generator
    may produce `diary_auto` rows; letting a caller claim that source would
    create a cost with no movement behind it, which then cannot be reconciled
    when the entry it pretends to belong to is edited.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str | None = Field(default=None, max_length=36)
    category: ExpenseCategory = ExpenseCategory.OTHER
    amount: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    expense_date: int | None = Field(default=None, description="Epoch ms; defaults to now")
    description: str | None = None
    created_at: int | None = None
    updated_at: int | None = None

    _check_id = field_validator("id")(_uuid_or_none)


class ExpenseUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category: ExpenseCategory | None = None
    amount: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    expense_date: int | None = None
    description: str | None = None
    season_id: str | None = Field(default=None, max_length=36)
    updated_at: int | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    season_id: str
    category: ExpenseCategory
    category_label: str = ""
    amount: Decimal
    expense_date: int
    description: str | None
    source: ExpenseSource
    stock_transaction_id: str | None
    created_at: int
    updated_at: int

    is_editable: bool = Field(
        default=True,
        description=(
            "False for diary_auto rows. They are derived from supply "
            "consumption and are changed by editing the diary entry."
        ),
    )

    @model_validator(mode="after")
    def _derive(self):
        if not self.category_label:
            self.category_label = EXPENSE_CATEGORY_LABELS_VI.get(
                self.category, self.category.value
            )
        self.is_editable = self.source != ExpenseSource.DIARY_AUTO
        return self


# ═══════════════════════════════════════════════════════════════════════════
#  Revenue
# ═══════════════════════════════════════════════════════════════════════════


class RevenueCreate(BaseModel):
    """Income from selling harvest.

    `amount` is authoritative. It can be omitted when both `quantity` and
    `unit_price` are given, in which case the product is used — but a supplied
    `amount` always wins. Real sales get rounded down, discounted for
    moisture, or partially paid, and deriving the total on read would
    silently discard the number the farmer actually received.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str | None = Field(default=None, max_length=36)
    quantity: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    unit: str | None = Field(default=None, max_length=16)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    revenue_date: int | None = None
    buyer: str | None = None
    description: str | None = None
    created_at: int | None = None
    updated_at: int | None = None

    _check_id = field_validator("id")(_uuid_or_none)

    @field_validator("unit")
    @classmethod
    def _known_unit(cls, v: str | None) -> str | None:
        if v is not None and v not in REVENUE_UNITS:
            raise ValueError(f"Đơn vị phải là một trong: {', '.join(REVENUE_UNITS)}")
        return v

    @model_validator(mode="after")
    def _resolve_amount(self):
        if self.amount is None:
            if self.quantity is None or self.unit_price is None:
                raise ValueError(
                    "Cần nhập 'amount', hoặc cả 'quantity' và 'unit_price' để tính ra nó."
                )
            self.amount = self.quantity * self.unit_price
        return self


class RevenueUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    quantity: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    unit: str | None = Field(default=None, max_length=16)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    revenue_date: int | None = None
    buyer: str | None = None
    description: str | None = None
    season_id: str | None = Field(default=None, max_length=36)
    updated_at: int | None = None

    @field_validator("unit")
    @classmethod
    def _known_unit(cls, v: str | None) -> str | None:
        if v is not None and v not in REVENUE_UNITS:
            raise ValueError(f"Đơn vị phải là một trong: {', '.join(REVENUE_UNITS)}")
        return v


class RevenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    season_id: str
    quantity: Decimal | None
    unit: str | None
    unit_price: Decimal | None
    amount: Decimal
    revenue_date: int
    buyer: str | None
    description: str | None
    created_at: int
    updated_at: int


# ═══════════════════════════════════════════════════════════════════════════
#  Season summary
# ═══════════════════════════════════════════════════════════════════════════


class CategoryBreakdown(BaseModel):
    category: ExpenseCategory
    label: str
    amount: Decimal
    share_pct: Decimal = Field(description="Percentage of total cost, 1 dp")


class SeasonSummary(BaseModel):
    """Cost, revenue and profit for one season.

    `profit` is computed, never stored (invariant I10). Storing it would need
    invalidation on every one of the many writes that can affect it, across
    two databases, one of which is frequently offline.
    """

    season_id: str
    season_name: str
    crop_type: str
    status: SeasonStatus
    status_label: str = ""
    start_date: int
    end_date: int | None

    total_cost: Decimal
    total_revenue: Decimal
    profit: Decimal
    margin_pct: Decimal | None = Field(
        default=None,
        description="profit / revenue as a percentage; null when there is no revenue yet",
    )

    expense_count: int
    revenue_count: int

    # Split out because the two behave differently for the farmer: manual
    # costs are things they chose to record, auto costs appeared by
    # themselves from the diary. Seeing the split is how they learn to trust
    # the automatic half.
    auto_generated_cost: Decimal
    manual_cost: Decimal

    cost_by_category: list[CategoryBreakdown] = Field(default_factory=list)

    @model_validator(mode="after")
    def _label(self):
        if not self.status_label:
            self.status_label = SEASON_STATUS_LABELS_VI.get(self.status, self.status.value)
        return self
