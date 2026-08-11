"""Shared schema building blocks."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50


class Page(BaseModel, Generic[T]):
    """Offset-paginated list envelope.

    `total` is the count *before* pagination, so the client can render "20 of
    137" and decide whether to keep scrolling. Issue #49 adds pagination to
    every list endpoint; doing it from the first endpoint avoids a breaking
    response-shape change later.
    """

    items: list[T]
    total: int = Field(description="Total matching rows, ignoring limit/offset")
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


class SyncFields(BaseModel):
    """The client-owned sync columns every synced resource exposes.

    `id` is accepted on create because record IDs are generated on the device
    (rule R1). That is what makes a retried write safe — the server upserts on
    a key the client already owns — and it means the REST API and the sync API
    agree on identity rather than each minting their own.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: int = Field(description="Epoch milliseconds, device clock")
    updated_at: int = Field(description="Epoch milliseconds, device clock")
