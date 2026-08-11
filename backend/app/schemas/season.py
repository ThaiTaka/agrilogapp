"""Crop season schemas (Issue #19)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import SEASON_STATUS_LABELS_VI, SeasonStatus

AREA_UNITS = ("sao", "ha", "m2", "công", "mẫu")


class SeasonBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120, examples=["Vụ Đông Xuân 2026"])
    crop_type: str = Field(min_length=1, max_length=80, examples=["Lúa"])
    area_size: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=3)
    area_unit: str = Field(default="sao", max_length=16)
    start_date: int = Field(description="Epoch milliseconds")
    end_date: int | None = Field(
        default=None, description="Epoch milliseconds. Null = season still running."
    )
    status: SeasonStatus = SeasonStatus.ACTIVE
    note: str | None = None

    @field_validator("area_unit")
    @classmethod
    def _known_area_unit(cls, v: str) -> str:
        if v not in AREA_UNITS:
            raise ValueError(f"Đơn vị diện tích phải là một trong: {', '.join(AREA_UNITS)}")
        return v

    @model_validator(mode="after")
    def _date_range(self):
        # Also enforced by ck_seasons_date_range_valid and by the mobile form.
        # Three layers, because a bad range silently breaks every report that
        # filters by the season window — and a silent report bug costs far
        # more to find than a loud validation error.
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("Ngày kết thúc không được trước ngày bắt đầu")
        return self


class SeasonCreate(SeasonBase):
    """`id` is optional and client-supplied (rule R1).

    An offline device generates the ID before it ever reaches the network, so
    a retried create cannot produce a duplicate — the server upserts on a key
    the client already owns. Omit it and the server generates one, which is
    what a browser or curl will do.
    """

    id: str | None = Field(default=None, max_length=36)
    created_at: int | None = None
    updated_at: int | None = None

    @field_validator("id")
    @classmethod
    def _valid_uuid(cls, v: str | None) -> str | None:
        if v is None:
            return None
        try:
            return str(uuid.UUID(v))
        except ValueError as exc:
            raise ValueError("id phải là UUID hợp lệ") from exc


class SeasonUpdate(BaseModel):
    """Partial update. Only the supplied fields change."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=120)
    crop_type: str | None = Field(default=None, min_length=1, max_length=80)
    area_size: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=3)
    area_unit: str | None = Field(default=None, max_length=16)
    start_date: int | None = None
    end_date: int | None = None
    status: SeasonStatus | None = None
    note: str | None = None
    updated_at: int | None = Field(
        default=None, description="Device clock. Used for last-write-wins."
    )

    @field_validator("area_unit")
    @classmethod
    def _known_area_unit(cls, v: str | None) -> str | None:
        if v is not None and v not in AREA_UNITS:
            raise ValueError(f"Đơn vị diện tích phải là một trong: {', '.join(AREA_UNITS)}")
        return v


class SeasonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    crop_type: str
    area_size: Decimal | None
    area_unit: str
    start_date: int
    end_date: int | None
    status: SeasonStatus
    status_label: str = ""
    note: str | None
    created_at: int
    updated_at: int

    @model_validator(mode="after")
    def _label(self):
        # Served from the backend so the app and the API can never disagree
        # about what a status is called in Vietnamese.
        if not self.status_label:
            self.status_label = SEASON_STATUS_LABELS_VI.get(self.status, self.status.value)
        return self


class SeasonDeleteResult(BaseModel):
    """What a soft delete actually removed.

    Returned rather than a bare 204 because deleting a season cascades, and a
    farmer tapping "xoá" deserves to know that 40 diary entries went with it.
    """

    id: str
    diary_entries_deleted: int
    expenses_deleted: int
    revenues_deleted: int
    stock_transactions_deleted: int
    stock_transactions_unlinked: int
