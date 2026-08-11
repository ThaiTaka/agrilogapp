"""The sync engine (Issues #31 push, #32 pull, #33 conflicts & dedup).

This is the module the whole data model exists to serve. Everything upstream —
client-generated IDs, two clocks, tombstones, deferred foreign keys — was
shaped by what happens here.

Five rules, each one load-bearing:

  1. The tenant comes from the JWT, never from the payload. `household_id` is
     not even in the wire format, so a malicious client cannot write into
     another household by forging a field that is never read.
  2. `created` and `updated` are treated identically — both are an upsert on
     a client-generated ID. A device whose success response was lost to a
     dropped connection resends the batch; treating that as an error would
     deadlock it forever.
  3. Conflicts resolve last-write-wins on the DEVICE clock, and the loser is
     REPORTED, not silently dropped.
  4. The whole batch is one transaction. A connection dropped mid-push leaves
     PostgreSQL exactly as it was; the client still holds every record at
     `_status != 'synced'` and retries. There is no partial-apply state.
  5. The pull cursor is the SERVER clock, rewound by a safety margin, because
     a feed that can skip a record is unfixable after the fact while a feed
     that occasionally repeats one is merely slightly wasteful.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, Integer, Numeric, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.numeric import quantize_money, quantize_quantity
from app.core.text import normalise_key
from app.core.timeutils import clamp_client_timestamp, from_ms, now_ms, to_ms
from app.models import SYNC_MODELS, SYNC_TABLE_ORDER, Supply, SyncSession
from app.models.enums import SyncDirection, SyncStatus
from app.schemas.sync import RejectedRecord, TableChanges

logger = logging.getLogger("agrilog.sync")

UTC = timezone.utc

# Never crosses the wire.
#
# `household_id` is excluded because the client already knows its household
# from the JWT and every row it can see belongs to it — sending it would add a
# column to seven WatermelonDB tables carrying zero information and create a
# seventh chance for a schema mismatch.
#
# `name_key` is derived from `name` by the server (see app/core/text.py); the
# client must not be able to set it independently or the two could disagree.
SERVER_ONLY_COLUMNS = frozenset(
    {
        "household_id",
        "server_updated_at",
        "deleted_at",
        "last_device_id",
        "name_key",
    }
)


def payload_columns(model) -> list[str]:
    """Whitelist of columns that appear in a sync payload.

    Generated columns (`*_day_local`) are excluded automatically via
    `column.computed` — they are recomputed by PostgreSQL on write, and a
    client sending one would be rejected by the database.
    """
    return [
        c.name
        for c in model.__table__.columns
        if c.name not in SERVER_ONLY_COLUMNS and c.computed is None
    ]


# ═══════════════════════════════════════════════════════════════════════════
#  Serialisation
# ═══════════════════════════════════════════════════════════════════════════


def _to_wire(value: Any) -> Any:
    """Decimal -> float, datetime -> epoch ms.

    WatermelonDB has three column types: string, number, boolean. Money in VND
    is a whole number of đồng far below float64's exact-integer ceiling, and
    quantities are rounded to 3 dp on both sides, so the conversion is lossless
    for every value this application holds (Data_Requirements_Database.md §7.1).
    """
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return to_ms(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def serialise(model, row) -> dict[str, Any]:
    return {name: _to_wire(getattr(row, name)) for name in payload_columns(model)}


def _coerce(model, column_name: str, value: Any) -> Any:
    """Turn an incoming JSON value into the column's Python type.

    Numerics go through the same quantisation the REST API uses, so a record
    written through `/supplies` and the same record arriving through `/sync`
    are stored bit-identically. Without that, last-write-wins would fire on
    values that only *look* different.
    """
    if value is None:
        return None

    column = model.__table__.columns[column_name]
    kind = column.type

    if isinstance(kind, Numeric):
        return quantize_money(value) if kind.scale == 2 else quantize_quantity(value)
    if isinstance(kind, BigInteger | Integer):
        return int(value)
    if isinstance(kind, Boolean):
        return bool(value)
    return value


def _derive_server_columns(model, values: dict[str, Any]) -> None:
    """Fill in columns the client is not allowed to send but the schema needs."""
    if model is Supply and "name" in values:
        values["name_key"] = normalise_key(str(values["name"]))


# ═══════════════════════════════════════════════════════════════════════════
#  Pull  (Issue #32)
# ═══════════════════════════════════════════════════════════════════════════


def pull(
    db: Session,
    household_id: uuid.UUID,
    *,
    last_pulled_at: int | None,
    device_id: str | None = None,
) -> dict[str, Any]:
    """Return everything that changed since the client's cursor.

    The cursor is rewound by `SYNC_CURSOR_SAFETY_MARGIN_MS` before querying. A
    row is *stamped* when written but only becomes *visible* when its
    transaction commits, so a transaction that writes at T5 and commits at T8
    is invisible to a pull running at T6 — which would then store cursor T6 and
    skip it forever. Re-delivering a row is harmless: the client upserts on a
    client-generated ID, so a duplicate pull is a no-op. The design trades a
    few redundant rows for the impossibility of a lost one.
    """
    session_row = SyncSession(
        household_id=household_id,
        device_id=device_id,
        direction=SyncDirection.PULL.value,
        last_pulled_at=last_pulled_at,
        status=SyncStatus.OK.value,
    )
    db.add(session_row)
    db.flush()

    # Captured ONCE, before any table is read. Taken at the end instead, a row
    # committed by another device during the read would fall before the
    # returned cursor and never be pulled again.
    now_dt = db.execute(select(func.clock_timestamp())).scalar_one()
    now_ts = to_ms(now_dt)

    bootstrap = not last_pulled_at
    client_cursor_ms = 0 if bootstrap else last_pulled_at
    # The margin widens DETECTION only. Classification below uses the
    # un-rewound cursor — see the comment on the created/updated split.
    detect_ms = (
        0 if bootstrap else max(0, last_pulled_at - settings.SYNC_CURSOR_SAFETY_MARGIN_MS)
    )
    detect_dt = from_ms(detect_ms)

    changes: dict[str, TableChanges] = {}
    pulled = 0

    for table in SYNC_TABLE_ORDER:
        model = SYNC_MODELS[table]
        created: list[dict] = []
        updated: list[dict] = []
        deleted: list[str] = []

        if bootstrap:
            # Everything live, all as `created`. The client has nothing.
            rows = db.execute(
                select(model).where(
                    model.household_id == household_id, model.deleted_at.is_(None)
                )
            ).scalars().all()
            created = [serialise(model, r) for r in rows]
        else:
            rows = db.execute(
                select(model).where(
                    model.household_id == household_id,
                    model.server_updated_at > detect_dt,
                )
            ).scalars().all()
            for row in rows:
                if row.deleted_at is not None:
                    deleted.append(row.id)
                # Classified against the client's ACTUAL cursor, never the
                # rewound one. WatermelonDB complains when `created` holds a
                # record it already has, and the margin's whole job is to
                # re-deliver rows the client probably does have. Rewinding the
                # classification too would turn every safety re-delivery into
                # a spurious "record already exists" on the device.
                elif row.created_at > client_cursor_ms:
                    created.append(serialise(model, row))
                else:
                    updated.append(serialise(model, row))

        changes[table] = TableChanges(created=created, updated=updated, deleted=deleted)
        pulled += len(created) + len(updated) + len(deleted)

    session_row.finished_at = datetime.now(UTC)
    session_row.records_pulled = pulled
    db.flush()

    logger.info(
        "pull household=%s device=%s cursor=%s records=%d",
        household_id, device_id, last_pulled_at, pulled,
    )
    return {"changes": changes, "timestamp": now_ts}


# ═══════════════════════════════════════════════════════════════════════════
#  Push  (Issues #31, #33)
# ═══════════════════════════════════════════════════════════════════════════


def _sync_fk_columns(model) -> list[tuple[str, str]]:
    """`(column_name, target_table)` for FKs pointing at other synced tables."""
    return [
        (fk.parent.name, fk.column.table.name)
        for fk in model.__table__.foreign_keys
        if fk.column.table.name in SYNC_MODELS
    ]


def _existing_ids(db: Session, table: str, household_id: uuid.UUID, ids: set[str]) -> set[str]:
    if not ids:
        return set()
    model = SYNC_MODELS[table]
    rows = db.execute(
        select(model.id).where(model.id.in_(ids), model.household_id == household_id)
    ).scalars().all()
    return set(rows)


class _Rejections:
    def __init__(self) -> None:
        self.items: list[RejectedRecord] = []

    def add(self, table: str, record_id: str, reason: str, **kw) -> None:
        self.items.append(RejectedRecord(table=table, id=record_id, reason=reason, **kw))


def push(
    db: Session,
    household_id: uuid.UUID,
    changes: dict[str, TableChanges],
    *,
    device_id: str | None = None,
) -> dict[str, Any]:
    """Apply a batch of client changes. One transaction, per-record reporting."""
    total = sum(t.total() for t in changes.values())
    if total > settings.SYNC_MAX_BATCH_RECORDS:
        raise ValueError(
            f"Batch quá lớn: {total} bản ghi (tối đa {settings.SYNC_MAX_BATCH_RECORDS}). "
            "Hãy đồng bộ thành nhiều lần."
        )

    session_row = SyncSession(
        household_id=household_id,
        device_id=device_id,
        direction=SyncDirection.PUSH.value,
        status=SyncStatus.OK.value,
    )
    db.add(session_row)
    db.flush()

    now_dt = db.execute(select(func.clock_timestamp())).scalar_one()
    server_ms = to_ms(now_dt)

    rejected = _Rejections()
    accepted = 0

    unknown = set(changes) - set(SYNC_MODELS)
    for table in unknown:
        for record in changes[table].created + changes[table].updated:
            rejected.add(table, str(record.get("id", "?")), "unknown_table")

    # ── Upserts, parents before children ───────────────────────────────────
    for table in SYNC_TABLE_ORDER:
        slice_ = changes.get(table)
        if slice_ is None:
            continue
        accepted += _apply_upserts(
            db, household_id, table, slice_, rejected, server_ms, device_id
        )

    # ── Deletes, children before parents ───────────────────────────────────
    for table in reversed(SYNC_TABLE_ORDER):
        slice_ = changes.get(table)
        if slice_ is None or not slice_.deleted:
            continue
        accepted += _apply_deletes(
            db, household_id, table, slice_.deleted, rejected, device_id
        )

    session_row.finished_at = datetime.now(UTC)
    session_row.records_pushed = accepted
    session_row.records_rejected = len(rejected.items)
    session_row.status = (
        SyncStatus.PARTIAL.value if rejected.items else SyncStatus.OK.value
    )
    if rejected.items:
        session_row.error_detail = "; ".join(
            f"{r.table}/{r.id}:{r.reason}" for r in rejected.items[:20]
        )
    db.flush()

    logger.info(
        "push household=%s device=%s accepted=%d rejected=%d",
        household_id, device_id, accepted, len(rejected.items),
    )
    return {
        "accepted": accepted,
        "rejected": rejected.items,
        "timestamp": server_ms,
    }


def _apply_upserts(
    db: Session,
    household_id: uuid.UUID,
    table: str,
    slice_: TableChanges,
    rejected: _Rejections,
    server_ms: int,
    device_id: str | None,
) -> int:
    model = SYNC_MODELS[table]
    allowed = set(payload_columns(model))
    fk_columns = _sync_fk_columns(model)

    # `created` and `updated` are the same operation. A device whose success
    # response was lost resends its batch with the rows still marked created;
    # rejecting that would deadlock it permanently.
    records = slice_.created + slice_.updated
    if not records:
        return 0

    # One existence query per referenced table rather than one per record.
    referenced: dict[str, set[str]] = {}
    for record in records:
        for column, target in fk_columns:
            value = record.get(column)
            if value:
                referenced.setdefault(target, set()).add(str(value))
    known: dict[str, set[str]] = {
        target: _existing_ids(db, target, household_id, ids)
        for target, ids in referenced.items()
    }

    accepted = 0
    for record in records:
        record_id = record.get("id")
        if not record_id or not isinstance(record_id, str):
            rejected.add(table, str(record_id or "?"), "invalid_record", detail="missing id")
            continue

        existing = db.get(model, record_id)

        # An ID that already belongs to another household is not ours to
        # touch. Reported per-record rather than failing the batch: a
        # colliding client UUID is astronomically unlikely, so this almost
        # always means a device was re-registered to a different household.
        if existing is not None and existing.household_id != household_id:
            rejected.add(table, record_id, "foreign_record")
            continue

        incoming_updated, was_clamped = clamp_client_timestamp(
            int(record.get("updated_at") or server_ms), server_ms=server_ms
        )
        if was_clamped:
            logger.warning(
                "clock skew clamped: household=%s device=%s table=%s id=%s",
                household_id, device_id, table, record_id,
            )

        if existing is not None:
            # Last-write-wins on the DEVICE clock: it is what represents the
            # order the two humans actually made their edits.
            if incoming_updated <= existing.updated_at:
                rejected.add(
                    table,
                    record_id,
                    "stale_update",
                    server_updated_at=existing.updated_at,
                )
                continue
        else:
            missing = [
                column
                for column, target in fk_columns
                if record.get(column) and str(record[column]) not in known.get(target, set())
            ]
            if missing:
                # Reject the child only, never the batch. Its parent is
                # usually still on another device; the client retries next
                # cycle, by which time it has arrived.
                rejected.add(
                    table,
                    record_id,
                    "missing_parent",
                    detail=f"unknown {', '.join(missing)}",
                )
                continue

        values = {
            name: _coerce(model, name, value)
            for name, value in record.items()
            if name in allowed and name != "id"
        }
        values["updated_at"] = incoming_updated
        _derive_server_columns(model, values)

        # A savepoint per record: a unique-constraint violation on one row
        # must not poison the session and take the other 499 down with it.
        try:
            with db.begin_nested():
                if existing is None:
                    values.setdefault("created_at", incoming_updated)
                    db.add(
                        model(
                            id=record_id,
                            household_id=household_id,
                            last_device_id=device_id,
                            **values,
                        )
                    )
                else:
                    for name, value in values.items():
                        setattr(existing, name, value)
                    existing.deleted_at = None   # an update revives a tombstone
                    existing.last_device_id = device_id
                db.flush()
        except IntegrityError as exc:
            rejected.add(
                table, record_id, "invalid_record",
                detail=_constraint_of(exc) or "constraint violation",
            )
            continue
        except SQLAlchemyError as exc:            # noqa: BLE001 - report, do not abort
            rejected.add(table, record_id, "invalid_record", detail=type(exc).__name__)
            continue

        # Only counted once the savepoint released, so `accepted` is the
        # number of rows that actually landed.
        accepted += 1

        if record_id in known.get(table, set()):
            pass
        else:
            known.setdefault(table, set()).add(record_id)

    return accepted


def _apply_deletes(
    db: Session,
    household_id: uuid.UUID,
    table: str,
    ids: list[str],
    rejected: _Rejections,
    device_id: str | None,
) -> int:
    """Tombstone rows. Idempotent — deleting an already-deleted row is success.

    A retrying client will resend the same delete, and telling it "already
    gone" as an error would be both useless and a reason to stop retrying.
    """
    model = SYNC_MODELS[table]
    # WatermelonDB sends a bare ID for a delete, with no client timestamp, so
    # the server has to supply one. Server-now is the only defensible choice:
    # it means a subsequent edit wins only if it genuinely happened after the
    # deletion, rather than any edit at all reviving a deleted row.
    ts = now_ms()
    now = datetime.now(UTC)
    accepted = 0

    for record_id in ids:
        row = db.get(model, record_id)
        if row is None:
            accepted += 1          # nothing to do; the client's view is correct
            continue
        if row.household_id != household_id:
            rejected.add(table, record_id, "foreign_record")
            continue
        if row.deleted_at is None:
            row.deleted_at = now
            row.updated_at = ts
            row.last_device_id = device_id
        accepted += 1

    db.flush()
    return accepted


def _constraint_of(exc: IntegrityError) -> str | None:
    message = str(getattr(exc, "orig", exc))
    marker = 'constraint "'
    if marker in message:
        return message.split(marker, 1)[1].split('"', 1)[0]
    return None


# ═══════════════════════════════════════════════════════════════════════════
#  Status
# ═══════════════════════════════════════════════════════════════════════════


def sync_status(db: Session, household_id: uuid.UUID) -> dict[str, Any]:
    """Operational counters, for the sync status UI and the load tests."""

    def _last(direction: SyncDirection) -> int | None:
        row = db.execute(
            select(SyncSession.finished_at)
            .where(
                SyncSession.household_id == household_id,
                SyncSession.direction == direction.value,
                SyncSession.finished_at.is_not(None),
            )
            .order_by(SyncSession.started_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        return to_ms(row) if row else None

    totals = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(SyncSession.records_pushed), 0),
            func.coalesce(func.sum(SyncSession.records_pulled), 0),
            func.coalesce(func.sum(SyncSession.records_rejected), 0),
        ).where(SyncSession.household_id == household_id)
    ).one()

    return {
        "last_pull_at": _last(SyncDirection.PULL),
        "last_push_at": _last(SyncDirection.PUSH),
        "total_sessions": totals[0],
        "records_pushed": totals[1],
        "records_pulled": totals[2],
        "records_rejected": totals[3],
        "server_time_ms": now_ms(),
    }
