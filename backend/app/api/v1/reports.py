"""Report endpoints for the three required charts (Issue #42).

    GET /api/v1/reports/income-expense?season_id=&granularity=
    GET /api/v1/reports/supply-consumption?season_id=&group_by=
    GET /api/v1/reports/season-comparison?limit=&status=

These exist alongside the client's own local computation, not instead of it.
The mobile app renders all three from WatermelonDB while offline (Issue #47);
these endpoints are the cross-check and the future web view. A shared golden
fixture asserts both sides produce identical numbers (§11.4), because "the
chart shows the same thing online and offline" has to be a tested property
rather than an aspiration.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DbSession, HouseholdId
from app.models.enums import SeasonStatus
from app.schemas.report import (
    Granularity,
    GroupBy,
    IncomeExpenseReport,
    SeasonComparisonReport,
    SupplyConsumptionReport,
)
from app.services import report_service
from app.services.errors import NotFound

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "/income-expense",
    response_model=IncomeExpenseReport,
    summary="Biểu đồ 1 — Thu chi theo thời gian",
)
def income_expense(
    db: DbSession,
    household_id: HouseholdId,
    season_id: Annotated[str, Query(description="Required — the chart is per season")],
    granularity: Annotated[Granularity, Query()] = Granularity.MONTH,
) -> IncomeExpenseReport:
    """*Am I spending faster than I'm earning this season?*

    Buckets are dense: a period with no activity is returned with zeros. A
    sparse series makes a line chart lie about the shape of spending — three
    quiet weeks then a large purchase would render as a gentle slope rather
    than a step.
    """
    try:
        return IncomeExpenseReport(
            **report_service.income_expense(
                db, household_id, season_id, granularity=granularity
            )
        )
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/supply-consumption",
    response_model=SupplyConsumptionReport,
    summary="Biểu đồ 2 — Vật tư tiêu thụ",
)
def supply_consumption(
    db: DbSession,
    household_id: HouseholdId,
    season_id: Annotated[str | None, Query(description="Omit for all seasons")] = None,
    group_by: Annotated[GroupBy, Query()] = GroupBy.CATEGORY,
) -> SupplyConsumptionReport:
    """*Which inputs are eating my budget?*

    Counts `out` movements only — a stock-in is a purchase, not consumption.

    When a group mixes units, `unit_mixed` is true and `unit` is null: summing
    kilograms and litres produces a number with no meaning, so the chart must
    plot **cost** in that case. This is why `total_cost` is the primary
    measure rather than quantity.
    """
    try:
        return SupplyConsumptionReport(
            **report_service.supply_consumption(
                db, household_id, season_id=season_id, group_by=group_by
            )
        )
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/season-comparison",
    response_model=SeasonComparisonReport,
    summary="Biểu đồ 3 — So sánh lợi nhuận giữa các mùa vụ",
)
def season_comparison(
    db: DbSession,
    household_id: HouseholdId,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    status: Annotated[SeasonStatus | None, Query()] = None,
) -> SeasonComparisonReport:
    """*Which season actually performed best?*

    Seasons with no records yet appear at zero rather than vanishing — a
    farmer comparing seasons needs to see the one they just started.
    Renders correctly with exactly one season (Issue #46).
    """
    return SeasonComparisonReport(
        **report_service.season_comparison(
            db, household_id, limit=limit, status=status.value if status else None
        )
    )
