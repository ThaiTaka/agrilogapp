"""Sync API contract (Issues #9, #31, #32, #33).

The shapes here are dictated by WatermelonDB's `synchronize()`. Deviating from
them would mean writing a custom adapter on the client, which is exactly the
work choosing WatermelonDB was meant to avoid.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TableChanges(BaseModel):
    """One table's slice of a change set.

    `created` and `updated` carry whole records; `deleted` carries bare ID
    strings, which is why the server keeps tombstones rather than hard
    deleting — a hard delete is invisible to a device that was offline when it
    happened.
    """

    model_config = ConfigDict(extra="forbid")

    created: list[dict[str, Any]] = Field(default_factory=list)
    updated: list[dict[str, Any]] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)

    def total(self) -> int:
        return len(self.created) + len(self.updated) + len(self.deleted)


class PullResponse(BaseModel):
    """Exactly the shape WatermelonDB's `pullChanges` must return."""

    changes: dict[str, TableChanges]
    timestamp: int = Field(
        description="Server clock in epoch ms. Becomes the client's next last_pulled_at."
    )


class PushRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    changes: dict[str, TableChanges]

    def total(self) -> int:
        return sum(t.total() for t in self.changes.values())


class RejectedRecord(BaseModel):
    """A record the server refused, reported rather than silently dropped.

    A farmer whose edit lost a last-write-wins race deserves to be told, not
    to discover three weeks later that the note never saved. The client
    surfaces this in the sync status UI (Issue #35).
    """

    table: str
    id: str
    reason: str = Field(
        description=(
            "stale_update | missing_parent | foreign_record | unknown_table | "
            "invalid_record"
        )
    )
    detail: str | None = None
    server_updated_at: int | None = Field(
        default=None, description="The winning record's device timestamp, for stale_update"
    )


class PushResponse(BaseModel):
    accepted: int
    rejected: list[RejectedRecord] = Field(default_factory=list)
    timestamp: int


class SyncStatus(BaseModel):
    """Operational view of a household's sync history (Issue #35 / #39)."""

    last_pull_at: int | None
    last_push_at: int | None
    total_sessions: int
    records_pushed: int
    records_pulled: int
    records_rejected: int
    server_time_ms: int
