"""Development seed data.

    python -m app.seed              # create if absent
    python -m app.seed --reset      # wipe this household's data first
    python -m app.seed --help

Accounts are created through `auth_service`, not by inserting rows directly,
so the seeded password hash is produced by exactly the code that will verify
it at login.

SCOPE NOTE. This currently seeds accounts, seasons and the supply catalogue.
Diary entries, stock movements and expenses are deliberately NOT seeded yet:
each of those must go through the stock-restore and auto-expense services to
satisfy invariants I3 and I6 (Data_Requirements_Database.md section 9), and
those services land with Issues #21-#29. Writing raw rows here in the meantime
would duplicate that logic and let the two drift — which is the exact failure
this project cannot afford, because the drift only becomes visible after a
sync. This module is extended as those services arrive.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select

from app.core.timeutils import now_ms, to_ms
from app.db.session import SessionLocal
from app.models import (
    DiaryEntry,
    Expense,
    Household,
    Revenue,
    Season,
    StockTransaction,
    Supply,
    User,
)
from app.models.enums import SeasonStatus, SupplyCategory
from app.schemas.supply import SupplyCreate
from app.services import auth_service, supply_service

UTC = timezone.utc

DEMO_EMAIL = "demo@agrilog.vn"
DEMO_PASSWORD = "demo1234"
SECOND_EMAIL = "thanhvien@agrilog.vn"


def _ms(year: int, month: int, day: int) -> int:
    return to_ms(datetime(year, month, day, tzinfo=UTC))


SEASONS = [
    # (name, crop, area, unit, start, end, status, note)
    (
        "Vụ Đông Xuân 2025-2026", "Lúa", Decimal("5.000"), "sao",
        _ms(2025, 12, 1), _ms(2026, 4, 15), SeasonStatus.CLOSED,
        "Vụ có lãi, giá lúa cuối vụ tốt.",
    ),
    (
        "Vụ Hè Thu 2026", "Cà chua", Decimal("3.000"), "sao",
        _ms(2026, 4, 20), _ms(2026, 8, 5), SeasonStatus.HARVESTED,
        "Sâu bệnh nhiều, chi phí thuốc cao.",
    ),
    (
        "Vụ Mùa 2026", "Bắp cải", Decimal("4.500"), "sao",
        _ms(2026, 8, 10), None, SeasonStatus.ACTIVE,
        "Đang canh tác.",
    ),
]

SUPPLIES = [
    # (name, category, unit, unit_cost VND, low_stock_threshold)
    ("Đạm Urê Phú Mỹ", SupplyCategory.FERTILIZER, "kg", Decimal("12000"), Decimal("20")),
    ("Lân Văn Điển", SupplyCategory.FERTILIZER, "kg", Decimal("8500"), Decimal("20")),
    ("Kali Clorua", SupplyCategory.FERTILIZER, "kg", Decimal("14000"), Decimal("15")),
    ("NPK 16-16-8", SupplyCategory.FERTILIZER, "bao", Decimal("620000"), Decimal("2")),
    ("Thuốc trừ sâu Regent", SupplyCategory.PESTICIDE, "chai", Decimal("45000"), Decimal("3")),
    ("Thuốc trừ bệnh Anvil", SupplyCategory.PESTICIDE, "chai", Decimal("68000"), Decimal("3")),
    ("Thuốc diệt cỏ Sofit", SupplyCategory.PESTICIDE, "chai", Decimal("95000"), Decimal("2")),
    ("Giống lúa OM5451", SupplyCategory.SEED, "kg", Decimal("22000"), Decimal("10")),
    ("Giống cà chua F1", SupplyCategory.SEED, "gói", Decimal("35000"), Decimal("5")),
    ("Dầu diesel", SupplyCategory.FUEL, "L", Decimal("21000"), Decimal("30")),
    ("Bình phun đeo vai", SupplyCategory.TOOL, "cái", Decimal("450000"), Decimal("1")),
    ("Bạt phủ luống", SupplyCategory.OTHER, "kg", Decimal("38000"), Decimal("5")),
]


def _reset(db, household_id) -> None:
    """Wipe this household's domain data, newest dependency first."""
    for model in (Expense, Revenue, StockTransaction, DiaryEntry, Season, Supply):
        db.execute(delete(model).where(model.household_id == household_id))
    db.flush()


def seed(reset: bool = False) -> int:
    db = SessionLocal()
    try:
        user = db.execute(
            select(User).where(func.lower(User.email) == DEMO_EMAIL)
        ).scalar_one_or_none()

        if user is None:
            user, household = auth_service.register_household(
                db,
                email=DEMO_EMAIL,
                password=DEMO_PASSWORD,
                full_name="Lê Văn A",
                household_name="Hộ ông Lê Văn A",
                phone="0912345678",
                province="Lâm Đồng",
                commune="Xã Hiệp An",
            )
            print(f"  + household  {household.name}")
            print(f"  + user       {DEMO_EMAIL} / {DEMO_PASSWORD}")
        else:
            household = db.get(Household, user.household_id)
            print(f"  = household  {household.name} (existing)")

        # A second user in the same household — this is what makes the
        # two-device conflict test (Issue #40) possible.
        second = db.execute(
            select(User).where(func.lower(User.email) == SECOND_EMAIL)
        ).scalar_one_or_none()
        if second is None:
            db.add(
                User(
                    household_id=household.id,
                    email=SECOND_EMAIL,
                    full_name="Lê Thị B",
                    password_hash=auth_service.hash_password(DEMO_PASSWORD),
                    is_active=True,
                )
            )
            db.flush()
            print(f"  + user       {SECOND_EMAIL} / {DEMO_PASSWORD} (same household)")

        if reset:
            _reset(db, household.id)
            print("  ! reset      existing seasons/supplies/diary/finance removed")

        existing_seasons = db.execute(
            select(func.count()).select_from(Season).where(Season.household_id == household.id)
        ).scalar_one()

        if existing_seasons == 0:
            ts = now_ms()
            for name, crop, area, unit, start, end, status, note in SEASONS:
                db.add(
                    Season(
                        household_id=household.id,
                        name=name,
                        crop_type=crop,
                        area_size=area,
                        area_unit=unit,
                        start_date=start,
                        end_date=end,
                        status=status.value,
                        note=note,
                        created_at=ts,
                        updated_at=ts,
                    )
                )
            print(f"  + seasons    {len(SEASONS)}")

            # Through the service, not raw ORM: it is what maintains
            # `name_key`, and seeding via a parallel path is how a seed script
            # ends up producing rows the application could never create.
            for name, category, unit, cost, low in SUPPLIES:
                supply_service.create_supply(
                    db,
                    household.id,
                    SupplyCreate(
                        name=name,
                        category=category,
                        unit=unit,
                        unit_cost=cost,
                        low_stock_threshold=low,
                    ),
                )
            print(f"  + supplies   {len(SUPPLIES)}")
        else:
            print(f"  = seasons    {existing_seasons} already present (use --reset to rebuild)")

        db.commit()
        print("\nSeed complete.")
        print(f"  Login: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI entry point
        db.rollback()
        print(f"\nSeed FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed AgriLog development data")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete the demo household's existing domain data before seeding",
    )
    args = parser.parse_args()
    print("Seeding AgriLog development data...")
    return seed(reset=args.reset)


if __name__ == "__main__":
    raise SystemExit(main())
