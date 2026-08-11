"""Sync endpoints (Issues #31, #32, #33).

    GET  /api/v1/sync/pull?last_pulled_at=<ms>&schema_version=<n>
    POST /api/v1/sync/push
    GET  /api/v1/sync/status

The request and response shapes are dictated by WatermelonDB's
`synchronize()`. The mobile adapter (Issue #34) is:

    synchronize({
      database,
      pullChanges: async ({ lastPulledAt, schemaVersion, migration }) => {
        const r = await api.get('/sync/pull', { lastPulledAt, schemaVersion, migration })
        return { changes: r.changes, timestamp: r.timestamp }
      },
      pushChanges: async ({ changes, lastPulledAt }) => {
        await api.post('/sync/push', { changes, lastPulledAt })
      },
    })
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession, DeviceId, HouseholdId
from app.schemas.sync import PullResponse, PushRequest, PushResponse, SyncStatus
from app.services import sync_service

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/pull", response_model=PullResponse, summary="Kéo thay đổi từ máy chủ")
def pull(
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
    last_pulled_at: Annotated[
        int | None,
        Query(
            alias="lastPulledAt",
            ge=0,
            description="Epoch ms from the previous pull. Omit or 0 for a full bootstrap.",
        ),
    ] = None,
    schema_version: Annotated[int | None, Query(alias="schemaVersion")] = None,
    migration: Annotated[str | None, Query()] = None,
) -> PullResponse:
    """Everything changed since the cursor, scoped to the caller's household.

    `schemaVersion` and `migration` are accepted because WatermelonDB always
    sends them. They are not acted on yet: the client and server schemas are
    versioned together and no migration-aware pull is needed until the mobile
    schema diverges (Issue #34 revisits this).
    """
    result = sync_service.pull(
        db, household_id, last_pulled_at=last_pulled_at, device_id=device_id
    )
    db.commit()
    return PullResponse(**result)


@router.post("/push", response_model=PushResponse, summary="Đẩy thay đổi cục bộ lên máy chủ")
def push(
    payload: PushRequest,
    db: DbSession,
    household_id: HouseholdId,
    device_id: DeviceId,
    last_pulled_at: Annotated[int | None, Query(alias="lastPulledAt", ge=0)] = None,
) -> PushResponse:
    """Apply a batch atomically.

    The whole batch is one transaction. A connection dropped mid-push leaves
    the database exactly as it was, the client still holds every record at
    `_status != 'synced'`, and it retries the whole thing. There is no
    partial-apply state to reconcile — a little wasted bandwidth bought in
    exchange for the guarantee that the database is never half-updated.

    Records that cannot be applied are reported individually rather than
    failing the batch, because the usual cause is a parent still sitting on
    another device.
    """
    try:
        result = sync_service.push(
            db, household_id, payload.changes, device_id=device_id
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    except Exception:
        db.rollback()
        raise

    db.commit()
    return PushResponse(**result)


@router.get("/status", response_model=SyncStatus, summary="Trạng thái đồng bộ của nông hộ")
def sync_status(db: DbSession, household_id: HouseholdId) -> SyncStatus:
    """Feeds the sync status indicator (Issue #35) and the load tests (#39)."""
    return SyncStatus(**sync_service.sync_status(db, household_id))
