"""Income, expense and season summary (Issue #27)."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

SEASONS = "/api/v1/seasons"
SUPPLIES = "/api/v1/supplies"
DIARY = "/api/v1/diary-entries"
EXPENSES = "/api/v1/expenses"
REVENUES = "/api/v1/revenues"

START = 1786665600000
DATE = 1786752000000


# ═══════════════════════════════════════════════════════════════════════════
#  Schema — no database
# ═══════════════════════════════════════════════════════════════════════════


class TestRevenueSchema:
    def test_amount_derived_from_quantity_and_price(self):
        from app.schemas.finance import RevenueCreate

        r = RevenueCreate(quantity="1250", unit="kg", unit_price="8500")
        assert r.amount == Decimal("10625000")

    def test_explicit_amount_wins_over_the_product(self):
        """Real sales get rounded down, discounted for moisture, or partly
        paid. The number the farmer received beats the arithmetic."""
        from app.schemas.finance import RevenueCreate

        r = RevenueCreate(quantity="1250", unit="kg", unit_price="8500", amount="10000000")
        assert r.amount == Decimal("10000000")

    def test_amount_required_when_it_cannot_be_derived(self):
        from pydantic import ValidationError

        from app.schemas.finance import RevenueCreate

        with pytest.raises(ValidationError, match="amount"):
            RevenueCreate(quantity="1250", unit="kg")

    def test_unknown_unit_rejected(self):
        from pydantic import ValidationError

        from app.schemas.finance import RevenueCreate

        with pytest.raises(ValidationError, match="Đơn vị"):
            RevenueCreate(amount="1000", unit="pound")

    def test_negative_amount_rejected(self):
        from pydantic import ValidationError

        from app.schemas.finance import ExpenseCreate

        with pytest.raises(ValidationError):
            ExpenseCreate(amount="-1")


# ═══════════════════════════════════════════════════════════════════════════
#  Database-backed
# ═══════════════════════════════════════════════════════════════════════════

pytestmark_db = pytest.mark.db


@pytest.fixture
def season(tenant):
    return tenant.post(
        SEASONS, json={"name": "Vụ Đông Xuân 2026", "crop_type": "Lúa", "start_date": START}
    ).json()


@pytest.fixture
def farm(tenant, season):
    urea = tenant.post(
        SUPPLIES,
        json={"name": "Đạm Urê", "category": "fertilizer", "unit": "kg",
              "unit_cost": "12000.00"},
    ).json()
    tenant.post(f"{SUPPLIES}/{urea['id']}/stock-in", json={"quantity": "100"})
    return {"t": tenant, "season": season, "urea": urea}


@pytest.mark.db
class TestExpenseCrud:
    def test_create(self, tenant, season):
        r = tenant.post(
            f"{SEASONS}/{season['id']}/expenses",
            json={"category": "labor", "amount": "1500000", "expense_date": DATE,
                  "description": "Thuê 3 công cấy"},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["amount"] == "1500000.00"
        assert body["category_label"] == "Nhân công"
        assert body["source"] == "manual"
        assert body["is_editable"] is True
        assert body["stock_transaction_id"] is None

    def test_source_cannot_be_forged(self, tenant, season):
        """Only the diary generator may write diary_auto. A forged one would
        be a cost with no movement behind it, impossible to reconcile."""
        r = tenant.post(
            f"{SEASONS}/{season['id']}/expenses",
            json={"category": "supply", "amount": "999", "source": "diary_auto"},
        )
        assert r.status_code == 201
        assert r.json()["source"] == "manual"

    def test_update(self, tenant, season):
        e = tenant.post(
            f"{SEASONS}/{season['id']}/expenses", json={"category": "labor", "amount": "100"}
        ).json()
        r = tenant.patch(f"{EXPENSES}/{e['id']}", json={"amount": "250", "category": "transport"})
        assert r.status_code == 200
        assert r.json()["amount"] == "250.00"
        assert r.json()["category"] == "transport"

    def test_soft_delete(self, tenant, season):
        e = tenant.post(
            f"{SEASONS}/{season['id']}/expenses", json={"category": "labor", "amount": "100"}
        ).json()
        assert tenant.delete(f"{EXPENSES}/{e['id']}").status_code == 204
        assert tenant.get(f"{EXPENSES}/{e['id']}").status_code == 404

    def test_filter_by_category(self, tenant, season):
        for cat in ("labor", "transport", "labor"):
            tenant.post(f"{SEASONS}/{season['id']}/expenses",
                        json={"category": cat, "amount": "100"})
        assert tenant.get(f"{EXPENSES}?category=labor").json()["total"] == 2

    def test_unknown_season_404(self, tenant):
        r = tenant.post(f"{SEASONS}/{uuid.uuid4()}/expenses", json={"amount": "100"})
        assert r.status_code == 404


@pytest.mark.db
class TestAutoExpenseIsReadOnly:
    """D7 — a hand-edited derived value diverges from its generator with no
    reconciliation path."""

    @pytest.fixture
    def auto_expense(self, farm):
        farm["t"].post(
            f"{SEASONS}/{farm['season']['id']}/diary-entries",
            json={
                "work_type": "fertilizing",
                "entry_date": DATE,
                "supply_usages": [{"supply_id": farm["urea"]["id"], "quantity": "25"}],
            },
        )
        rows = farm["t"].get(f"{EXPENSES}?source=diary_auto").json()["items"]
        assert len(rows) == 1
        return rows[0]

    def test_it_appears_by_itself(self, auto_expense):
        assert auto_expense["amount"] == "300000.00"
        assert auto_expense["category"] == "supply"
        assert auto_expense["stock_transaction_id"] is not None

    def test_flagged_not_editable(self, auto_expense):
        assert auto_expense["is_editable"] is False

    def test_patch_rejected(self, farm, auto_expense):
        r = farm["t"].patch(f"{EXPENSES}/{auto_expense['id']}", json={"amount": "1"})
        assert r.status_code == 409
        assert "nhật ký canh tác" in r.json()["detail"]

    def test_delete_rejected(self, farm, auto_expense):
        r = farm["t"].delete(f"{EXPENSES}/{auto_expense['id']}")
        assert r.status_code == 409

    def test_amount_survives_the_rejected_edit(self, farm, auto_expense):
        farm["t"].patch(f"{EXPENSES}/{auto_expense['id']}", json={"amount": "1"})
        assert farm["t"].get(f"{EXPENSES}/{auto_expense['id']}").json()["amount"] == "300000.00"

    def test_editing_the_diary_entry_does_change_it(self, farm, auto_expense):
        """The supported path."""
        entry = farm["t"].get(DIARY).json()["items"][0]
        farm["t"].patch(
            f"{DIARY}/{entry['id']}",
            json={"supply_usages": [{"supply_id": farm["urea"]["id"], "quantity": "10"}]},
        )
        assert farm["t"].get(f"{EXPENSES}/{auto_expense['id']}").json()["amount"] == "120000.00"


@pytest.mark.db
class TestRevenueCrud:
    def test_create_with_quantity_and_price(self, tenant, season):
        r = tenant.post(
            f"{SEASONS}/{season['id']}/revenues",
            json={"quantity": "1250", "unit": "kg", "unit_price": "8500",
                  "revenue_date": DATE, "buyer": "Thương lái Sáu Tâm"},
        )
        assert r.status_code == 201, r.text
        assert r.json()["amount"] == "10625000.00"

    def test_create_with_amount_only(self, tenant, season):
        r = tenant.post(f"{SEASONS}/{season['id']}/revenues", json={"amount": "5000000"})
        assert r.status_code == 201
        assert r.json()["quantity"] is None

    def test_amount_recomputed_when_price_changes(self, tenant, season):
        rev = tenant.post(
            f"{SEASONS}/{season['id']}/revenues",
            json={"quantity": "1000", "unit": "kg", "unit_price": "8000"},
        ).json()
        r = tenant.patch(f"{REVENUES}/{rev['id']}", json={"unit_price": "9000"})
        assert r.json()["amount"] == "9000000.00"

    def test_explicit_amount_is_not_overwritten(self, tenant, season):
        """The farmer restating the total means they were paid that."""
        rev = tenant.post(
            f"{SEASONS}/{season['id']}/revenues",
            json={"quantity": "1000", "unit": "kg", "unit_price": "8000"},
        ).json()
        r = tenant.patch(
            f"{REVENUES}/{rev['id']}", json={"unit_price": "9000", "amount": "8500000"}
        )
        assert r.json()["amount"] == "8500000.00"

    def test_soft_delete(self, tenant, season):
        rev = tenant.post(f"{SEASONS}/{season['id']}/revenues", json={"amount": "100"}).json()
        assert tenant.delete(f"{REVENUES}/{rev['id']}").status_code == 204
        assert tenant.get(f"{REVENUES}/{rev['id']}").status_code == 404


@pytest.mark.db
class TestSeasonSummary:
    def test_empty_season(self, tenant, season):
        s = tenant.get(f"{SEASONS}/{season['id']}/summary").json()
        assert s["total_cost"] == "0.00"
        assert s["total_revenue"] == "0.00"
        assert s["profit"] == "0.00"
        assert s["margin_pct"] is None          # no revenue -> no margin, not 0
        assert s["cost_by_category"] == []

    def test_profit_is_revenue_minus_cost(self, tenant, season):
        tenant.post(f"{SEASONS}/{season['id']}/expenses",
                    json={"category": "labor", "amount": "3000000"})
        tenant.post(f"{SEASONS}/{season['id']}/revenues", json={"amount": "10000000"})

        s = tenant.get(f"{SEASONS}/{season['id']}/summary").json()
        assert s["total_cost"] == "3000000.00"
        assert s["total_revenue"] == "10000000.00"
        assert s["profit"] == "7000000.00"
        assert s["margin_pct"] == "70.0"

    def test_loss_making_season(self, tenant, season):
        tenant.post(f"{SEASONS}/{season['id']}/expenses",
                    json={"category": "labor", "amount": "5000000"})
        tenant.post(f"{SEASONS}/{season['id']}/revenues", json={"amount": "2000000"})
        s = tenant.get(f"{SEASONS}/{season['id']}/summary").json()
        assert s["profit"] == "-3000000.00"

    def test_supply_cost_included_without_double_counting(self, farm):
        """I9 — consumption is already a diary_auto expense, so there is no
        separate 'add supply costs' step."""
        t, season = farm["t"], farm["season"]
        t.post(
            f"{SEASONS}/{season['id']}/diary-entries",
            json={"work_type": "fertilizing", "entry_date": DATE,
                  "supply_usages": [{"supply_id": farm["urea"]["id"], "quantity": "25"}]},
        )
        t.post(f"{SEASONS}/{season['id']}/expenses",
               json={"category": "labor", "amount": "500000"})

        s = t.get(f"{SEASONS}/{season['id']}/summary").json()
        assert s["total_cost"] == "800000.00"        # 300k auto + 500k manual, once
        assert s["auto_generated_cost"] == "300000.00"
        assert s["manual_cost"] == "500000.00"
        assert s["expense_count"] == 2

    def test_cost_breakdown_by_category(self, tenant, season):
        for cat, amt in (("labor", "600000"), ("transport", "300000"), ("labor", "100000")):
            tenant.post(f"{SEASONS}/{season['id']}/expenses",
                        json={"category": cat, "amount": amt})

        s = tenant.get(f"{SEASONS}/{season['id']}/summary").json()
        rows = {r["category"]: r for r in s["cost_by_category"]}
        assert rows["labor"]["amount"] == "700000.00"
        assert rows["labor"]["label"] == "Nhân công"
        assert rows["labor"]["share_pct"] == "70.0"
        assert rows["transport"]["share_pct"] == "30.0"

    def test_breakdown_sorted_by_amount(self, tenant, season):
        for cat, amt in (("labor", "100"), ("transport", "900"), ("machinery", "500")):
            tenant.post(f"{SEASONS}/{season['id']}/expenses",
                        json={"category": cat, "amount": amt})
        cats = [r["category"] for r in
                tenant.get(f"{SEASONS}/{season['id']}/summary").json()["cost_by_category"]]
        assert cats == ["transport", "machinery", "labor"]

    def test_deleting_a_diary_entry_updates_the_summary(self, farm):
        """The whole chain: entry -> movement -> expense -> season total."""
        t, season = farm["t"], farm["season"]
        entry = t.post(
            f"{SEASONS}/{season['id']}/diary-entries",
            json={"work_type": "fertilizing", "entry_date": DATE,
                  "supply_usages": [{"supply_id": farm["urea"]["id"], "quantity": "25"}]},
        ).json()
        assert t.get(f"{SEASONS}/{season['id']}/summary").json()["total_cost"] == "300000.00"

        t.delete(f"{DIARY}/{entry['id']}")
        assert t.get(f"{SEASONS}/{season['id']}/summary").json()["total_cost"] == "0.00"

    def test_soft_deleted_records_are_excluded(self, tenant, season):
        e = tenant.post(f"{SEASONS}/{season['id']}/expenses",
                        json={"category": "labor", "amount": "1000"}).json()
        tenant.delete(f"{EXPENSES}/{e['id']}")
        assert tenant.get(f"{SEASONS}/{season['id']}/summary").json()["total_cost"] == "0.00"

    def test_unknown_season_404(self, tenant):
        assert tenant.get(f"{SEASONS}/{uuid.uuid4()}/summary").status_code == 404


@pytest.mark.db
class TestTenantIsolation:
    def test_summary_counts_only_this_household(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        sa = a.post(SEASONS, json={"name": "A", "crop_type": "Lúa",
                                   "start_date": START}).json()
        sb = b.post(SEASONS, json={"name": "B", "crop_type": "Lúa",
                                   "start_date": START}).json()
        a.post(f"{SEASONS}/{sa['id']}/expenses", json={"category": "labor", "amount": "100"})
        b.post(f"{SEASONS}/{sb['id']}/expenses", json={"category": "labor", "amount": "999999"})

        assert a.get(f"{SEASONS}/{sa['id']}/summary").json()["total_cost"] == "100.00"

    def test_cannot_read_another_households_expense(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        sb = b.post(SEASONS, json={"name": "B", "crop_type": "Lúa",
                                   "start_date": START}).json()
        theirs = b.post(f"{SEASONS}/{sb['id']}/expenses",
                        json={"category": "labor", "amount": "100"}).json()
        assert a.get(f"{EXPENSES}/{theirs['id']}").status_code == 404
        assert a.patch(f"{EXPENSES}/{theirs['id']}", json={"amount": "1"}).status_code == 404
        assert a.delete(f"{EXPENSES}/{theirs['id']}").status_code == 404

    def test_cannot_read_another_households_summary(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        sb = b.post(SEASONS, json={"name": "B", "crop_type": "Lúa",
                                   "start_date": START}).json()
        assert a.get(f"{SEASONS}/{sb['id']}/summary").status_code == 404
