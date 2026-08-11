"""Report schemas for the three required charts (Issue #42).

The three questions a farmer actually asks, from the proposal's §3
("trực quan hóa thu chi và vật tư tiêu thụ qua 3 biểu đồ"):

  1. Am I spending faster than I'm earning this season?
  2. Which inputs are eating my budget?
  3. Which season actually performed best?
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

from app.models.enums import SeasonStatus, SupplyCategory


class Granularity(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class GroupBy(str, Enum):
    CATEGORY = "category"
    SUPPLY = "supply"


# ═══════════════════════════════════════════════════════════════════════════
#  1. Income vs Expense over time
# ═══════════════════════════════════════════════════════════════════════════


class IncomeExpenseBucket(BaseModel):
    period: str = Field(description="'2026-09-12' | '2026-W37' | '2026-09'")
    revenue: Decimal
    expense: Decimal
    profit: Decimal


class IncomeExpenseTotals(BaseModel):
    revenue: Decimal
    expense: Decimal
    profit: Decimal


class IncomeExpenseReport(BaseModel):
    """Time series for the season, with DENSE buckets.

    A period with no activity is emitted with zeros rather than omitted. A
    sparse series makes a line chart lie about the shape of spending — three
    quiet weeks followed by a large purchase would render as a gentle slope
    instead of a step.
    """

    season_id: str
    season_name: str
    granularity: Granularity
    buckets: list[IncomeExpenseBucket]
    totals: IncomeExpenseTotals


# ═══════════════════════════════════════════════════════════════════════════
#  2. Supply consumption
# ═══════════════════════════════════════════════════════════════════════════


class SupplyConsumptionItem(BaseModel):
    key: str = Field(description="Category value, or supply id when grouped by supply")
    label: str
    quantity: Decimal
    unit: str | None = Field(
        default=None, description="Null when the group mixes units — see unit_mixed"
    )
    unit_mixed: bool = Field(
        default=False,
        description=(
            "True when the group sums more than one unit. The chart must then "
            "plot cost, not quantity: adding kilograms to litres is meaningless."
        ),
    )
    total_cost: Decimal
    share_pct: Decimal
    transaction_count: int


class SupplyConsumptionReport(BaseModel):
    season_id: str | None
    season_name: str | None
    group_by: GroupBy
    items: list[SupplyConsumptionItem]
    total_cost: Decimal


# ═══════════════════════════════════════════════════════════════════════════
#  3. Season comparison
# ═══════════════════════════════════════════════════════════════════════════


class SeasonComparisonItem(BaseModel):
    season_id: str
    name: str
    crop_type: str
    status: SeasonStatus
    start_date: int
    end_date: int | None
    revenue: Decimal
    expense: Decimal
    profit: Decimal
    margin_pct: Decimal | None


class SeasonComparisonReport(BaseModel):
    seasons: list[SeasonComparisonItem]
    best_season_id: str | None = Field(
        default=None, description="Highest profit; null when there are no seasons"
    )
    worst_season_id: str | None = None


__all__ = [
    "Granularity",
    "GroupBy",
    "IncomeExpenseBucket",
    "IncomeExpenseReport",
    "IncomeExpenseTotals",
    "SeasonComparisonItem",
    "SeasonComparisonReport",
    "SupplyCategory",
    "SupplyConsumptionItem",
    "SupplyConsumptionReport",
]
