"""Supply catalogue and inventory ledger (Issue #23)."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

SUPPLIES = "/api/v1/supplies"
SEASONS = "/api/v1/seasons"

UREA = {
    "name": "Đạm Urê Phú Mỹ",
    "category": "fertilizer",
    "unit": "kg",
    "unit_cost": "12000.00",
    "low_stock_threshold": "20.000",
}


def _in(t, sid, qty, **kw):
    return t.post(f"{SUPPLIES}/{sid}/stock-in", json={"quantity": str(qty), **kw})


def _out(t, sid, qty, **kw):
    return t.post(f"{SUPPLIES}/{sid}/stock-out", json={"quantity": str(qty), **kw})


def _level(t, sid) -> Decimal:
    return Decimal(t.get(f"{SUPPLIES}/{sid}").json()["on_hand"])


# ═══════════════════════════════════════════════════════════════════════════
#  Decimal contract — no database
# ═══════════════════════════════════════════════════════════════════════════


class TestNumericContract:
    def test_float_error_does_not_leak_in(self):
        """Decimal(0.1) is 0.1000000000000000055511151231257827...

        Everything must route through str() first.
        """
        from app.core.numeric import quantize_quantity

        assert quantize_quantity(0.1) == Decimal("0.100")

    def test_the_classic_sum(self):
        """0.1 + 0.2 == 0.30000000000000004 in float. Not here.

        Specified in Data_Requirements_Database.md section 7.1 as a required
        round-trip stability test.
        """
        from app.core.numeric import quantize_quantity

        total = sum(
            (quantize_quantity(x) for x in ("0.1", "0.2", "0.3")), Decimal("0")
        )
        assert total == Decimal("0.600")

    def test_half_up_rounding(self):
        from app.core.numeric import quantize_money, quantize_quantity

        assert quantize_quantity("0.0005") == Decimal("0.001")
        assert quantize_money("0.005") == Decimal("0.01")

    def test_line_total_rounds_once_at_the_end(self):
        from app.core.numeric import line_total

        assert line_total(Decimal("3.333"), Decimal("12000.00")) == Decimal("39996.00")

    def test_rejects_garbage(self):
        from app.core.numeric import quantize_quantity

        with pytest.raises(ValueError, match="Không phải số"):
            quantize_quantity("mười ký")


# ═══════════════════════════════════════════════════════════════════════════
#  Database-backed
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.db
class TestCatalogue:
    def test_create(self, tenant):
        r = tenant.post(SUPPLIES, json=UREA)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["name"] == "Đạm Urê Phú Mỹ"
        assert body["category_label"] == "Phân bón"
        assert body["on_hand"] == "0.000"
        assert body["is_archived"] is False

    def test_new_supply_is_flagged_low_stock(self, tenant):
        """Zero on hand against a threshold of 20 is genuinely low."""
        assert tenant.post(SUPPLIES, json=UREA).json()["is_low_stock"] is True

    def test_zero_threshold_disables_the_flag(self, tenant):
        r = tenant.post(SUPPLIES, json={**UREA, "low_stock_threshold": "0"})
        assert r.json()["is_low_stock"] is False

    def test_duplicate_name_and_unit_conflicts(self, tenant):
        tenant.post(SUPPLIES, json=UREA)
        r = tenant.post(SUPPLIES, json=UREA)
        assert r.status_code == 409
        assert "đã có trong danh mục" in r.json()["detail"]

    def test_duplicate_check_is_case_insensitive(self, tenant):
        tenant.post(SUPPLIES, json=UREA)
        assert tenant.post(SUPPLIES, json={**UREA, "name": "đạm urê phú mỹ"}).status_code == 409

    def test_duplicate_check_survives_a_c_locale_database(self, tenant, db):
        """Regression guard for the locale-dependent lower() bug.

        PostgreSQL folds case per the database collation. Under `C`,
        lower('Đạm Urê Phú Mỹ') returns 'Đạm urê phú mỹ' — the Đ is untouched
        — so an index on lower(name) accepted the same supply twice and the
        service's duplicate check matched nothing. Matching is now on
        `name_key`, folded in Python.
        """
        from sqlalchemy import select

        from app.core.text import normalise_key
        from app.models import Supply

        tenant.post(SUPPLIES, json=UREA)
        stored = db.execute(select(Supply.name_key)).scalar_one()
        assert stored == normalise_key(UREA["name"]) == "đạm urê phú mỹ"

        for variant in ("ĐẠM URÊ PHÚ MỸ", "đạm urê phú mỹ", "  Đạm Urê Phú Mỹ  "):
            assert tenant.post(SUPPLIES, json={**UREA, "name": variant}).status_code == 409

    def test_unicode_composition_is_normalised(self, tenant):
        """'â' arrives as one code point or as 'a' plus a combining circumflex,
        depending on the keyboard and OS the farmer typed it on. Both are the
        same character to a human and must produce the same key.

        The decomposed form is built with unicodedata rather than typed as a
        literal, because an editor would silently re-normalise the source file
        and the test would pass without testing anything.
        """
        import unicodedata

        source = "Ph\u00e2n Kali"                  # '\u00e2' as U+00E2
        precomposed = unicodedata.normalize("NFC", source)
        decomposed = unicodedata.normalize("NFD", source)   # 'a' + U+0302
        assert precomposed != decomposed          # different bytes...
        assert len(decomposed) > len(precomposed)

        tenant.post(SUPPLIES, json={**UREA, "name": precomposed})
        r = tenant.post(SUPPLIES, json={**UREA, "name": decomposed})
        assert r.status_code == 409

    def test_same_name_different_unit_allowed(self, tenant):
        """'Đạm Urê' by the kg and by the bao are two real inventory lines."""
        tenant.post(SUPPLIES, json=UREA)
        assert tenant.post(SUPPLIES, json={**UREA, "unit": "bao"}).status_code == 201

    def test_filter_by_category(self, tenant):
        tenant.post(SUPPLIES, json=UREA)
        tenant.post(SUPPLIES, json={**UREA, "name": "Regent", "category": "pesticide",
                                    "unit": "chai"})
        assert tenant.get(f"{SUPPLIES}?category=pesticide").json()["total"] == 1

    def test_search_by_name(self, tenant):
        tenant.post(SUPPLIES, json=UREA)
        tenant.post(SUPPLIES, json={**UREA, "name": "Kali Clorua", "unit": "bao"})
        assert tenant.get(f"{SUPPLIES}?search=kali").json()["total"] == 1

    def test_update_does_not_touch_history(self, tenant):
        """Changing today's price must not rewrite a closed season's costs."""
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        _in(tenant, sid, "10")
        tenant.patch(f"{SUPPLIES}/{sid}", json={"unit_cost": "99000.00"})

        txn = tenant.get(f"{SUPPLIES}/{sid}/transactions").json()["items"][0]
        assert txn["unit_cost"] == "12000.00"
        assert txn["total_cost"] == "120000.00"

    def test_requires_authentication(self, api):
        assert api.get(SUPPLIES).status_code == 401


@pytest.mark.db
class TestStockLevels:
    def test_in_adds(self, tenant):
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        r = _in(tenant, sid, "50")
        assert r.status_code == 201
        assert r.json()["supply"]["on_hand"] == "50.000"

    def test_out_subtracts(self, tenant):
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        _in(tenant, sid, "50")
        assert _out(tenant, sid, "12.5").json()["supply"]["on_hand"] == "37.500"

    def test_ledger_sums_correctly_over_many_movements(self, tenant):
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        for q in ("10.5", "20.25", "0.125"):
            _in(tenant, sid, q)
        for q in ("5.375", "1.5"):
            _out(tenant, sid, q)
        assert _level(tenant, sid) == Decimal("24.000")

    def test_no_stored_counter_exists(self, tenant, db):
        """D1: on_hand is derived. This asserts nobody adds a cached column."""
        from app.models import Supply

        assert "current_stock" not in Supply.__table__.columns
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        _in(tenant, sid, "50")
        row = db.get(Supply, sid)
        assert not hasattr(row, "current_stock")

    def test_negative_stock_is_allowed_and_flagged(self, tenant):
        """I2: blocking would force the farmer to abandon the usage entry, and
        a missing log is worse than a correctable number."""
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        r = _out(tenant, sid, "5")
        assert r.status_code == 201
        assert r.json()["supply"]["on_hand"] == "-5.000"
        assert r.json()["supply"]["is_negative"] is True

    def test_voiding_a_movement_restores_the_balance(self, tenant):
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        _in(tenant, sid, "50")
        txn = _out(tenant, sid, "20").json()["transaction"]
        assert _level(tenant, sid) == Decimal("30.000")

        r = tenant.delete(f"{SUPPLIES}/{sid}/transactions/{txn['id']}")
        assert r.status_code == 200
        assert r.json()["on_hand"] == "50.000"

    def test_list_reports_levels_without_n_plus_1(self, tenant):
        ids = []
        for i in range(5):
            ids.append(tenant.post(SUPPLIES, json={**UREA, "name": f"VT {i}"}).json()["id"])
        for sid in ids:
            _in(tenant, sid, "7")
        levels = {i["id"]: i["on_hand"] for i in tenant.get(SUPPLIES).json()["items"]}
        assert set(levels.values()) == {"7.000"}

    def test_low_stock_filter(self, tenant):
        low = tenant.post(SUPPLIES, json=UREA).json()["id"]
        ok = tenant.post(SUPPLIES, json={**UREA, "name": "Kali", "unit": "bao"}).json()["id"]
        _in(tenant, low, "5")      # below threshold 20
        _in(tenant, ok, "500")

        body = tenant.get(f"{SUPPLIES}?low_stock_only=true").json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == low


@pytest.mark.db
class TestCostSnapshot:
    def test_defaults_to_the_catalogue_price(self, tenant):
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        txn = _in(tenant, sid, "10").json()["transaction"]
        assert txn["unit_cost"] == "12000.00"
        assert txn["total_cost"] == "120000.00"

    def test_explicit_price_overrides(self, tenant):
        """A real purchase happens at the price actually paid that day."""
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        txn = _in(tenant, sid, "10", unit_cost="13500.00").json()["transaction"]
        assert txn["unit_cost"] == "13500.00"
        assert txn["total_cost"] == "135000.00"

    def test_total_cost_rounds_to_dong(self, tenant):
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        txn = _in(tenant, sid, "3.333", unit_cost="12000.00").json()["transaction"]
        assert txn["total_cost"] == "39996.00"


@pytest.mark.db
class TestStockTake:
    def test_counted_more_than_ledger_creates_a_positive_delta(self, tenant):
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        _in(tenant, sid, "50")
        r = tenant.post(f"{SUPPLIES}/{sid}/stock-take", json={"counted_quantity": "55"})
        assert r.status_code == 200
        assert r.json()["delta"] == "5.000"
        assert r.json()["supply"]["on_hand"] == "55.000"

    def test_counted_less_creates_a_negative_delta(self, tenant):
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        _in(tenant, sid, "50")
        r = tenant.post(f"{SUPPLIES}/{sid}/stock-take", json={"counted_quantity": "42.5"})
        assert r.json()["delta"] == "-7.500"
        assert r.json()["supply"]["on_hand"] == "42.500"

    def test_matching_count_writes_nothing(self, tenant):
        """A no-op row would bump updated_at and manufacture a phantom conflict
        for another device editing the same supply."""
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        _in(tenant, sid, "50")
        r = tenant.post(f"{SUPPLIES}/{sid}/stock-take", json={"counted_quantity": "50"})
        assert r.status_code == 200
        assert r.json()["no_change"] is True
        assert r.json()["transaction"] is None
        assert tenant.get(f"{SUPPLIES}/{sid}/transactions").json()["total"] == 1

    def test_adjustment_appears_in_the_ledger(self, tenant):
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        _in(tenant, sid, "50")
        tenant.post(f"{SUPPLIES}/{sid}/stock-take", json={"counted_quantity": "48"})
        types = [t["txn_type"] for t in tenant.get(f"{SUPPLIES}/{sid}/transactions").json()["items"]]
        assert "adjust" in types


@pytest.mark.db
class TestDeletionAndArchiving:
    def test_unused_supply_can_be_deleted(self, tenant):
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        assert tenant.delete(f"{SUPPLIES}/{sid}").status_code == 204
        assert tenant.get(f"{SUPPLIES}/{sid}").status_code == 404

    def test_supply_with_history_cannot_be_deleted(self, tenant):
        """Tombstoning it would make every device drop the row locally,
        leaving last season's diary entries with a blank supply name."""
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        _in(tenant, sid, "10")
        r = tenant.delete(f"{SUPPLIES}/{sid}")
        assert r.status_code == 409
        assert "lưu trữ" in r.json()["detail"]

    def test_archiving_hides_it_but_keeps_it(self, tenant):
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        _in(tenant, sid, "10")
        tenant.patch(f"{SUPPLIES}/{sid}", json={"is_archived": True})

        assert tenant.get(SUPPLIES).json()["total"] == 0
        assert tenant.get(f"{SUPPLIES}?include_archived=true").json()["total"] == 1
        assert tenant.get(f"{SUPPLIES}/{sid}").status_code == 200

    def test_archived_supply_keeps_its_ledger(self, tenant):
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        _in(tenant, sid, "10")
        tenant.patch(f"{SUPPLIES}/{sid}", json={"is_archived": True})
        assert tenant.get(f"{SUPPLIES}/{sid}/transactions").json()["total"] == 1

    def test_archived_supply_can_be_restored(self, tenant):
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        tenant.patch(f"{SUPPLIES}/{sid}", json={"is_archived": True})
        tenant.patch(f"{SUPPLIES}/{sid}", json={"is_archived": False})
        assert tenant.get(SUPPLIES).json()["total"] == 1


@pytest.mark.db
class TestSeasonAllocation:
    def test_movement_can_be_allocated_to_a_season(self, tenant):
        season = tenant.post(
            SEASONS, json={"name": "Vụ Mùa", "crop_type": "Lúa", "start_date": 1786665600000}
        ).json()
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        txn = _in(tenant, sid, "10", season_id=season["id"]).json()["transaction"]
        assert txn["season_id"] == season["id"]

    def test_unknown_season_404(self, tenant):
        sid = tenant.post(SUPPLIES, json=UREA).json()["id"]
        assert _in(tenant, sid, "10", season_id=str(uuid.uuid4())).status_code == 404

    def test_cannot_allocate_to_another_households_season(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        theirs = b.post(
            SEASONS, json={"name": "Của B", "crop_type": "Lúa", "start_date": 1786665600000}
        ).json()
        sid = a.post(SUPPLIES, json=UREA).json()["id"]
        assert _in(a, sid, "10", season_id=theirs["id"]).status_code == 404


@pytest.mark.db
class TestTenantIsolation:
    def test_levels_are_per_household(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        a_id = a.post(SUPPLIES, json=UREA).json()["id"]
        b_id = b.post(SUPPLIES, json=UREA).json()["id"]
        _in(a, a_id, "100")
        _in(b, b_id, "7")
        assert _level(a, a_id) == Decimal("100.000")
        assert _level(b, b_id) == Decimal("7.000")

    def test_cannot_read_another_households_supply(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        theirs = b.post(SUPPLIES, json=UREA).json()["id"]
        assert a.get(f"{SUPPLIES}/{theirs}").status_code == 404

    def test_cannot_move_stock_on_another_households_supply(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        theirs = b.post(SUPPLIES, json=UREA).json()["id"]
        assert _in(a, theirs, "999").status_code == 404
        assert _level(b, theirs) == Decimal("0.000")

    def test_cannot_void_another_households_transaction(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        theirs = b.post(SUPPLIES, json=UREA).json()["id"]
        txn = _in(b, theirs, "10").json()["transaction"]
        mine = a.post(SUPPLIES, json=UREA).json()["id"]
        assert a.delete(f"{SUPPLIES}/{mine}/transactions/{txn['id']}").status_code == 404
        assert _level(b, theirs) == Decimal("10.000")
