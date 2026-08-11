"""Epoch-ms date handling and the sync clock-skew guard. No database required."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import settings
from app.core.timeutils import (
    MS_PER_DAY,
    clamp_client_timestamp,
    from_ms,
    local_day_index,
    local_month_key,
    now_ms,
    to_ms,
)

UTC = timezone.utc


class TestEpochConversion:
    def test_roundtrip(self):
        dt = datetime(2026, 9, 12, 13, 45, 30, tzinfo=UTC)
        assert from_ms(to_ms(dt)) == dt

    def test_naive_datetime_read_as_utc(self):
        naive = datetime(2026, 9, 12, 0, 0, 0)
        aware = datetime(2026, 9, 12, 0, 0, 0, tzinfo=UTC)
        assert to_ms(naive) == to_ms(aware)

    def test_now_ms_is_sane(self):
        # Somewhere between 2020 and 2100.
        assert 1_577_836_800_000 < now_ms() < 4_102_444_800_000


class TestLocalDay:
    """These must agree with the SQL generated columns exactly.

    The Python side buckets report data on the mobile client; the SQL side
    buckets it on the server. A one-day disagreement means the same season
    renders two different charts depending on where the numbers came from.
    """

    def test_offset_is_utc_plus_7(self):
        assert settings.APP_TZ_OFFSET_MS == 7 * 60 * 60 * 1000 == 25_200_000

    def test_matches_sql_expression(self):
        """Mirrors ((col + 25200000) / 86400000)::INTEGER."""
        for ms in (0, 1_767_225_600_000, 1_789_000_123_456, now_ms()):
            expected = (ms + 25_200_000) // MS_PER_DAY
            assert local_day_index(ms) == expected

    def test_late_evening_stays_on_the_same_local_day(self):
        """20:00 on the 12th in Vietnam must not become the 13th.

        This is the classic offline-sync date bug: the entry is logged at
        20:00 local (= 13:00 UTC) and a naive UTC bucket keeps it on the 12th,
        but an entry at 23:30 local (= 16:30 UTC) is still the 12th too. Both
        must land in the same local day.
        """
        eight_pm_local = to_ms(datetime(2026, 9, 12, 13, 0, tzinfo=UTC))
        half_eleven_local = to_ms(datetime(2026, 9, 12, 16, 30, tzinfo=UTC))
        assert local_day_index(eight_pm_local) == local_day_index(half_eleven_local)

    def test_local_midnight_starts_a_new_day(self):
        before = to_ms(datetime(2026, 9, 12, 16, 59, 59, tzinfo=UTC))   # 23:59:59 local
        after = to_ms(datetime(2026, 9, 12, 17, 0, 1, tzinfo=UTC))      # 00:00:01 local, 13th
        assert local_day_index(after) == local_day_index(before) + 1

    def test_month_key_format(self):
        assert local_month_key(to_ms(datetime(2026, 9, 12, 3, 0, tzinfo=UTC))) == "2026-09"

    def test_month_key_respects_local_offset(self):
        """23:30 on 30 Sep local (16:30 UTC) belongs to September, not October."""
        assert local_month_key(to_ms(datetime(2026, 9, 30, 16, 30, tzinfo=UTC))) == "2026-09"


class TestClockSkewGuard:
    def test_normal_timestamp_passes_through(self):
        server = now_ms()
        value, clamped = clamp_client_timestamp(server - 1000, server_ms=server)
        assert value == server - 1000
        assert clamped is False

    def test_small_drift_tolerated(self):
        """Ordinary NTP drift must not be treated as a broken clock."""
        server = now_ms()
        ahead = server + 60_000   # 1 minute
        value, clamped = clamp_client_timestamp(ahead, server_ms=server)
        assert value == ahead
        assert clamped is False

    def test_far_future_clamped(self):
        """A phone stamped 2030 would otherwise win every future conflict on
        that record -- permanently and silently discarding other devices' edits."""
        server = now_ms()
        value, clamped = clamp_client_timestamp(server + 4 * 365 * 86_400_000, server_ms=server)
        assert value == server
        assert clamped is True

    def test_boundary_is_exclusive(self):
        server = now_ms()
        edge = server + settings.SYNC_CLOCK_SKEW_TOLERANCE_MS
        assert clamp_client_timestamp(edge, server_ms=server) == (edge, False)
        assert clamp_client_timestamp(edge + 1, server_ms=server) == (server, True)

    def test_past_timestamps_never_clamped(self):
        """A device offline for three weeks legitimately pushes old timestamps."""
        server = now_ms()
        old = server - 21 * 86_400_000
        assert clamp_client_timestamp(old, server_ms=server) == (old, False)
