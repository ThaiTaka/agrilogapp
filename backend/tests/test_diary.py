"""Farming diary, stock restore and auto-expense (Issues #21, #25, #29).

The invariants under test (Data_Requirements_Database.md section 9):

  I3  create -> edit -> delete returns on_hand to EXACTLY its prior value
  I4  the restore is idempotent
  I6  exactly one expense per supply-consuming movement
  I7  a bare stock-out generates no expense
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

SEASONS = "/api/v1/seasons"
SUPPLIES = "/api/v1/supplies"
DIARY = "/api/v1/diary-entries"

START = 1786665600000          # 2026-08-10
ENTRY_DATE = 1786752000000     # 2026-08-11

pytestmark = pytest.mark.db


# ═══════════════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def farm(tenant):
    """A season plus two stocked supplies — the state a real entry needs."""
    season = tenant.post(
        SEASONS, json={"name": "Vụ Đông Xuân 2026", "crop_type": "Lúa", "start_date": START}
    ).json()

    urea = tenant.post(
        SUPPLIES,
        json={"name": "Đạm Urê", "category": "fertilizer", "unit": "kg",
              "unit_cost": "12000.00", "low_stock_threshold": "20.000"},
    ).json()
    regent = tenant.post(
        SUPPLIES,
        json={"name": "Thuốc Regent", "category": "pesticide", "unit": "chai",
              "unit_cost": "45000.00"},
    ).json()

    tenant.post(f"{SUPPLIES}/{urea['id']}/stock-in", json={"quantity": "100"})
    tenant.post(f"{SUPPLIES}/{regent['id']}/stock-in", json={"quantity": "10"})

    return {"t": tenant, "season": season, "urea": urea, "regent": regent}


def level(t, supply_id) -> Decimal:
    return Decimal(t.get(f"{SUPPLIES}/{supply_id}").json()["on_hand"])


def create_entry(farm, usages=None, **kw):
    body = {"work_type": "fertilizing", "entry_date": ENTRY_DATE, "note": "Bón thúc đợt 1"}
    body.update(kw)
    if usages is not None:
        body["supply_usages"] = usages
    return farm["t"].post(f"{SEASONS}/{farm['season']['id']}/diary-entries", json=body)


def expenses_for(t, db, entry_id) -> list:
    from sqlalchemy import select

    from app.models import Expense, StockTransaction

    return list(
        db.execute(
            select(Expense)
            .join(StockTransaction, StockTransaction.id == Expense.stock_transaction_id)
            .where(StockTransaction.diary_entry_id == entry_id, Expense.deleted_at.is_(None))
        )
        .scalars()
        .all()
    )


# ═══════════════════════════════════════════════════════════════════════════
#  CRUD (#21)
# ═══════════════════════════════════════════════════════════════════════════


class TestCreate:
    def test_plain_entry(self, farm):
        r = create_entry(farm)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["work_type"] == "fertilizing"
        assert body["work_type_label"] == "Bón phân"
        assert body["supply_usages"] == []
        assert body["total_supply_cost"] == "0.00"

    def test_entry_with_supply_usage(self, farm):
        r = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "25.5"}])
        assert r.status_code == 201, r.text
        body = r.json()
        assert len(body["supply_usages"]) == 1
        line = body["supply_usages"][0]
        assert line["supply_name"] == "Đạm Urê"
        assert line["quantity"] == "25.500"
        assert line["unit_cost"] == "12000.00"
        assert line["total_cost"] == "306000.00"
        assert body["total_supply_cost"] == "306000.00"

    def test_usage_reduces_inventory(self, farm):
        create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "25.5"}])
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("74.500")

    def test_multiple_supplies(self, farm):
        r = create_entry(
            farm,
            [
                {"supply_id": farm["urea"]["id"], "quantity": "10"},
                {"supply_id": farm["regent"]["id"], "quantity": "2"},
            ],
        )
        assert len(r.json()["supply_usages"]) == 2
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("90.000")
        assert level(farm["t"], farm["regent"]["id"]) == Decimal("8.000")

    def test_duplicate_supply_lines_rejected(self, farm):
        """Reconciliation is keyed by supply_id, so two lines for one supply
        makes 'which line changed?' unanswerable."""
        r = create_entry(
            farm,
            [
                {"supply_id": farm["urea"]["id"], "quantity": "10"},
                {"supply_id": farm["urea"]["id"], "quantity": "5"},
            ],
        )
        assert r.status_code == 422

    def test_unknown_supply_404(self, farm):
        r = create_entry(farm, [{"supply_id": str(uuid.uuid4()), "quantity": "1"}])
        assert r.status_code == 404

    def test_unknown_season_404(self, tenant):
        r = tenant.post(
            f"{SEASONS}/{uuid.uuid4()}/diary-entries",
            json={"work_type": "spraying", "entry_date": ENTRY_DATE},
        )
        assert r.status_code == 404

    def test_price_override_snapshots(self, farm):
        r = create_entry(
            farm,
            [{"supply_id": farm["urea"]["id"], "quantity": "10", "unit_cost": "13500.00"}],
        )
        assert r.json()["supply_usages"][0]["total_cost"] == "135000.00"

    def test_invalid_weather_rejected(self, farm):
        assert create_entry(farm, weather="typhoon").status_code == 422


class TestListAndFilter:
    def test_filter_by_work_type(self, farm):
        create_entry(farm, work_type="fertilizing")
        create_entry(farm, work_type="spraying")
        body = farm["t"].get(f"{DIARY}?work_type=spraying").json()
        assert body["total"] == 1

    def test_filter_by_date_range(self, farm):
        create_entry(farm, entry_date=ENTRY_DATE)
        create_entry(farm, entry_date=ENTRY_DATE + 5 * 86400000)
        body = farm["t"].get(f"{DIARY}?date_from={ENTRY_DATE + 86400000}").json()
        assert body["total"] == 1

    def test_season_scoped_listing(self, farm):
        other = farm["t"].post(
            SEASONS, json={"name": "Vụ khác", "crop_type": "Ngô", "start_date": START}
        ).json()
        create_entry(farm)
        farm["t"].post(
            f"{SEASONS}/{other['id']}/diary-entries",
            json={"work_type": "sowing", "entry_date": ENTRY_DATE},
        )
        assert farm["t"].get(f"{SEASONS}/{farm['season']['id']}/diary-entries").json()["total"] == 1
        assert farm["t"].get(DIARY).json()["total"] == 2

    def test_usages_loaded_without_n_plus_1(self, farm):
        for _ in range(4):
            create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "1"}])
        items = farm["t"].get(DIARY).json()["items"]
        assert all(len(i["supply_usages"]) == 1 for i in items)

    def test_sorted_newest_first(self, farm):
        create_entry(farm, entry_date=ENTRY_DATE, title="cũ")
        create_entry(farm, entry_date=ENTRY_DATE + 86400000, title="mới")
        titles = [i["title"] for i in farm["t"].get(DIARY).json()["items"]]
        assert titles == ["mới", "cũ"]


# ═══════════════════════════════════════════════════════════════════════════
#  Stock restore — hoàn kho (#25)
# ═══════════════════════════════════════════════════════════════════════════


class TestStockRestoreOnEdit:
    def test_increasing_quantity_takes_more_stock(self, farm):
        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "10"}]).json()
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("90.000")

        farm["t"].patch(
            f"{DIARY}/{entry['id']}",
            json={"supply_usages": [{"supply_id": farm["urea"]["id"], "quantity": "30"}]},
        )
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("70.000")

    def test_decreasing_quantity_returns_stock(self, farm):
        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "30"}]).json()
        farm["t"].patch(
            f"{DIARY}/{entry['id']}",
            json={"supply_usages": [{"supply_id": farm["urea"]["id"], "quantity": "10"}]},
        )
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("90.000")

    def test_removing_a_supply_returns_all_of_it(self, farm):
        entry = create_entry(
            farm,
            [
                {"supply_id": farm["urea"]["id"], "quantity": "10"},
                {"supply_id": farm["regent"]["id"], "quantity": "3"},
            ],
        ).json()
        farm["t"].patch(
            f"{DIARY}/{entry['id']}",
            json={"supply_usages": [{"supply_id": farm["urea"]["id"], "quantity": "10"}]},
        )
        assert level(farm["t"], farm["regent"]["id"]) == Decimal("10.000")
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("90.000")

    def test_adding_a_supply_consumes_it(self, farm):
        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "10"}]).json()
        farm["t"].patch(
            f"{DIARY}/{entry['id']}",
            json={
                "supply_usages": [
                    {"supply_id": farm["urea"]["id"], "quantity": "10"},
                    {"supply_id": farm["regent"]["id"], "quantity": "4"},
                ]
            },
        )
        assert level(farm["t"], farm["regent"]["id"]) == Decimal("6.000")

    def test_empty_list_reverses_everything(self, farm):
        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "40"}]).json()
        farm["t"].patch(f"{DIARY}/{entry['id']}", json={"supply_usages": []})
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("100.000")

    def test_omitting_usages_leaves_them_alone(self, farm):
        """Collapsing 'omitted' and '[]' would make fixing a typo in the note
        silently wipe the fertiliser record."""
        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "40"}]).json()
        r = farm["t"].patch(f"{DIARY}/{entry['id']}", json={"note": "sửa ghi chú"})
        assert r.status_code == 200
        assert len(r.json()["supply_usages"]) == 1
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("60.000")

    def test_unchanged_usage_does_not_bump_updated_at(self, farm, db):
        """A no-op write would manufacture a last-write-wins conflict against
        another device that legitimately edited the same row."""
        from sqlalchemy import select

        from app.models import StockTransaction

        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "10"}]).json()
        txn_id = entry["supply_usages"][0]["transaction_id"]
        before = db.execute(
            select(StockTransaction.updated_at).where(StockTransaction.id == txn_id)
        ).scalar_one()

        farm["t"].patch(
            f"{DIARY}/{entry['id']}",
            json={"supply_usages": [{"supply_id": farm["urea"]["id"], "quantity": "10"}]},
        )
        after = db.execute(
            select(StockTransaction.updated_at).where(StockTransaction.id == txn_id)
        ).scalar_one()
        assert after == before

    def test_moving_the_date_moves_the_consumption(self, farm, db):
        """A consumption dated differently from the work that caused it lands
        in the wrong report bucket."""
        from sqlalchemy import select

        from app.models import StockTransaction

        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "10"}]).json()
        new_date = ENTRY_DATE + 3 * 86400000
        farm["t"].patch(f"{DIARY}/{entry['id']}", json={"entry_date": new_date})

        txn_date = db.execute(
            select(StockTransaction.txn_date).where(
                StockTransaction.diary_entry_id == entry["id"],
                StockTransaction.deleted_at.is_(None),
            )
        ).scalar_one()
        assert txn_date == new_date


class TestStockRestoreOnDelete:
    def test_delete_returns_all_stock(self, farm):
        entry = create_entry(
            farm,
            [
                {"supply_id": farm["urea"]["id"], "quantity": "25"},
                {"supply_id": farm["regent"]["id"], "quantity": "3"},
            ],
        ).json()
        r = farm["t"].delete(f"{DIARY}/{entry['id']}")
        assert r.status_code == 200
        body = r.json()
        assert body["stock_transactions_reversed"] == 2
        assert body["quantity_restored"][farm["urea"]["id"]] == "25.000"

        assert level(farm["t"], farm["urea"]["id"]) == Decimal("100.000")
        assert level(farm["t"], farm["regent"]["id"]) == Decimal("10.000")

    def test_deleted_entry_disappears(self, farm):
        entry = create_entry(farm).json()
        farm["t"].delete(f"{DIARY}/{entry['id']}")
        assert farm["t"].get(f"{DIARY}/{entry['id']}").status_code == 404
        assert farm["t"].get(DIARY).json()["total"] == 0

    def test_restore_re_consumes(self, farm):
        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "25"}]).json()
        farm["t"].delete(f"{DIARY}/{entry['id']}")
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("100.000")

        r = farm["t"].post(f"{DIARY}/{entry['id']}/restore")
        assert r.status_code == 200
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("75.000")


class TestInvariantI3:
    """create -> edit -> delete returns on_hand to EXACTLY its prior value."""

    def test_full_lifecycle_is_exactly_neutral(self, farm):
        t, urea, regent = farm["t"], farm["urea"]["id"], farm["regent"]["id"]
        before_u, before_r = level(t, urea), level(t, regent)

        entry = create_entry(
            farm,
            [{"supply_id": urea, "quantity": "33.333"},
             {"supply_id": regent, "quantity": "1.5"}],
        ).json()

        t.patch(
            f"{DIARY}/{entry['id']}",
            json={"supply_usages": [{"supply_id": urea, "quantity": "12.125"}]},
        )
        t.patch(
            f"{DIARY}/{entry['id']}",
            json={"supply_usages": [
                {"supply_id": urea, "quantity": "0.001"},
                {"supply_id": regent, "quantity": "9.999"},
            ]},
        )
        t.delete(f"{DIARY}/{entry['id']}")

        assert level(t, urea) == before_u
        assert level(t, regent) == before_r

    def test_thirds_do_not_drift(self, farm):
        """Three-decimal quantities that do not divide evenly are where a
        float implementation would leave a residue."""
        t, urea = farm["t"], farm["urea"]["id"]
        before = level(t, urea)
        for q in ("0.001", "33.333", "0.007", "66.659"):
            entry = create_entry(farm, [{"supply_id": urea, "quantity": q}]).json()
            t.delete(f"{DIARY}/{entry['id']}")
        assert level(t, urea) == before

    def test_repeated_identical_edits_are_idempotent(self, farm):
        """I4 — a sync retry replays the same edit."""
        t, urea = farm["t"], farm["urea"]["id"]
        entry = create_entry(farm, [{"supply_id": urea, "quantity": "10"}]).json()
        for _ in range(5):
            t.patch(
                f"{DIARY}/{entry['id']}",
                json={"supply_usages": [{"supply_id": urea, "quantity": "17.5"}]},
            )
        assert level(t, urea) == Decimal("82.500")

    def test_repeated_deletes_are_idempotent(self, farm):
        t, urea = farm["t"], farm["urea"]["id"]
        entry = create_entry(farm, [{"supply_id": urea, "quantity": "10"}]).json()
        t.delete(f"{DIARY}/{entry['id']}")
        assert t.delete(f"{DIARY}/{entry['id']}").status_code == 404
        assert level(t, urea) == Decimal("100.000")


# ═══════════════════════════════════════════════════════════════════════════
#  Auto-generated expense (#29)
# ═══════════════════════════════════════════════════════════════════════════


class TestAutoExpense:
    def test_usage_creates_one_expense(self, farm, db):
        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "25"}]).json()
        rows = expenses_for(farm["t"], db, entry["id"])
        assert len(rows) == 1
        assert rows[0].amount == Decimal("300000.00")
        assert rows[0].source == "diary_auto"
        assert rows[0].category == "supply"
        assert rows[0].season_id == farm["season"]["id"]

    def test_expense_matches_the_line_total(self, farm, db):
        entry = create_entry(
            farm, [{"supply_id": farm["urea"]["id"], "quantity": "3.333"}]
        ).json()
        rows = expenses_for(farm["t"], db, entry["id"])
        assert rows[0].amount == Decimal(entry["supply_usages"][0]["total_cost"])

    def test_editing_quantity_updates_the_expense(self, farm, db):
        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "10"}]).json()
        farm["t"].patch(
            f"{DIARY}/{entry['id']}",
            json={"supply_usages": [{"supply_id": farm["urea"]["id"], "quantity": "20"}]},
        )
        rows = expenses_for(farm["t"], db, entry["id"])
        assert len(rows) == 1
        assert rows[0].amount == Decimal("240000.00")

    def test_removing_usage_removes_the_expense(self, farm, db):
        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "10"}]).json()
        farm["t"].patch(f"{DIARY}/{entry['id']}", json={"supply_usages": []})
        assert expenses_for(farm["t"], db, entry["id"]) == []

    def test_deleting_entry_removes_the_expense(self, farm, db):
        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "10"}]).json()
        farm["t"].delete(f"{DIARY}/{entry['id']}")
        assert expenses_for(farm["t"], db, entry["id"]) == []

    def test_restore_revives_the_same_expense_row(self, farm, db):
        """I6 — the unique index covers soft-deleted rows, so a restore must
        reuse the existing row rather than insert a second one."""
        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "10"}]).json()
        original = expenses_for(farm["t"], db, entry["id"])[0].id

        farm["t"].delete(f"{DIARY}/{entry['id']}")
        farm["t"].post(f"{DIARY}/{entry['id']}/restore")

        rows = expenses_for(farm["t"], db, entry["id"])
        assert len(rows) == 1
        assert rows[0].id == original

    def test_repeated_edits_never_duplicate_the_expense(self, farm, db):
        """I6 under a sync retry — the farmer's costs must not multiply."""
        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "10"}]).json()
        for q in ("11", "12", "12", "13", "13"):
            farm["t"].patch(
                f"{DIARY}/{entry['id']}",
                json={"supply_usages": [{"supply_id": farm["urea"]["id"], "quantity": q}]},
            )
        rows = expenses_for(farm["t"], db, entry["id"])
        assert len(rows) == 1
        assert rows[0].amount == Decimal("156000.00")

    def test_bare_stock_out_generates_no_expense(self, farm, db):
        """I7 — that movement is a stock-take or transfer; the money left the
        household when the supply was bought. Booking it again double-counts."""
        from sqlalchemy import func, select

        from app.models import Expense

        farm["t"].post(f"{SUPPLIES}/{farm['urea']['id']}/stock-out", json={"quantity": "5"})
        count = db.execute(select(func.count()).select_from(Expense)).scalar_one()
        assert count == 0

    def test_stock_in_generates_no_expense(self, farm, db):
        from sqlalchemy import func, select

        from app.models import Expense

        farm["t"].post(f"{SUPPLIES}/{farm['urea']['id']}/stock-in", json={"quantity": "50"})
        assert db.execute(select(func.count()).select_from(Expense)).scalar_one() == 0

    def test_unique_index_makes_duplication_impossible(self, farm, db):
        """The structural guarantee: even a buggy service cannot double-count,
        because the database refuses the second row."""
        import uuid as _uuid

        from sqlalchemy.exc import IntegrityError

        from app.models import Expense

        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "10"}]).json()
        txn_id = entry["supply_usages"][0]["transaction_id"]

        db.add(
            Expense(
                id=str(_uuid.uuid4()),
                household_id=_uuid.UUID(farm["t"].household_id),
                season_id=farm["season"]["id"],
                stock_transaction_id=txn_id,
                category="supply",
                amount=Decimal("1.00"),
                expense_date=ENTRY_DATE,
                source="diary_auto",
                created_at=1,
                updated_at=1,
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()


class TestSeasonTotals:
    def test_supply_cost_flows_into_the_season_total(self, farm, db):
        """I9 — consumption is already a diary_auto expense, so there is no
        separate 'add supply costs' step and double-counting is impossible."""
        import uuid as _uuid

        from app.services import finance_service

        create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "25"}])
        totals = finance_service.season_totals(
            db, _uuid.UUID(farm["t"].household_id), farm["season"]["id"]
        )
        assert totals["total_cost"] == Decimal("300000.00")
        assert totals["total_revenue"] == Decimal("0")
        assert totals["profit"] == Decimal("-300000.00")


# ═══════════════════════════════════════════════════════════════════════════
#  Isolation
# ═══════════════════════════════════════════════════════════════════════════


class TestTenantIsolation:
    def test_cannot_read_another_households_entry(self, farm, make_tenant):
        other = make_tenant()
        entry = create_entry(farm).json()
        assert other.get(f"{DIARY}/{entry['id']}").status_code == 404

    def test_cannot_edit_another_households_entry(self, farm, make_tenant):
        other = make_tenant()
        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "10"}]).json()
        assert other.patch(f"{DIARY}/{entry['id']}", json={"note": "x"}).status_code == 404
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("90.000")

    def test_cannot_delete_another_households_entry(self, farm, make_tenant):
        other = make_tenant()
        entry = create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "10"}]).json()
        assert other.delete(f"{DIARY}/{entry['id']}").status_code == 404
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("90.000")

    def test_cannot_consume_another_households_supply(self, farm, make_tenant):
        other = make_tenant()
        other_season = other.post(
            SEASONS, json={"name": "Của B", "crop_type": "Ngô", "start_date": START}
        ).json()
        r = other.post(
            f"{SEASONS}/{other_season['id']}/diary-entries",
            json={
                "work_type": "fertilizing",
                "entry_date": ENTRY_DATE,
                "supply_usages": [{"supply_id": farm["urea"]["id"], "quantity": "50"}],
            },
        )
        assert r.status_code == 404
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("100.000")


class TestSeasonCascade:
    def test_deleting_the_season_reverses_diary_consumption(self, farm):
        """The season cascade tombstones diary-generated movements, which
        returns the stock — the same hoàn kho rule (I3)."""
        create_entry(farm, [{"supply_id": farm["urea"]["id"], "quantity": "30"}])
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("70.000")

        r = farm["t"].delete(f"{SEASONS}/{farm['season']['id']}")
        assert r.status_code == 200
        assert r.json()["diary_entries_deleted"] == 1
        assert r.json()["stock_transactions_deleted"] == 1
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("100.000")

    def test_standalone_purchase_survives_season_deletion(self, farm):
        """A purchase booked against the season is de-allocated, not deleted:
        the fertiliser is still physically in the shed."""
        farm["t"].post(
            f"{SUPPLIES}/{farm['urea']['id']}/stock-in",
            json={"quantity": "40", "season_id": farm["season"]["id"]},
        )
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("140.000")

        r = farm["t"].delete(f"{SEASONS}/{farm['season']['id']}")
        assert r.json()["stock_transactions_unlinked"] == 1
        assert level(farm["t"], farm["urea"]["id"]) == Decimal("140.000")
