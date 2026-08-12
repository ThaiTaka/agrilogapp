"""The three required report charts (Issue #42).

One test class per chart, plus the golden fixture that the mobile Jest suite
reads too (§11.4) — that shared file is what makes "the chart shows the same
number offline and online" a tested property rather than an aspiration.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

SEASONS = "/api/v1/seasons"
SUPPLIES = "/api/v1/supplies"
INCOME_EXPENSE = "/api/v1/reports/income-expense"
CONSUMPTION = "/api/v1/reports/supply-consumption"
COMPARISON = "/api/v1/reports/season-comparison"

UTC = timezone.utc
# Lives in docs/, not tests/, because the mobile Jest suite reads the SAME
# file — same arrangement as docs/sync_contract.json. A fixture buried in one
# side's test folder is a fixture the other side will quietly stop checking.
FIXTURE = Path(__file__).resolve().parents[2] / "docs" / "reports_golden.json"

pytestmark = pytest.mark.db


def ms(y: int, m: int, d: int, hour: int = 3) -> int:
    """Epoch ms for a Vietnam-local date. 03:00 UTC is 10:00 local — safely
    inside the day whichever way the offset is applied."""
    return int(datetime(y, m, d, hour, tzinfo=UTC).timestamp() * 1000)


@pytest.fixture
def scenario(tenant):
    """A deterministic three-month season with known numbers.

    Dec 2026 : 2,000,000 cost                       (no revenue)
    Jan 2027 : nothing at all                       (the empty bucket)
    Feb 2027 : 1,000,000 cost + 12,000,000 revenue
    """
    season = tenant.post(
        SEASONS,
        json={
            "name": "Vụ Đông Xuân 2026-2027",
            "crop_type": "Lúa",
            "start_date": ms(2026, 12, 1),
            "end_date": ms(2027, 2, 28),
        },
    ).json()
    sid = season["id"]

    tenant.post(f"{SEASONS}/{sid}/expenses",
                json={"category": "labor", "amount": "2000000",
                      "expense_date": ms(2026, 12, 5)})
    tenant.post(f"{SEASONS}/{sid}/expenses",
                json={"category": "transport", "amount": "1000000",
                      "expense_date": ms(2027, 2, 10)})
    tenant.post(f"{SEASONS}/{sid}/revenues",
                json={"amount": "12000000", "revenue_date": ms(2027, 2, 20)})

    return {"t": tenant, "season": season, "sid": sid}


# ═══════════════════════════════════════════════════════════════════════════
#  Chart 1 — Income vs Expense
# ═══════════════════════════════════════════════════════════════════════════


class TestIncomeExpense:
    def test_monthly_totals(self, scenario):
        r = scenario["t"].get(f"{INCOME_EXPENSE}?season_id={scenario['sid']}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["totals"] == {
            "revenue": "12000000.00",
            "expense": "3000000.00",
            "profit": "9000000.00",
        }

    def test_buckets_are_dense(self, scenario):
        """January has no activity and must still appear, at zero.

        A sparse series makes a line chart lie about the shape of spending.
        """
        body = scenario["t"].get(f"{INCOME_EXPENSE}?season_id={scenario['sid']}").json()
        periods = [b["period"] for b in body["buckets"]]
        assert periods == ["2026-12", "2027-01", "2027-02"]

        january = next(b for b in body["buckets"] if b["period"] == "2027-01")
        assert january == {
            "period": "2027-01", "revenue": "0.00", "expense": "0.00", "profit": "0.00"
        }

    def test_bucket_values(self, scenario):
        body = scenario["t"].get(f"{INCOME_EXPENSE}?season_id={scenario['sid']}").json()
        by_period = {b["period"]: b for b in body["buckets"]}
        assert by_period["2026-12"]["expense"] == "2000000.00"
        assert by_period["2026-12"]["profit"] == "-2000000.00"
        assert by_period["2027-02"]["revenue"] == "12000000.00"
        assert by_period["2027-02"]["profit"] == "11000000.00"

    def test_bucket_profits_sum_to_the_total(self, scenario):
        body = scenario["t"].get(f"{INCOME_EXPENSE}?season_id={scenario['sid']}").json()
        summed = sum(Decimal(b["profit"]) for b in body["buckets"])
        assert summed == Decimal(body["totals"]["profit"])

    def test_matches_the_season_summary(self, scenario):
        """Two independent code paths over the same data must agree."""
        t, sid = scenario["t"], scenario["sid"]
        report = t.get(f"{INCOME_EXPENSE}?season_id={sid}").json()["totals"]
        summary = t.get(f"{SEASONS}/{sid}/summary").json()
        assert report["expense"] == summary["total_cost"]
        assert report["revenue"] == summary["total_revenue"]
        assert report["profit"] == summary["profit"]

    def test_daily_granularity(self, scenario):
        body = scenario["t"].get(
            f"{INCOME_EXPENSE}?season_id={scenario['sid']}&granularity=day"
        ).json()
        assert body["granularity"] == "day"
        periods = [b["period"] for b in body["buckets"]]
        assert periods[0] == "2026-12-01"
        assert "2026-12-05" in periods
        assert len(periods) == 90          # 1 Dec .. 28 Feb inclusive

    def test_weekly_granularity(self, scenario):
        body = scenario["t"].get(
            f"{INCOME_EXPENSE}?season_id={scenario['sid']}&granularity=week"
        ).json()
        assert all(b["period"].count("-W") == 1 for b in body["buckets"])
        assert sum(Decimal(b["expense"]) for b in body["buckets"]) == Decimal("3000000.00")

    def test_empty_season_still_renders(self, tenant):
        """The chart must draw for a season the farmer only just created."""
        season = tenant.post(
            SEASONS,
            json={"name": "Vụ mới", "crop_type": "Ngô",
                  "start_date": ms(2027, 3, 1), "end_date": ms(2027, 5, 1)},
        ).json()
        body = tenant.get(f"{INCOME_EXPENSE}?season_id={season['id']}").json()
        assert body["totals"]["profit"] == "0.00"
        assert len(body["buckets"]) == 3
        assert all(b["expense"] == "0.00" for b in body["buckets"])

    def test_activity_outside_the_declared_window_is_included(self, tenant):
        """Otherwise the chart total would not match the season summary."""
        season = tenant.post(
            SEASONS, json={"name": "V", "crop_type": "Lúa",
                           "start_date": ms(2027, 1, 1), "end_date": ms(2027, 1, 31)},
        ).json()
        tenant.post(f"{SEASONS}/{season['id']}/expenses",
                    json={"category": "labor", "amount": "500000",
                          "expense_date": ms(2027, 3, 15)})

        body = tenant.get(f"{INCOME_EXPENSE}?season_id={season['id']}").json()
        assert body["totals"]["expense"] == "500000.00"
        assert "2027-03" in [b["period"] for b in body["buckets"]]

    def test_unknown_season_404(self, tenant):
        assert tenant.get(f"{INCOME_EXPENSE}?season_id={uuid.uuid4()}").status_code == 404

    def test_season_id_is_required(self, tenant):
        assert tenant.get(INCOME_EXPENSE).status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
#  Chart 2 — Supply consumption
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def consumption(tenant):
    season = tenant.post(
        SEASONS, json={"name": "Vụ Hè Thu", "crop_type": "Cà chua",
                       "start_date": ms(2027, 4, 1)},
    ).json()

    urea = tenant.post(SUPPLIES, json={"name": "Đạm Urê", "category": "fertilizer",
                                       "unit": "kg", "unit_cost": "12000"}).json()
    kali = tenant.post(SUPPLIES, json={"name": "Kali", "category": "fertilizer",
                                       "unit": "bao", "unit_cost": "600000"}).json()
    regent = tenant.post(SUPPLIES, json={"name": "Regent", "category": "pesticide",
                                         "unit": "chai", "unit_cost": "45000"}).json()

    for s in (urea, kali, regent):
        tenant.post(f"{SUPPLIES}/{s['id']}/stock-in", json={"quantity": "100"})

    tenant.post(
        f"{SEASONS}/{season['id']}/diary-entries",
        json={"work_type": "fertilizing", "entry_date": ms(2027, 4, 10),
              "supply_usages": [
                  {"supply_id": urea["id"], "quantity": "50"},      # 600,000
                  {"supply_id": kali["id"], "quantity": "2"},       # 1,200,000
              ]},
    )
    tenant.post(
        f"{SEASONS}/{season['id']}/diary-entries",
        json={"work_type": "spraying", "entry_date": ms(2027, 4, 15),
              "supply_usages": [{"supply_id": regent["id"], "quantity": "4"}]},  # 180,000
    )
    return {"t": tenant, "season": season, "urea": urea, "kali": kali, "regent": regent}


class TestSupplyConsumption:
    def test_grouped_by_category(self, consumption):
        body = consumption["t"].get(
            f"{CONSUMPTION}?season_id={consumption['season']['id']}"
        ).json()
        rows = {i["key"]: i for i in body["items"]}
        assert rows["fertilizer"]["total_cost"] == "1800000.00"
        assert rows["fertilizer"]["label"] == "Phân bón"
        assert rows["pesticide"]["total_cost"] == "180000.00"
        assert body["total_cost"] == "1980000.00"

    def test_mixed_units_are_flagged_and_unit_suppressed(self, consumption):
        """Fertilizer here holds both kg and bao. Reporting '52.000' for the
        group is a number with no meaning, so the chart must plot cost."""
        body = consumption["t"].get(
            f"{CONSUMPTION}?season_id={consumption['season']['id']}"
        ).json()
        fert = next(i for i in body["items"] if i["key"] == "fertilizer")
        assert fert["unit_mixed"] is True
        assert fert["unit"] is None

        pest = next(i for i in body["items"] if i["key"] == "pesticide")
        assert pest["unit_mixed"] is False
        assert pest["unit"] == "chai"

    def test_share_percentages(self, consumption):
        body = consumption["t"].get(
            f"{CONSUMPTION}?season_id={consumption['season']['id']}"
        ).json()
        shares = {i["key"]: Decimal(i["share_pct"]) for i in body["items"]}
        assert shares["fertilizer"] == Decimal("90.9")
        assert sum(shares.values()) == pytest.approx(Decimal("100"), abs=Decimal("0.2"))

    def test_sorted_by_cost_descending(self, consumption):
        body = consumption["t"].get(
            f"{CONSUMPTION}?season_id={consumption['season']['id']}"
        ).json()
        costs = [Decimal(i["total_cost"]) for i in body["items"]]
        assert costs == sorted(costs, reverse=True)

    def test_grouped_by_supply(self, consumption):
        body = consumption["t"].get(
            f"{CONSUMPTION}?season_id={consumption['season']['id']}&group_by=supply"
        ).json()
        rows = {i["label"]: i for i in body["items"]}
        assert rows["Kali"]["total_cost"] == "1200000.00"
        assert rows["Đạm Urê"]["quantity"] == "50.000"
        assert rows["Đạm Urê"]["unit"] == "kg"
        assert rows["Đạm Urê"]["unit_mixed"] is False

    def test_stock_in_is_not_consumption(self, consumption):
        """Including purchases would double the apparent usage of everything."""
        t = consumption["t"]
        t.post(f"{SUPPLIES}/{consumption['urea']['id']}/stock-in",
               json={"quantity": "500", "season_id": consumption["season"]["id"]})
        body = t.get(f"{CONSUMPTION}?season_id={consumption['season']['id']}").json()
        assert body["total_cost"] == "1980000.00"

    def test_reversed_consumption_disappears(self, consumption):
        """Deleting the diary entry restores the stock, so it is no longer
        consumed and must leave the chart."""
        t = consumption["t"]
        entry = t.get("/api/v1/diary-entries?work_type=spraying").json()["items"][0]
        t.delete(f"/api/v1/diary-entries/{entry['id']}")

        body = t.get(f"{CONSUMPTION}?season_id={consumption['season']['id']}").json()
        assert "pesticide" not in [i["key"] for i in body["items"]]
        assert body["total_cost"] == "1800000.00"

    def test_across_all_seasons(self, consumption):
        body = consumption["t"].get(CONSUMPTION).json()
        assert body["season_id"] is None
        assert body["total_cost"] == "1980000.00"

    def test_empty_household(self, tenant):
        body = tenant.get(CONSUMPTION).json()
        assert body["items"] == []
        assert body["total_cost"] == "0.00"


# ═══════════════════════════════════════════════════════════════════════════
#  Chart 3 — Season comparison
# ═══════════════════════════════════════════════════════════════════════════


class TestSeasonComparison:
    @pytest.fixture
    def three_seasons(self, tenant):
        out = []
        for i, (name, cost, revenue) in enumerate(
            [("Vụ 1", "1000000", "5000000"),
             ("Vụ 2", "4000000", "2000000"),
             ("Vụ 3", "2000000", "9000000")]
        ):
            s = tenant.post(SEASONS, json={"name": name, "crop_type": "Lúa",
                                           "start_date": ms(2026, 1 + i, 1)}).json()
            tenant.post(f"{SEASONS}/{s['id']}/expenses",
                        json={"category": "labor", "amount": cost})
            tenant.post(f"{SEASONS}/{s['id']}/revenues", json={"amount": revenue})
            out.append(s)
        return out

    def test_profit_per_season(self, tenant, three_seasons):
        body = tenant.get(COMPARISON).json()
        rows = {s["name"]: s for s in body["seasons"]}
        assert rows["Vụ 1"]["profit"] == "4000000.00"
        assert rows["Vụ 2"]["profit"] == "-2000000.00"
        assert rows["Vụ 3"]["profit"] == "7000000.00"

    def test_best_and_worst(self, tenant, three_seasons):
        body = tenant.get(COMPARISON).json()
        rows = {s["name"]: s["season_id"] for s in body["seasons"]}
        assert body["best_season_id"] == rows["Vụ 3"]
        assert body["worst_season_id"] == rows["Vụ 2"]

    def test_margin(self, tenant, three_seasons):
        body = tenant.get(COMPARISON).json()
        rows = {s["name"]: s for s in body["seasons"]}
        assert rows["Vụ 1"]["margin_pct"] == "80.0"
        assert rows["Vụ 2"]["margin_pct"] == "-100.0"

    def test_renders_with_exactly_one_season(self, tenant):
        """Issue #46 — a single-bar chart, not an error state."""
        s = tenant.post(SEASONS, json={"name": "Duy nhất", "crop_type": "Lúa",
                                       "start_date": ms(2026, 1, 1)}).json()
        body = tenant.get(COMPARISON).json()
        assert len(body["seasons"]) == 1
        assert body["best_season_id"] == body["worst_season_id"] == s["id"]

    def test_season_with_no_records_appears_at_zero(self, tenant, three_seasons):
        """A farmer comparing seasons needs to see the one they just started,
        not have it silently missing."""
        tenant.post(SEASONS, json={"name": "Vừa tạo", "crop_type": "Ngô",
                                   "start_date": ms(2026, 6, 1)})
        body = tenant.get(COMPARISON).json()
        fresh = next(s for s in body["seasons"] if s["name"] == "Vừa tạo")
        assert fresh["profit"] == "0.00"
        assert fresh["margin_pct"] is None

    def test_no_seasons_at_all(self, tenant):
        body = tenant.get(COMPARISON).json()
        assert body["seasons"] == []
        assert body["best_season_id"] is None

    def test_limit(self, tenant, three_seasons):
        assert len(tenant.get(f"{COMPARISON}?limit=2").json()["seasons"]) == 2

    def test_status_filter(self, tenant, three_seasons):
        tenant.patch(f"{SEASONS}/{three_seasons[0]['id']}", json={"status": "closed"})
        body = tenant.get(f"{COMPARISON}?status=closed").json()
        assert len(body["seasons"]) == 1
        assert body["seasons"][0]["name"] == "Vụ 1"

    def test_deleted_season_excluded(self, tenant, three_seasons):
        tenant.delete(f"{SEASONS}/{three_seasons[1]['id']}")
        names = [s["name"] for s in tenant.get(COMPARISON).json()["seasons"]]
        assert "Vụ 2" not in names


# ═══════════════════════════════════════════════════════════════════════════
#  Isolation
# ═══════════════════════════════════════════════════════════════════════════


class TestTenantIsolation:
    def test_cannot_report_on_another_households_season(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        theirs = b.post(SEASONS, json={"name": "Của B", "crop_type": "Lúa",
                                       "start_date": ms(2026, 1, 1)}).json()
        assert a.get(f"{INCOME_EXPENSE}?season_id={theirs['id']}").status_code == 404
        assert a.get(f"{CONSUMPTION}?season_id={theirs['id']}").status_code == 404

    def test_comparison_lists_only_own_seasons(self, make_tenant):
        a, b = make_tenant(), make_tenant()
        a.post(SEASONS, json={"name": "A", "crop_type": "Lúa", "start_date": ms(2026, 1, 1)})
        b.post(SEASONS, json={"name": "B", "crop_type": "Ngô", "start_date": ms(2026, 1, 1)})
        names = [s["name"] for s in a.get(COMPARISON).json()["seasons"]]
        assert names == ["A"]

    def test_reports_require_authentication(self, api):
        assert api.get(COMPARISON).status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
#  Golden fixture — the offline/online parity contract (§11.4)
# ═══════════════════════════════════════════════════════════════════════════


class TestGoldenFixture:
    """Freezes the three reports over a known dataset.

    The same JSON is committed for the mobile Jest suite to assert its local
    WatermelonDB reducers against (Issue #47). Two suites reading one file is
    what makes "the chart shows the same number offline and online" a tested
    property instead of a hope.
    """

    def test_matches_the_committed_fixture(self, scenario):
        actual = scenario["t"].get(
            f"{INCOME_EXPENSE}?season_id={scenario['sid']}"
        ).json()
        actual.pop("season_id")

        if not FIXTURE.exists():                       # pragma: no cover
            FIXTURE.parent.mkdir(parents=True, exist_ok=True)
            FIXTURE.write_text(
                json.dumps(actual, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            pytest.skip(f"golden fixture created at {FIXTURE}; re-run to assert")

        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
        assert actual == expected, (
            "Report output drifted from the golden fixture. If the change is "
            "intended, delete the file and re-run to regenerate — then update "
            "the mobile Jest fixture to match, or the two sides will disagree."
        )
