"""Supply and stock-ledger schemas (Issue #23)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    SUPPLY_CATEGORY_LABELS_VI,
    TXN_TYPE_LABELS_VI,
    SupplyCategory,
    TxnType,
)

COMMON_UNITS = ("kg", "g", "tấn", "L", "ml", "bao", "chai", "gói", "cái", "bình")


def _uuid_or_none(v: str | None) -> str | None:
    if v is None:
        return None
    try:
        return str(uuid.UUID(v))
    except ValueError as exc:
        raise ValueError("id phải là UUID hợp lệ") from exc


# ═══════════════════════════════════════════════════════════════════════════
#  Supply
# ═══════════════════════════════════════════════════════════════════════════


class SupplyCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str | None = Field(default=None, max_length=36)
    name: str = Field(min_length=1, max_length=120, examples=["Đạm Urê Phú Mỹ"])
    category: SupplyCategory
    unit: str = Field(min_length=1, max_length=16, examples=["kg"])
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=16, decimal_places=2)
    low_stock_threshold: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=14, decimal_places=3
    )
    note: str | None = None
    created_at: int | None = None
    updated_at: int | None = None

    _check_id = field_validator("id")(_uuid_or_none)


class SupplyUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: SupplyCategory | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=16)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    low_stock_threshold: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=3
    )
    is_archived: bool | None = None
    note: str | None = None
    updated_at: int | None = None


class SupplyOut(BaseModel):
    """A supply plus its derived stock position.

    `on_hand` is NEVER a stored column — it is always recomputed from the
    ledger (D1). A cached counter decremented independently by two offline
    devices is undetectably wrong after sync.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: SupplyCategory
    category_label: str = ""
    unit: str
    unit_cost: Decimal
    low_stock_threshold: Decimal
    is_archived: bool
    note: str | None
    created_at: int
    updated_at: int

    on_hand: Decimal = Field(
        default=Decimal("0.000"), description="Σin + Σadjust − Σout over the live ledger"
    )
    is_low_stock: bool = False
    is_negative: bool = Field(
        default=False,
        description=(
            "Stock has gone below zero — the farmer logged usage of something "
            "they never recorded buying. A prompt, not an error."
        ),
    )

    @model_validator(mode="after")
    def _derive(self):
        if not self.category_label:
            self.category_label = SUPPLY_CATEGORY_LABELS_VI.get(
                self.category, self.category.value
            )
        self.is_negative = self.on_hand < 0
        self.is_low_stock = (
            self.low_stock_threshold > 0 and self.on_hand <= self.low_stock_threshold
        )
        return self


# ═══════════════════════════════════════════════════════════════════════════
#  Stock movements
# ═══════════════════════════════════════════════════════════════════════════


class StockMovementCreate(BaseModel):
    """A stock-in or stock-out. Quantity is always positive; direction comes
    from the endpoint."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str | None = Field(default=None, max_length=36)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_cost: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=16,
        decimal_places=2,
        description=(
            "Price at the time of this movement. Defaults to the supply's "
            "current unit_cost. Snapshotted, never joined live — fertiliser "
            "bought in March must stay costed at March's price."
        ),
    )
    season_id: str | None = Field(default=None, max_length=36)
    txn_date: int | None = Field(default=None, description="Epoch ms; defaults to now")
    note: str | None = None
    created_at: int | None = None
    updated_at: int | None = None

    _check_id = field_validator("id")(_uuid_or_none)


class StockAdjustCreate(BaseModel):
    """A stock-take (kiểm kê).

    The farmer counts what is physically there; the server computes the delta
    against the ledger and records that. Asking for a delta instead would make
    the farmer do arithmetic against a number they do not trust — which is the
    reason they are counting in the first place.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str | None = Field(default=None, max_length=36)
    counted_quantity: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    txn_date: int | None = None
    note: str | None = None

    _check_id = field_validator("id")(_uuid_or_none)


class StockTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    supply_id: str
    season_id: str | None
    diary_entry_id: str | None
    txn_type: TxnType
    txn_type_label: str = ""
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    txn_date: int
    note: str | None
    created_at: int
    updated_at: int

    @model_validator(mode="after")
    def _label(self):
        if not self.txn_type_label:
            self.txn_type_label = TXN_TYPE_LABELS_VI.get(self.txn_type, self.txn_type.value)
        return self


class StockMovementResult(BaseModel):
    """The movement, plus the resulting stock position.

    Returned together so the inventory screen can update without a second
    request — one fewer thing to fail on a rural connection.
    """

    transaction: StockTransactionOut | None
    supply: SupplyOut


class StockAdjustResult(StockMovementResult):
    delta: Decimal = Field(description="Signed correction applied; 0 means no change was needed")
    no_change: bool = False
