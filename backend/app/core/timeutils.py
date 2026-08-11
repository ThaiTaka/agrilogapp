"""Time helpers.

AgriLog stores every *business* date as epoch milliseconds (BIGINT), because
that is exactly WatermelonDB's own date representation. Keeping the same
integer on both sides removes the timezone conversion at the sync boundary --
which is where "logged at 8pm on the 12th, shows up on the 13th" bugs come
from. See Data_Requirements_Database.md section 7.2.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from app.core.config import settings

UTC = timezone.utc  # `datetime.UTC` is 3.11+; this keeps the stated 3.10 floor
MS_PER_DAY = 86_400_000


def now_ms() -> int:
    """Current UTC time as epoch milliseconds."""
    return int(time.time() * 1000)


def to_ms(dt: datetime) -> int:
    """Convert a datetime to epoch milliseconds.

    Naive datetimes are interpreted as UTC — the server never produces naive
    local times, so a naive value here is always a UTC value that lost its
    tzinfo somewhere in transit.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


def from_ms(ms: int) -> datetime:
    """Convert epoch milliseconds to a timezone-aware UTC datetime."""
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def local_day_index(ms: int) -> int:
    """Days since the epoch in the app's fixed local timezone (UTC+7).

    Mirrors the SQL generated columns exactly:
        ((<date_col> + 25200000) / 86400000)::INTEGER

    Python's `//` floors while PostgreSQL's integer `/` truncates toward zero;
    they agree for every non-negative input, and every date this application
    handles is post-1970.
    """
    return (ms + settings.APP_TZ_OFFSET_MS) // MS_PER_DAY


def local_month_key(ms: int) -> str:
    """Report bucket key, e.g. '2026-09', in the app's fixed local timezone."""
    return from_ms(ms + settings.APP_TZ_OFFSET_MS).strftime("%Y-%m")


def clamp_client_timestamp(client_ms: int, *, server_ms: int | None = None) -> tuple[int, bool]:
    """Guard against a device with a badly wrong system clock.

    Without this, one phone stamped with a far-future date wins every
    subsequent last-write-wins comparison on a record, permanently and
    silently discarding every other device's edits.

    Returns ``(effective_ms, was_clamped)``.
    """
    server_ms = server_ms if server_ms is not None else now_ms()
    if client_ms > server_ms + settings.SYNC_CLOCK_SKEW_TOLERANCE_MS:
        return server_ms, True
    return client_ms, False
