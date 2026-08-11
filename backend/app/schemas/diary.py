"""Farming diary schemas (Issues #21, #25, #29)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import WORK_TYPE_LABELS_VI, WorkType

WEATHER_VALUES = ("sunny", "cloudy", "rain", "storm", "windy")


def _uuid_or_none(v: str | None) -> str | None:
    if v is None:
        return None
    try:
        return str(uuid.UUID(v))
    except ValueError as exc:
        raise ValueError("id phải là UUID hợp lệ") from exc


class SupplyUsageIn(BaseModel):
    """One supply consumed by a diary entry.

    Becomes a `stock_transactions` row (`txn_type='out'`) which in turn
    generates a `diary_auto` expense. The farmer enters it once; the ledger
    and the cost sheet both update.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str | None = Field(
        default=None,
        max_length=36,
        description="Client-supplied ID for the resulting stock transaction",
    )
    supply_id: str = Field(max_length=36)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_cost: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=16,
        decimal_places=2,
        description="Defaults to the supply's current price, then snapshotted",
    )
    note: str | None = None

    _check_id = field_validator("id")(_uuid_or_none)


class _DiaryFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    work_type: WorkType
    entry_date: int | None = Field(default=None, description="Epoch ms; defaults to now")
    title: str | None = Field(default=None, max_length=160)
    note: str | None = None
    weather: str | None = Field(default=None, max_length=32)
    labor_hours: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=2)

    @field_validator("weather")
    @classmethod
    def _known_weather(cls, v: str | None) -> str | None:
        if v is not None and v not in WEATHER_VALUES:
            raise ValueError(f"Thời tiết phải là một trong: {', '.join(WEATHER_VALUES)}")
        return v


def _no_duplicate_supplies(usages: list[SupplyUsageIn]) -> list[SupplyUsageIn]:
    """Reconciliation on update is keyed by supply_id.

    Two lines for the same supply would make "which line did the farmer
    change?" unanswerable, so it is rejected at the edge rather than resolved
    by a guess. The UI sums them before submitting.
    """
    seen = [u.supply_id for u in usages]
    dupes = {s for s in seen if seen.count(s) > 1}
    if dupes:
        raise ValueError(
            "Mỗi vật tư chỉ được khai báo một dòng trong cùng một nhật ký. "
            f"Trùng: {', '.join(sorted(dupes))}"
        )
    return usages


class DiaryEntryCreate(_DiaryFields):
    id: str | None = Field(default=None, max_length=36)
    supply_usages: list[SupplyUsageIn] = Field(default_factory=list)
    created_at: int | None = None
    updated_at: int | None = None

    _check_id = field_validator("id")(_uuid_or_none)
    _check_usages = field_validator("supply_usages")(_no_duplicate_supplies)


class DiaryEntryUpdate(BaseModel):
    """Partial update.

    `supply_usages` distinguishes *absent* from *empty*:
      * omitted  -> consumption is left exactly as it is
      * `[]`     -> every consumption is reversed and the stock returned

    Collapsing those two would make "I only changed the note" silently wipe
    the farmer's fertiliser record.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    work_type: WorkType | None = None
    entry_date: int | None = None
    title: str | None = Field(default=None, max_length=160)
    note: str | None = None
    weather: str | None = Field(default=None, max_length=32)
    labor_hours: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=2)
    season_id: str | None = Field(default=None, max_length=36)
    supply_usages: list[SupplyUsageIn] | None = None
    updated_at: int | None = None

    @field_validator("weather")
    @classmethod
    def _known_weather(cls, v: str | None) -> str | None:
        if v is not None and v not in WEATHER_VALUES:
            raise ValueError(f"Thời tiết phải là một trong: {', '.join(WEATHER_VALUES)}")
        return v

    @field_validator("supply_usages")
    @classmethod
    def _check_usages(cls, v: list[SupplyUsageIn] | None) -> list[SupplyUsageIn] | None:
        return None if v is None else _no_duplicate_supplies(v)


class SupplyUsageOut(BaseModel):
    transaction_id: str
    supply_id: str
    supply_name: str
    unit: str
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    note: str | None = None


class DiaryEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    season_id: str
    work_type: WorkType
    work_type_label: str = ""
    entry_date: int
    title: str | None
    note: str | None
    weather: str | None
    labor_hours: Decimal | None
    created_at: int
    updated_at: int

    supply_usages: list[SupplyUsageOut] = Field(default_factory=list)
    total_supply_cost: Decimal = Field(
        default=Decimal("0.00"),
        description="Σ total_cost of the consumptions — equals the auto-generated expenses",
    )

    @model_validator(mode="after")
    def _label(self):
        if not self.work_type_label:
            self.work_type_label = WORK_TYPE_LABELS_VI.get(self.work_type, self.work_type.value)
        return self


class DiaryDeleteResult(BaseModel):
    """What deleting the entry reversed.

    Returned rather than a bare 204 so the UI can tell the farmer "3 khoản
    vật tư đã được hoàn kho" instead of leaving them to wonder.
    """

    id: str
    stock_transactions_reversed: int
    expenses_removed: int
    quantity_restored: dict[str, Decimal] = Field(
        default_factory=dict, description="supply_id -> quantity returned to inventory"
    )
