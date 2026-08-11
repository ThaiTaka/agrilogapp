"""Income / expense endpoints and the season financial summary (Issue #27).

    GET/POST  /api/v1/seasons/{season_id}/expenses
    GET/POST  /api/v1/seasons/{season_id}/revenues
    GET       /api/v1/seasons/{season_id}/summary
    GET/PATCH/DELETE  /api/v1/expenses/{id}
    GET/PATCH/DELETE  /api/v1/revenues/{id}
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession, DeviceId, HouseholdId
from app.models.enums import EXPENSE_CATEGORY_LABELS_VI, ExpenseCategory, ExpenseSource
from app.schemas.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.schemas.finance import (
    CategoryBreakdown,
    ExpenseCreate,
    ExpenseOut,
    ExpenseUpdate,
    RevenueCreate,
    RevenueOut,
    RevenueUpdate,
    SeasonSummary,
)
from app.services import finance_service
from app.services.errors import Conflict, NotFound, ValidationFailed

season_router = APIRouter(prefix="/seasons/{season_id}", tags=["finance"])
router = APIRouter(tags=["finance"])

_STATUS = {NotFound: 404, Conflict: 409, ValidationFailed: 422}


def _http(exc: Exception) -> HTTPException:
    for kind, code in _STATUS.items():
        if isinstance(exc, kind):
            return HTTPException(status_code=code, detail=str(exc))
    raise exc


# ═══════════════════════════════════════════════════════════════════════════
#  Expenses
# ═══════════════════════════════════════════════════════════════════════════


@season_router.get("/expenses", response_model=Page[ExpenseOut], summary="Chi phí của mùa vụ")
def list_expenses_for_season(
    season_id: str,
    db: DbSession,
    household_id: HouseholdId,
    category: Annotated[ExpenseCategory | None, Query()] = None,
    source: Annotated[ExpenseSource | None, Query()] = None,
    date_from: Annotated[int | None, Query()] = None,
    date_to: Annotated[int | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ExpenseOut]:
    rows, total = finance_service.list_expenses(
        db,
        household_id,
        season_id=season_id,
        category=category,
        source=source,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return Page[ExpenseOut](
        items=[ExpenseOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@season_router.post(
    "/expenses",
    response_model=ExpenseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ghi khoản chi",
)
def create_expense(
    season_id: str,
    payload: ExpenseCreate,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
) -> ExpenseOut:
    """Records a manual cost.

    Supply costs are NOT entered here — they appear by themselves from the
    diary entry that consumed the supply. Entering them again would
    double-count (invariant I9).
    """
    try:
        expense = finance_service.create_expense(
            db, household_id, season_id, payload, device_id=device_id
        )
    except (NotFound, Conflict, ValidationFailed) as exc:
        raise _http(exc) from exc
    result = ExpenseOut.model_validate(expense)
    db.commit()
    return result


@router.get("/expenses", response_model=Page[ExpenseOut], summary="Chi phí (mọi mùa vụ)")
def list_expenses(
    db: DbSession,
    household_id: HouseholdId,
    season_id: Annotated[str | None, Query()] = None,
    category: Annotated[ExpenseCategory | None, Query()] = None,
    source: Annotated[ExpenseSource | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ExpenseOut]:
    rows, total = finance_service.list_expenses(
        db,
        household_id,
        season_id=season_id,
        category=category,
        source=source,
        limit=limit,
        offset=offset,
    )
    return Page[ExpenseOut](
        items=[ExpenseOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/expenses/{expense_id}", response_model=ExpenseOut, summary="Chi tiết khoản chi")
def get_expense(expense_id: str, db: DbSession, household_id: HouseholdId) -> ExpenseOut:
    try:
        return ExpenseOut.model_validate(
            finance_service.get_expense(db, household_id, expense_id)
        )
    except NotFound as exc:
        raise _http(exc) from exc


@router.patch("/expenses/{expense_id}", response_model=ExpenseOut, summary="Sửa khoản chi")
def update_expense(
    expense_id: str,
    payload: ExpenseUpdate,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
) -> ExpenseOut:
    """409 for `diary_auto` rows — edit the diary entry instead.

    A hand-edited derived value diverges from its generator with no
    reconciliation path: the next edit to the diary entry would either
    overwrite the correction or not, depending on ordering (D7).
    """
    try:
        expense = finance_service.update_expense(
            db, household_id, expense_id, payload, device_id=device_id
        )
    except (NotFound, Conflict, ValidationFailed) as exc:
        raise _http(exc) from exc
    result = ExpenseOut.model_validate(expense)
    db.commit()
    return result


@router.delete(
    "/expenses/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xoá khoản chi",
)
def delete_expense(
    expense_id: str, db: DbSession, household_id: HouseholdId, device_id: DeviceId
):
    try:
        finance_service.delete_expense(db, household_id, expense_id, device_id=device_id)
    except (NotFound, Conflict) as exc:
        raise _http(exc) from exc
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  Revenues
# ═══════════════════════════════════════════════════════════════════════════


@season_router.get("/revenues", response_model=Page[RevenueOut], summary="Doanh thu của mùa vụ")
def list_revenues_for_season(
    season_id: str,
    db: DbSession,
    household_id: HouseholdId,
    date_from: Annotated[int | None, Query()] = None,
    date_to: Annotated[int | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[RevenueOut]:
    rows, total = finance_service.list_revenues(
        db,
        household_id,
        season_id=season_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return Page[RevenueOut](
        items=[RevenueOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@season_router.post(
    "/revenues",
    response_model=RevenueOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ghi khoản thu",
)
def create_revenue(
    season_id: str,
    payload: RevenueCreate,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
) -> RevenueOut:
    try:
        revenue = finance_service.create_revenue(
            db, household_id, season_id, payload, device_id=device_id
        )
    except (NotFound, Conflict, ValidationFailed) as exc:
        raise _http(exc) from exc
    result = RevenueOut.model_validate(revenue)
    db.commit()
    return result


@router.get("/revenues", response_model=Page[RevenueOut], summary="Doanh thu (mọi mùa vụ)")
def list_revenues(
    db: DbSession,
    household_id: HouseholdId,
    season_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[RevenueOut]:
    rows, total = finance_service.list_revenues(
        db, household_id, season_id=season_id, limit=limit, offset=offset
    )
    return Page[RevenueOut](
        items=[RevenueOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/revenues/{revenue_id}", response_model=RevenueOut, summary="Chi tiết khoản thu")
def get_revenue(revenue_id: str, db: DbSession, household_id: HouseholdId) -> RevenueOut:
    try:
        return RevenueOut.model_validate(
            finance_service.get_revenue(db, household_id, revenue_id)
        )
    except NotFound as exc:
        raise _http(exc) from exc


@router.patch("/revenues/{revenue_id}", response_model=RevenueOut, summary="Sửa khoản thu")
def update_revenue(
    revenue_id: str,
    payload: RevenueUpdate,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
) -> RevenueOut:
    try:
        revenue = finance_service.update_revenue(
            db, household_id, revenue_id, payload, device_id=device_id
        )
    except (NotFound, Conflict, ValidationFailed) as exc:
        raise _http(exc) from exc
    result = RevenueOut.model_validate(revenue)
    db.commit()
    return result


@router.delete(
    "/revenues/{revenue_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xoá khoản thu",
)
def delete_revenue(
    revenue_id: str, db: DbSession, household_id: HouseholdId, device_id: DeviceId
):
    try:
        finance_service.delete_revenue(db, household_id, revenue_id, device_id=device_id)
    except NotFound as exc:
        raise _http(exc) from exc
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  Summary
# ═══════════════════════════════════════════════════════════════════════════


@season_router.get(
    "/summary",
    response_model=SeasonSummary,
    summary="Tổng kết mùa vụ: chi phí, doanh thu, lợi nhuận",
)
def season_summary(season_id: str, db: DbSession, household_id: HouseholdId) -> SeasonSummary:
    """Profit is computed here, never stored (invariant I10).

    Supply consumption is already present as `diary_auto` expenses, so
    `total_cost` includes it with no separate step — double-counting is
    structurally impossible (I9). The split between auto and manual cost is
    surfaced because it is how a farmer learns to trust the automatic half.
    """
    try:
        data = finance_service.season_summary(db, household_id, season_id)
    except NotFound as exc:
        raise _http(exc) from exc

    data["cost_by_category"] = [
        CategoryBreakdown(
            category=row["category"],
            label=EXPENSE_CATEGORY_LABELS_VI.get(row["category"], row["category"]),
            amount=row["amount"],
            share_pct=row["share_pct"],
        )
        for row in data["cost_by_category"]
    ]
    return SeasonSummary(**data)
