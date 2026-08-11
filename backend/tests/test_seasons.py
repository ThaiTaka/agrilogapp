"""Season CRUD (Issue #19)."""

from __future__ import annotations

import uuid

import pytest

SEASONS = "/api/v1/seasons"

# 2026-08-10 and 2026-11-15, epoch ms
START = 1786665600000
END = 1794787200000

VALID = {
    "name": "Vụ Đông Xuân 2026",
    "crop_type": "Lúa",
    "area_size": "5.000",
    "area_unit": "sao",
    "start_date": START,
    "end_date": END,
    "status": "active",
    "note": "Giống OM5451",
}


# ═══════════════════════════════════════════════════════════════════════════
#  Schema validation — no database
# ═══════════════════════════════════════════════════════════════════════════


class TestSeasonSchema:
    def test_end_before_start_rejected(self):
        from pydantic import ValidationError

        from app.schemas.season import SeasonCreate

        with pytest.raises(ValidationError, match="Ngày kết thúc"):
            SeasonCreate(**{**VALID, "end_date": START - 1})

    def test_open_ended_season_allowed(self):
        """A farmer mid-season has not decided when it ends."""
        from app.schemas.season import SeasonCreate

        assert SeasonCreate(**{**VALID, "end_date": None}).end_date is None

    def test_unknown_area_unit_rejected(self):
        from pydantic import ValidationError

        from app.schemas.season import SeasonCreate

        with pytest.raises(ValidationError, match="Đơn vị diện tích"):
            SeasonCreate(**{**VALID, "area_unit": "acre"})

    def test_negative_area_rejected(self):
        from pydantic import ValidationError

        from app.schemas.season import SeasonCreate

        with pytest.raises(ValidationError):
            SeasonCreate(**{**VALID, "area_size": "-1"})

    def test_non_uuid_id_rejected(self):
        from pydantic import ValidationError

        from app.schemas.season import SeasonCreate

        with pytest.raises(ValidationError, match="UUID"):
            SeasonCreate(**{**VALID, "id": "not-a-uuid"})


# ═══════════════════════════════════════════════════════════════════════════
#  Database-backed
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.db
class TestCreate:
    def test_creates_a_season(self, tenant):
        r = tenant.post(SEASONS, json=VALID)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["name"] == "Vụ Đông Xuân 2026"
        assert body["status"] == "active"
        assert body["status_label"] == "Đang canh tác"
        assert uuid.UUID(body["id"])
        assert body["created_at"] > 0 and body["updated_at"] > 0

    def test_client_supplied_id_is_honoured(self, tenant):
        """Rule R1: the device owns the ID, generated before any network call."""
        given = str(uuid.uuid4())
        r = tenant.post(SEASONS, json={**VALID, "id": given})
        assert r.status_code == 201
        assert r.json()["id"] == given

    def test_duplicate_id_conflicts(self, tenant):
        """A repeated create through REST is a mistake worth surfacing.

        Idempotent upsert belongs on /sync/push, where a repeat is a retry.
        """
        given = str(uuid.uuid4())
        tenant.post(SEASONS, json={**VALID, "id": given})
        assert tenant.post(SEASONS, json={**VALID, "id": given}).status_code == 409

    def test_defaults_applied(self, tenant):
        minimal = {"name": "Vụ Mùa", "crop_type": "Bắp cải", "start_date": START}
        r = tenant.post(SEASONS, json=minimal)
        assert r.status_code == 201
        body = r.json()
        assert body["area_unit"] == "sao"
        assert body["status"] == "active"
        assert body["end_date"] is None

    def test_requires_authentication(self, api):
        assert api.post(SEASONS, json=VALID).status_code == 401

    def test_end_before_start_is_422(self, tenant):
        assert tenant.post(SEASONS, json={**VALID, "end_date": START - 1}).status_code == 422

    def test_decimal_area_survives_roundtrip(self, tenant):
        r = tenant.post(SEASONS, json={**VALID, "area_size": "12.345"})
        assert r.json()["area_size"] == "12.345"


@pytest.mark.db
class TestList:
    def test_lists_only_this_households_seasons(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        a.post(SEASONS, json=VALID)
        a.post(SEASONS, json={**VALID, "name": "Vụ Hè Thu"})
        b.post(SEASONS, json={**VALID, "name": "Của hộ B"})

        body = a.get(SEASONS).json()
        assert body["total"] == 2
        assert {i["name"] for i in body["items"]} == {"Vụ Đông Xuân 2026", "Vụ Hè Thu"}

    def test_empty_household(self, tenant):
        body = tenant.get(SEASONS).json()
        assert body == {"items": [], "total": 0, "limit": 50, "offset": 0}

    def test_filter_by_status(self, tenant):
        tenant.post(SEASONS, json=VALID)
        tenant.post(SEASONS, json={**VALID, "name": "Đã xong", "status": "closed"})
        body = tenant.get(f"{SEASONS}?status=closed").json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Đã xong"

    def test_filter_by_crop_type_is_case_insensitive(self, tenant):
        tenant.post(SEASONS, json=VALID)
        tenant.post(SEASONS, json={**VALID, "name": "Cà chua", "crop_type": "Cà chua"})
        assert tenant.get(f"{SEASONS}?crop_type=lúa").json()["total"] == 1

    def test_pagination(self, tenant):
        for i in range(5):
            tenant.post(SEASONS, json={**VALID, "name": f"Vụ {i}", "start_date": START + i * 86400000})
        page = tenant.get(f"{SEASONS}?limit=2&offset=0").json()
        assert page["total"] == 5 and len(page["items"]) == 2

        second = tenant.get(f"{SEASONS}?limit=2&offset=2").json()
        assert {i["id"] for i in page["items"]}.isdisjoint({i["id"] for i in second["items"]})

    def test_sorted_newest_first(self, tenant):
        tenant.post(SEASONS, json={**VALID, "name": "Cũ", "start_date": START})
        tenant.post(SEASONS, json={**VALID, "name": "Mới", "start_date": START + 86400000})
        names = [i["name"] for i in tenant.get(SEASONS).json()["items"]]
        assert names == ["Mới", "Cũ"]

    def test_limit_is_capped(self, tenant):
        assert tenant.get(f"{SEASONS}?limit=99999").status_code == 422


@pytest.mark.db
class TestRetrieve:
    def test_get_by_id(self, tenant):
        created = tenant.post(SEASONS, json=VALID).json()
        r = tenant.get(f"{SEASONS}/{created['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]

    def test_unknown_id_404(self, tenant):
        assert tenant.get(f"{SEASONS}/{uuid.uuid4()}").status_code == 404


@pytest.mark.db
class TestUpdate:
    def test_partial_update(self, tenant):
        created = tenant.post(SEASONS, json=VALID).json()
        r = tenant.patch(f"{SEASONS}/{created['id']}", json={"status": "harvested"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "harvested"
        assert body["status_label"] == "Đã thu hoạch"
        assert body["name"] == VALID["name"]        # untouched
        assert body["crop_type"] == VALID["crop_type"]

    def test_updated_at_advances(self, tenant):
        created = tenant.post(SEASONS, json=VALID).json()
        after = tenant.patch(f"{SEASONS}/{created['id']}", json={"note": "đổi"}).json()
        assert after["updated_at"] >= created["updated_at"]
        assert after["created_at"] == created["created_at"]

    def test_client_supplied_updated_at_wins(self, tenant):
        """The device clock drives last-write-wins, so the client can set it."""
        created = tenant.post(SEASONS, json=VALID).json()
        stamp = created["updated_at"] + 5000
        r = tenant.patch(f"{SEASONS}/{created['id']}", json={"note": "x", "updated_at": stamp})
        assert r.json()["updated_at"] == stamp

    def test_range_validated_against_stored_values(self, tenant):
        """Sending only end_date must still be checked against the stored start_date."""
        created = tenant.post(SEASONS, json=VALID).json()
        r = tenant.patch(f"{SEASONS}/{created['id']}", json={"end_date": START - 1})
        assert r.status_code == 409

    def test_can_reopen_an_ended_season(self, tenant):
        created = tenant.post(SEASONS, json=VALID).json()
        r = tenant.patch(f"{SEASONS}/{created['id']}", json={"end_date": None, "status": "active"})
        assert r.status_code == 200
        assert r.json()["end_date"] is None

    def test_unknown_id_404(self, tenant):
        assert tenant.patch(f"{SEASONS}/{uuid.uuid4()}", json={"note": "x"}).status_code == 404


@pytest.mark.db
class TestSoftDelete:
    def test_removes_from_listing(self, tenant):
        created = tenant.post(SEASONS, json=VALID).json()
        assert tenant.delete(f"{SEASONS}/{created['id']}").status_code == 200
        assert tenant.get(SEASONS).json()["total"] == 0
        assert tenant.get(f"{SEASONS}/{created['id']}").status_code == 404

    def test_row_survives_as_a_tombstone(self, tenant, db):
        """Rule R3: a hard delete is invisible to a device that was offline."""
        from sqlalchemy import select

        from app.models import Season

        created = tenant.post(SEASONS, json=VALID).json()
        tenant.delete(f"{SEASONS}/{created['id']}")

        row = db.execute(select(Season).where(Season.id == created["id"])).scalar_one()
        assert row.deleted_at is not None

    def test_reports_what_the_cascade_removed(self, tenant):
        created = tenant.post(SEASONS, json=VALID).json()
        body = tenant.delete(f"{SEASONS}/{created['id']}").json()
        assert body["id"] == created["id"]
        assert body["diary_entries_deleted"] == 0
        assert body["stock_transactions_unlinked"] == 0

    def test_delete_is_idempotent_at_the_api_level(self, tenant):
        created = tenant.post(SEASONS, json=VALID).json()
        tenant.delete(f"{SEASONS}/{created['id']}")
        assert tenant.delete(f"{SEASONS}/{created['id']}").status_code == 404

    def test_cursor_bumped_so_the_deletion_syncs(self, tenant, db):
        """The tombstone must be visible to /sync/pull, which means
        server_updated_at has to advance on delete."""
        from sqlalchemy import select

        from app.models import Season

        created = tenant.post(SEASONS, json=VALID).json()
        before = db.execute(
            select(Season.server_updated_at).where(Season.id == created["id"])
        ).scalar_one()

        tenant.delete(f"{SEASONS}/{created['id']}")
        after = db.execute(
            select(Season.server_updated_at).where(Season.id == created["id"])
        ).scalar_one()
        assert after > before

    def test_id_can_be_reused_after_delete(self, tenant):
        """A tombstoned ID stays taken — reusing it would resurrect a deleted
        row on any device that has not yet pulled the tombstone."""
        created = tenant.post(SEASONS, json=VALID).json()
        tenant.delete(f"{SEASONS}/{created['id']}")
        assert tenant.post(SEASONS, json={**VALID, "id": created["id"]}).status_code == 409


@pytest.mark.db
class TestTenantIsolation:
    """Household A must not be able to see or touch household B's data.

    This is the acceptance criterion of Issue #19 and the single most
    important property of the whole API.
    """

    def test_cannot_read_another_households_season(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        theirs = b.post(SEASONS, json=VALID).json()
        assert a.get(f"{SEASONS}/{theirs['id']}").status_code == 404

    def test_cannot_update_another_households_season(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        theirs = b.post(SEASONS, json=VALID).json()
        assert a.patch(f"{SEASONS}/{theirs['id']}", json={"name": "cướp"}).status_code == 404

        assert b.get(f"{SEASONS}/{theirs['id']}").json()["name"] == VALID["name"]

    def test_cannot_delete_another_households_season(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        theirs = b.post(SEASONS, json=VALID).json()
        assert a.delete(f"{SEASONS}/{theirs['id']}").status_code == 404
        assert b.get(f"{SEASONS}/{theirs['id']}").status_code == 200

    def test_404_not_403_so_existence_is_not_confirmed(self, make_tenant):
        """Distinguishing 'not yours' from 'does not exist' confirms an ID
        exists somewhere in the system — a leak across the tenant boundary."""
        a, b = make_tenant(), make_tenant()
        theirs = b.post(SEASONS, json=VALID).json()

        real_but_foreign = a.get(f"{SEASONS}/{theirs['id']}")
        pure_fiction = a.get(f"{SEASONS}/{uuid.uuid4()}")
        assert real_but_foreign.status_code == pure_fiction.status_code == 404
        assert real_but_foreign.json() == pure_fiction.json()

    def test_household_id_cannot_be_forged_in_the_body(self, make_tenant):
        """The tenant comes from the token, never the payload."""
        a, b = make_tenant(), make_tenant()
        r = a.post(SEASONS, json={**VALID, "household_id": b.household_id})
        assert r.status_code == 201
        assert b.get(SEASONS).json()["total"] == 0
        assert a.get(SEASONS).json()["total"] == 1
