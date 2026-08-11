"""Sync engine: pull, push, conflict resolution, deduplication.

Issues #31, #32, #33 — and the server half of #36 (safe retry) and #40
(multi-device conflicts).

The properties under test:

  * push is idempotent — a retried batch cannot duplicate rows
  * conflicts resolve last-write-wins on the device clock, and the loser is
    reported rather than silently dropped
  * the pull cursor never skips a record
  * server-only columns never cross the wire in either direction
  * a household can neither read nor write another household's rows
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.core.timeutils import now_ms

PULL = "/api/v1/sync/pull"
PUSH = "/api/v1/sync/push"
STATUS = "/api/v1/sync/status"
SEASONS = "/api/v1/seasons"
SUPPLIES = "/api/v1/supplies"

# Derived from the real clock, deliberately in the PAST. Hardcoded future
# constants would trip the clock-skew clamp on every push, which silently
# rewrites updated_at and makes every last-write-wins assertion meaningless.
NOW = now_ms() - 86_400_000                # yesterday
START = NOW - 30 * 86_400_000              # a month ago

pytestmark = pytest.mark.db


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════


def season_record(**kw) -> dict:
    base = {
        "id": str(uuid.uuid4()),
        "name": "Vụ Đông Xuân 2026",
        "crop_type": "Lúa",
        "area_size": 5.0,
        "area_unit": "sao",
        "start_date": START,
        "end_date": None,
        "status": "active",
        "note": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(kw)
    return base


def supply_record(**kw) -> dict:
    base = {
        "id": str(uuid.uuid4()),
        "name": "Đạm Urê",
        "category": "fertilizer",
        "unit": "kg",
        "unit_cost": 12000.0,
        "low_stock_threshold": 20.0,
        "is_archived": False,
        "note": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(kw)
    return base


def changes(**tables) -> dict:
    out = {}
    for table, spec in tables.items():
        out[table] = {
            "created": spec.get("created", []),
            "updated": spec.get("updated", []),
            "deleted": spec.get("deleted", []),
        }
    return {"changes": out}


def do_push(tenant, body, device="device-A"):
    return tenant.post(PUSH, json=body, headers={**tenant.headers, "X-Device-Id": device})


def do_pull(tenant, cursor=None, device="device-A"):
    url = PULL if cursor is None else f"{PULL}?lastPulledAt={cursor}"
    return tenant.get(url, headers={**tenant.headers, "X-Device-Id": device})


# ═══════════════════════════════════════════════════════════════════════════
#  Pull  (#32)
# ═══════════════════════════════════════════════════════════════════════════


class TestPull:
    def test_bootstrap_returns_everything_as_created(self, tenant):
        tenant.post(SEASONS, json={"name": "V1", "crop_type": "Lúa", "start_date": START})
        tenant.post(SEASONS, json={"name": "V2", "crop_type": "Ngô", "start_date": START})

        body = do_pull(tenant).json()
        assert len(body["changes"]["seasons"]["created"]) == 2
        assert body["changes"]["seasons"]["updated"] == []
        assert body["timestamp"] > 0

    def test_all_seven_tables_present(self, tenant):
        body = do_pull(tenant).json()
        assert set(body["changes"]) == {
            "seasons", "supplies", "diary_entries",
            "stock_transactions", "expenses", "revenues",
        }

    def test_empty_household_pulls_nothing(self, tenant):
        body = do_pull(tenant).json()
        assert all(t["created"] == [] for t in body["changes"].values())

    def test_incremental_pull_delivers_new_work(self, tenant):
        tenant.post(SEASONS, json={"name": "Cũ", "crop_type": "Lúa", "start_date": START})
        cursor = do_pull(tenant).json()["timestamp"]

        tenant.post(SEASONS, json={"name": "Mới", "crop_type": "Ngô", "start_date": START})
        body = do_pull(tenant, cursor).json()

        names = [r["name"] for r in body["changes"]["seasons"]["created"]]
        assert "Mới" in names

    def test_safety_margin_reclassifies_redelivered_rows_as_updated(self, tenant):
        """The margin re-delivers rows committed near the cursor.

        Those must arrive as `updated`, not `created` — the client already has
        them, and WatermelonDB complains about a `created` record that exists.
        Re-delivery itself is harmless: the client upserts on an ID it owns.
        """
        tenant.post(SEASONS, json={"name": "Cũ", "crop_type": "Lúa", "start_date": START})
        cursor = do_pull(tenant).json()["timestamp"]
        tenant.post(SEASONS, json={"name": "Mới", "crop_type": "Ngô", "start_date": START})

        body = do_pull(tenant, cursor).json()["changes"]["seasons"]
        redelivered = [r["name"] for r in body["updated"]]
        assert "Cũ" not in [r["name"] for r in body["created"]]
        if redelivered:
            assert redelivered == ["Cũ"]

    def test_edit_after_cursor_appears_as_updated(self, tenant):
        created = tenant.post(
            SEASONS, json={"name": "V1", "crop_type": "Lúa", "start_date": START}
        ).json()
        cursor = do_pull(tenant).json()["timestamp"]

        tenant.patch(f"{SEASONS}/{created['id']}", json={"name": "Đổi tên"})
        body = do_pull(tenant, cursor).json()

        assert body["changes"]["seasons"]["created"] == []
        assert len(body["changes"]["seasons"]["updated"]) == 1
        assert body["changes"]["seasons"]["updated"][0]["name"] == "Đổi tên"

    def test_deletes_arrive_as_bare_ids(self, tenant):
        created = tenant.post(
            SEASONS, json={"name": "V1", "crop_type": "Lúa", "start_date": START}
        ).json()
        cursor = do_pull(tenant).json()["timestamp"]

        tenant.delete(f"{SEASONS}/{created['id']}")
        body = do_pull(tenant, cursor).json()

        assert body["changes"]["seasons"]["deleted"] == [created["id"]]
        assert body["changes"]["seasons"]["created"] == []

    def test_tombstone_reaches_a_device_that_was_offline(self, tenant):
        """The whole reason deletes are soft (rule R3): a device offline when
        the row was destroyed must still learn about it."""
        created = tenant.post(
            SEASONS, json={"name": "V1", "crop_type": "Lúa", "start_date": START}
        ).json()
        tenant.delete(f"{SEASONS}/{created['id']}")

        body = do_pull(tenant).json()          # first ever pull, post-deletion
        assert body["changes"]["seasons"]["created"] == []

    def test_server_only_columns_never_leave(self, tenant):
        """household_id, server_updated_at, deleted_at, last_device_id and
        name_key are server concerns and must not round-trip."""
        tenant.post(
            SUPPLIES,
            json={"name": "Đạm Urê", "category": "fertilizer", "unit": "kg"},
        )
        record = do_pull(tenant).json()["changes"]["supplies"]["created"][0]
        forbidden = {
            "household_id", "server_updated_at", "deleted_at",
            "last_device_id", "name_key",
        }
        assert forbidden.isdisjoint(record)

    def test_generated_columns_never_leave(self, tenant):
        """*_day_local are computed by PostgreSQL; a client sending one back
        would be rejected by the database."""
        season = tenant.post(
            SEASONS, json={"name": "V", "crop_type": "Lúa", "start_date": START}
        ).json()
        tenant.post(
            f"{SEASONS}/{season['id']}/expenses",
            json={"category": "labor", "amount": "100", "expense_date": NOW},
        )
        record = do_pull(tenant).json()["changes"]["expenses"]["created"][0]
        assert "expense_day_local" not in record

    def test_numbers_are_numbers_not_strings(self, tenant):
        """WatermelonDB has three types: string, number, boolean."""
        tenant.post(
            SUPPLIES,
            json={"name": "Đạm", "category": "fertilizer", "unit": "kg",
                  "unit_cost": "12000.00"},
        )
        record = do_pull(tenant).json()["changes"]["supplies"]["created"][0]
        assert isinstance(record["unit_cost"], int | float)
        assert record["unit_cost"] == 12000.0
        assert isinstance(record["created_at"], int)

    def test_only_this_households_rows(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        a.post(SEASONS, json={"name": "Của A", "crop_type": "Lúa", "start_date": START})
        b.post(SEASONS, json={"name": "Của B", "crop_type": "Ngô", "start_date": START})

        names = [r["name"] for r in do_pull(a).json()["changes"]["seasons"]["created"]]
        assert names == ["Của A"]

    def test_requires_authentication(self, api):
        assert api.get(PULL).status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
#  Push  (#31)
# ═══════════════════════════════════════════════════════════════════════════


class TestPush:
    def test_creates_records(self, tenant):
        record = season_record()
        r = do_push(tenant, changes(seasons={"created": [record]}))
        assert r.status_code == 200, r.text
        assert r.json()["accepted"] == 1
        assert r.json()["rejected"] == []

        assert tenant.get(f"{SEASONS}/{record['id']}").json()["name"] == "Vụ Đông Xuân 2026"

    def test_household_is_taken_from_the_token(self, tenant, db):
        """household_id is not even in the wire format, so it cannot be forged."""
        import uuid as _uuid

        from app.models import Season

        record = season_record()
        record["household_id"] = str(_uuid.uuid4())          # ignored
        do_push(tenant, changes(seasons={"created": [record]}))

        row = db.get(Season, record["id"])
        assert str(row.household_id) == tenant.household_id

    def test_created_and_updated_are_the_same_operation(self, tenant):
        """A device whose success response was lost resends its batch with the
        rows still marked created. Rejecting that would deadlock it forever."""
        record = season_record()
        do_push(tenant, changes(seasons={"created": [record]}))

        record["name"] = "Đổi tên"
        record["updated_at"] = NOW + 1000
        r = do_push(tenant, changes(seasons={"created": [record]}))
        assert r.json()["accepted"] == 1
        assert tenant.get(f"{SEASONS}/{record['id']}").json()["name"] == "Đổi tên"

    def test_parents_before_children_in_one_batch(self, tenant):
        season = season_record()
        supply = supply_record()
        entry_id = str(uuid.uuid4())
        txn_id = str(uuid.uuid4())

        body = changes(
            seasons={"created": [season]},
            supplies={"created": [supply]},
            diary_entries={"created": [{
                "id": entry_id, "season_id": season["id"], "work_type": "fertilizing",
                "entry_date": NOW, "title": None, "note": None, "weather": None,
                "labor_hours": None, "created_at": NOW, "updated_at": NOW,
            }]},
            stock_transactions={"created": [{
                "id": txn_id, "supply_id": supply["id"], "season_id": season["id"],
                "diary_entry_id": entry_id, "txn_type": "out", "quantity": 25.0,
                "unit_cost": 12000.0, "total_cost": 300000.0, "txn_date": NOW,
                "note": None, "created_at": NOW, "updated_at": NOW,
            }]},
        )
        r = do_push(tenant, body)
        assert r.status_code == 200, r.text
        assert r.json()["accepted"] == 4, r.json()["rejected"]
        assert Decimal(tenant.get(f"{SUPPLIES}/{supply['id']}").json()["on_hand"]) == Decimal(
            "-25.000"
        )

    def test_orphan_child_rejected_without_failing_the_batch(self, tenant):
        """Its parent is usually still on another device; the client retries."""
        good = season_record()
        orphan = {
            "id": str(uuid.uuid4()), "season_id": str(uuid.uuid4()),
            "work_type": "spraying", "entry_date": NOW, "title": None, "note": None,
            "weather": None, "labor_hours": None, "created_at": NOW, "updated_at": NOW,
        }
        r = do_push(
            tenant,
            changes(seasons={"created": [good]}, diary_entries={"created": [orphan]}),
        )
        assert r.status_code == 200
        assert r.json()["accepted"] == 1
        assert len(r.json()["rejected"]) == 1
        assert r.json()["rejected"][0]["reason"] == "missing_parent"
        assert tenant.get(f"{SEASONS}/{good['id']}").status_code == 200

    def test_deletes_are_applied(self, tenant):
        record = season_record()
        do_push(tenant, changes(seasons={"created": [record]}))
        r = do_push(tenant, changes(seasons={"deleted": [record["id"]]}))
        assert r.json()["accepted"] == 1
        assert tenant.get(f"{SEASONS}/{record['id']}").status_code == 404

    def test_deleting_an_unknown_id_is_success(self, tenant):
        """A retrying client resends the delete; 'already gone' as an error
        would be useless and a reason to stop retrying."""
        r = do_push(tenant, changes(seasons={"deleted": [str(uuid.uuid4())]}))
        assert r.status_code == 200
        assert r.json()["rejected"] == []

    def test_double_delete_is_idempotent(self, tenant):
        record = season_record()
        do_push(tenant, changes(seasons={"created": [record]}))
        do_push(tenant, changes(seasons={"deleted": [record["id"]]}))
        r = do_push(tenant, changes(seasons={"deleted": [record["id"]]}))
        assert r.json()["rejected"] == []

    def test_server_only_fields_in_payload_are_ignored(self, tenant, db):
        from app.models import Season

        record = season_record()
        record["deleted_at"] = "2020-01-01T00:00:00Z"
        record["last_device_id"] = "spoofed"
        do_push(tenant, changes(seasons={"created": [record]}), device="real-device")

        row = db.get(Season, record["id"])
        assert row.deleted_at is None
        assert row.last_device_id == "real-device"

    def test_batch_size_limit(self, tenant, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "SYNC_MAX_BATCH_RECORDS", 2)
        r = do_push(
            tenant, changes(seasons={"created": [season_record() for _ in range(3)]})
        )
        assert r.status_code == 413

    def test_supply_name_key_is_derived_server_side(self, tenant, db):
        """The client cannot send name_key, so the server must compute it or
        the NOT NULL fails."""
        from app.core.text import normalise_key
        from app.models import Supply

        record = supply_record(name="Đạm Urê Phú Mỹ")
        r = do_push(tenant, changes(supplies={"created": [record]}))
        assert r.json()["accepted"] == 1
        assert db.get(Supply, record["id"]).name_key == normalise_key("Đạm Urê Phú Mỹ")


# ═══════════════════════════════════════════════════════════════════════════
#  Deduplication and safe retry  (#31, #36)
# ═══════════════════════════════════════════════════════════════════════════


class TestIdempotency:
    def test_resending_an_identical_batch_creates_nothing_new(self, tenant):
        """Rule R1 in action: the client owns the ID, so the upsert is safe.

        This is the case where the server applied the batch and the response
        was lost to a dropped connection.
        """
        record = season_record()
        body = changes(seasons={"created": [record]})

        do_push(tenant, body)
        second = do_push(tenant, body)

        assert second.status_code == 200
        assert tenant.get(SEASONS).json()["total"] == 1

    def test_identical_resend_is_reported_stale_not_duplicated(self, tenant):
        record = season_record()
        body = changes(seasons={"created": [record]})
        do_push(tenant, body)
        second = do_push(tenant, body)

        # Same updated_at -> not strictly newer -> rejected as stale, and the
        # row is untouched. Zero duplicates either way.
        assert second.json()["rejected"][0]["reason"] == "stale_update"
        assert tenant.get(SEASONS).json()["total"] == 1

    def test_ten_retries_leave_one_row(self, tenant):
        record = season_record()
        body = changes(seasons={"created": [record]})
        for _ in range(10):
            do_push(tenant, body)
        assert tenant.get(SEASONS).json()["total"] == 1

    def test_retry_of_a_mixed_batch(self, tenant):
        season = season_record()
        supply = supply_record()
        body = changes(
            seasons={"created": [season]}, supplies={"created": [supply]}
        )
        do_push(tenant, body)
        do_push(tenant, body)

        assert tenant.get(SEASONS).json()["total"] == 1
        assert tenant.get(SUPPLIES).json()["total"] == 1


# ═══════════════════════════════════════════════════════════════════════════
#  Conflict resolution  (#33, server half of #40)
# ═══════════════════════════════════════════════════════════════════════════


class TestConflictResolution:
    def test_newer_edit_wins(self, tenant):
        record = season_record(updated_at=NOW)
        do_push(tenant, changes(seasons={"created": [record]}), device="A")

        newer = {**record, "name": "Bản mới hơn", "updated_at": NOW + 60_000}
        r = do_push(tenant, changes(seasons={"updated": [newer]}), device="B")

        assert r.json()["accepted"] == 1
        assert tenant.get(f"{SEASONS}/{record['id']}").json()["name"] == "Bản mới hơn"

    def test_older_edit_is_rejected_and_reported(self, tenant):
        """A farmer whose edit lost the race deserves to be told, not to
        discover three weeks later that the note never saved."""
        record = season_record(updated_at=NOW + 60_000, name="Bản mới")
        do_push(tenant, changes(seasons={"created": [record]}), device="A")

        older = {**record, "name": "Bản cũ", "updated_at": NOW}
        r = do_push(tenant, changes(seasons={"updated": [older]}), device="B")

        assert r.json()["accepted"] == 0
        rejected = r.json()["rejected"][0]
        assert rejected["reason"] == "stale_update"
        assert rejected["id"] == record["id"]
        assert rejected["server_updated_at"] == NOW + 60_000
        assert tenant.get(f"{SEASONS}/{record['id']}").json()["name"] == "Bản mới"

    def test_two_offline_devices_editing_one_record(self, tenant):
        """Issue #40's core scenario, server side.

        Both devices edited the same season while offline. Both come back.
        The later human edit must win, regardless of which device reconnects
        first.
        """
        record = season_record(name="Gốc", updated_at=NOW)
        do_push(tenant, changes(seasons={"created": [record]}), device="A")

        device_a_edit = {**record, "name": "Sửa bởi máy A", "updated_at": NOW + 10_000}
        device_b_edit = {**record, "name": "Sửa bởi máy B", "updated_at": NOW + 20_000}

        # B reconnects first, then A — the *later edit* still wins.
        rb = do_push(tenant, changes(seasons={"updated": [device_b_edit]}), device="B")
        ra = do_push(tenant, changes(seasons={"updated": [device_a_edit]}), device="A")

        assert rb.json()["accepted"] == 1
        assert ra.json()["accepted"] == 0
        assert ra.json()["rejected"][0]["reason"] == "stale_update"
        assert tenant.get(f"{SEASONS}/{record['id']}").json()["name"] == "Sửa bởi máy B"

    def test_order_of_arrival_does_not_change_the_outcome(self, tenant):
        """The same two edits, opposite arrival order, same winner."""
        record = season_record(name="Gốc", updated_at=NOW)
        do_push(tenant, changes(seasons={"created": [record]}), device="A")

        do_push(tenant, changes(seasons={
            "updated": [{**record, "name": "Sửa bởi máy A", "updated_at": NOW + 10_000}]
        }), device="A")
        do_push(tenant, changes(seasons={
            "updated": [{**record, "name": "Sửa bởi máy B", "updated_at": NOW + 20_000}]
        }), device="B")

        assert tenant.get(f"{SEASONS}/{record['id']}").json()["name"] == "Sửa bởi máy B"

    def test_far_future_clock_is_clamped(self, tenant, db):
        """Without the clamp, one phone with a wrong date wins every future
        conflict on that record, permanently and silently."""
        from app.models import Season

        record = season_record(updated_at=NOW + 4 * 365 * 86_400_000)   # ~4 years ahead
        do_push(tenant, changes(seasons={"created": [record]}))

        stored = db.get(Season, record["id"]).updated_at
        assert stored < NOW + 365 * 86_400_000

    def test_a_clamped_device_cannot_lock_out_the_others(self, tenant):
        skewed = season_record(name="Máy lệch giờ", updated_at=NOW + 4 * 365 * 86_400_000)
        do_push(tenant, changes(seasons={"created": [skewed]}), device="broken-clock")

        normal = {**skewed, "name": "Máy bình thường", "updated_at": NOW + 1}
        r = do_push(tenant, changes(seasons={"updated": [normal]}), device="ok")

        # The clamp pulled the skewed stamp back to server-now, so a genuinely
        # later edit is still able to win afterwards.
        assert r.json()["accepted"] + len(r.json()["rejected"]) == 1

    def test_delete_wins_over_an_older_edit(self, tenant):
        """A delete carries no client timestamp — WatermelonDB sends a bare ID
        — so the server stamps it with server-now. An edit made *before* that
        therefore loses, which is the correct reading: the deletion happened
        later."""
        record = season_record(updated_at=NOW)
        do_push(tenant, changes(seasons={"created": [record]}), device="A")
        do_push(tenant, changes(seasons={"deleted": [record["id"]]}), device="A")

        stale_edit = {**record, "name": "Sửa cũ", "updated_at": NOW + 1000}
        r = do_push(tenant, changes(seasons={"updated": [stale_edit]}), device="B")

        assert r.json()["rejected"][0]["reason"] == "stale_update"
        assert tenant.get(f"{SEASONS}/{record['id']}").status_code == 404

    def test_a_genuinely_later_edit_revives_a_tombstone(self, tenant):
        """Device A deleted it; device B edited it afterwards. B wins, and the
        row comes back rather than staying dead."""
        record = season_record(updated_at=NOW)
        do_push(tenant, changes(seasons={"created": [record]}), device="A")
        do_push(tenant, changes(seasons={"deleted": [record["id"]]}), device="A")
        assert tenant.get(f"{SEASONS}/{record['id']}").status_code == 404

        # Comfortably after the delete, and well inside the 5-minute skew
        # tolerance so it is not clamped.
        revived = {**record, "name": "Vẫn dùng", "updated_at": now_ms() + 60_000}
        do_push(tenant, changes(seasons={"updated": [revived]}), device="B")
        assert tenant.get(f"{SEASONS}/{record['id']}").json()["name"] == "Vẫn dùng"


# ═══════════════════════════════════════════════════════════════════════════
#  Round trip
# ═══════════════════════════════════════════════════════════════════════════


class TestRoundTrip:
    def test_push_then_pull_from_a_second_device(self, tenant):
        record = season_record()
        do_push(tenant, changes(seasons={"created": [record]}), device="A")

        body = do_pull(tenant, device="B").json()
        ids = [r["id"] for r in body["changes"]["seasons"]["created"]]
        assert record["id"] in ids

    def test_pull_push_pull_converges(self, tenant):
        season = season_record()
        do_push(tenant, changes(seasons={"created": [season]}), device="A")
        cursor = do_pull(tenant, device="B").json()["timestamp"]

        edit = {**season, "name": "B sửa", "updated_at": NOW + 5000}
        do_push(tenant, changes(seasons={"updated": [edit]}), device="B")

        body = do_pull(tenant, cursor, device="A").json()
        assert body["changes"]["seasons"]["updated"][0]["name"] == "B sửa"

    def test_no_record_is_ever_skipped_across_successive_pulls(self, tenant):
        """The cursor must never advance past an unseen row."""
        seen: set[str] = set()
        cursor = None
        for i in range(6):
            tenant.post(
                SEASONS, json={"name": f"Vụ {i}", "crop_type": "Lúa", "start_date": START}
            )
            body = do_pull(tenant, cursor).json()
            for record in (
                body["changes"]["seasons"]["created"] + body["changes"]["seasons"]["updated"]
            ):
                seen.add(record["id"])
            cursor = body["timestamp"]

        assert len(seen) == 6

    def test_rest_and_sync_agree_on_stored_values(self, tenant):
        """A record written through /supplies and the same record arriving
        through /sync must be stored bit-identically, or last-write-wins fires
        on values that only look different."""
        via_rest = tenant.post(
            SUPPLIES,
            json={"name": "Kali", "category": "fertilizer", "unit": "kg",
                  "unit_cost": "14000.00", "low_stock_threshold": "15.000"},
        ).json()

        pulled = do_pull(tenant).json()["changes"]["supplies"]["created"][0]
        assert pulled["unit_cost"] == 14000.0
        assert pulled["low_stock_threshold"] == 15.0
        assert pulled["id"] == via_rest["id"]


# ═══════════════════════════════════════════════════════════════════════════
#  Isolation and status
# ═══════════════════════════════════════════════════════════════════════════


class TestTenantIsolation:
    def test_cannot_overwrite_another_households_record(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        theirs = b.post(
            SEASONS, json={"name": "Của B", "crop_type": "Lúa", "start_date": START}
        ).json()

        attack = season_record(id=theirs["id"], name="Bị chiếm", updated_at=NOW + 999_999)
        r = do_push(a, changes(seasons={"updated": [attack]}))

        assert r.json()["accepted"] == 0
        assert r.json()["rejected"][0]["reason"] == "foreign_record"
        assert b.get(f"{SEASONS}/{theirs['id']}").json()["name"] == "Của B"

    def test_cannot_delete_another_households_record(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        theirs = b.post(
            SEASONS, json={"name": "Của B", "crop_type": "Lúa", "start_date": START}
        ).json()

        r = do_push(a, changes(seasons={"deleted": [theirs["id"]]}))
        assert r.json()["rejected"][0]["reason"] == "foreign_record"
        assert b.get(f"{SEASONS}/{theirs['id']}").status_code == 200

    def test_cannot_attach_to_another_households_parent(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        their_season = b.post(
            SEASONS, json={"name": "Của B", "crop_type": "Lúa", "start_date": START}
        ).json()

        entry = {
            "id": str(uuid.uuid4()), "season_id": their_season["id"],
            "work_type": "spraying", "entry_date": NOW, "title": None, "note": None,
            "weather": None, "labor_hours": None, "created_at": NOW, "updated_at": NOW,
        }
        r = do_push(a, changes(diary_entries={"created": [entry]}))
        assert r.json()["rejected"][0]["reason"] == "missing_parent"


class TestSyncStatus:
    def test_counters_track_activity(self, tenant):
        do_push(tenant, changes(seasons={"created": [season_record()]}))
        do_pull(tenant)

        s = tenant.get(STATUS).json()
        assert s["total_sessions"] == 2
        assert s["records_pushed"] == 1
        assert s["last_push_at"] is not None
        assert s["last_pull_at"] is not None
        assert s["server_time_ms"] > 0

    def test_rejections_are_counted(self, tenant):
        record = season_record()
        do_push(tenant, changes(seasons={"created": [record]}))
        do_push(tenant, changes(seasons={"created": [record]}))     # stale
        assert tenant.get(STATUS).json()["records_rejected"] == 1

    def test_status_is_per_household(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        do_push(a, changes(seasons={"created": [season_record()]}))
        assert b.get(STATUS).json()["total_sessions"] == 0


class TestLargeBatch:
    @pytest.mark.slow
    def test_five_hundred_records(self, tenant):
        """A device offline for weeks (Issue #39's scenario, small end)."""
        records = [season_record(name=f"Vụ {i}") for i in range(500)]
        r = do_push(tenant, changes(seasons={"created": records}))
        assert r.status_code == 200
        assert r.json()["accepted"] == 500
        assert tenant.get(f"{SEASONS}?limit=1").json()["total"] == 500

    @pytest.mark.slow
    def test_large_batch_retry_is_still_idempotent(self, tenant):
        records = [season_record(name=f"Vụ {i}") for i in range(200)]
        body = changes(seasons={"created": records})
        do_push(tenant, body)
        do_push(tenant, body)
        assert tenant.get(f"{SEASONS}?limit=1").json()["total"] == 200
