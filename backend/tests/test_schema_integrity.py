"""Checks against the real, migrated PostgreSQL schema.

These require a live database and are skipped automatically when one is not
reachable (see conftest.py). They complement `test_schema_parity.py`, which
compares models to migrations without a database: this module verifies that
what actually landed in PostgreSQL behaves as designed.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.models import SYNC_MODELS
from app.models.enums import (
    ExpenseCategory,
    ExpenseSource,
    SeasonStatus,
    SupplyCategory,
    SyncDirection,
    SyncStatus,
    TxnType,
    WorkType,
)

pytestmark = pytest.mark.db


def _check_clause(db, table: str, constraint: str) -> str:
    row = db.execute(
        text(
            """
            SELECT pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            WHERE t.relname = :table AND c.conname = :constraint
            """
        ),
        {"table": table, "constraint": constraint},
    ).scalar()
    assert row is not None, f"constraint {constraint} not found on {table}"
    return row


class TestEnumConstraintsMatchPython:
    """A value added to a Python enum and forgotten in the CHECK constraint
    (or the reverse) fails here rather than in production."""

    @pytest.mark.parametrize(
        ("table", "constraint", "enum"),
        [
            ("seasons", "ck_seasons_status_valid", SeasonStatus),
            ("supplies", "ck_supplies_category_valid", SupplyCategory),
            ("diary_entries", "ck_diary_entries_work_type_valid", WorkType),
            ("stock_transactions", "ck_stock_transactions_txn_type_valid", TxnType),
            ("expenses", "ck_expenses_category_valid", ExpenseCategory),
            ("expenses", "ck_expenses_source_valid", ExpenseSource),
            ("sync_sessions", "ck_sync_sessions_direction_valid", SyncDirection),
            ("sync_sessions", "ck_sync_sessions_status_valid", SyncStatus),
        ],
    )
    def test_constraint_lists_every_python_value(self, db, table, constraint, enum):
        clause = _check_clause(db, table, constraint)
        for value in enum.values():
            assert f"'{value}'" in clause, (
                f"{enum.__name__}.{value} is missing from {constraint}"
            )


class TestTriggerKeepsPullCursorHonest:
    def test_trigger_exists_on_every_synced_table(self, db):
        for table in SYNC_MODELS:
            found = db.execute(
                text(
                    """
                    SELECT 1 FROM pg_trigger tg
                    JOIN pg_class t ON t.oid = tg.tgrelid
                    WHERE t.relname = :table
                      AND tg.tgname = :name
                      AND NOT tg.tgisinternal
                    """
                ),
                {"table": table, "name": f"trg_{table}_touch_server_updated_at"},
            ).scalar()
            assert found, f"{table} has no server_updated_at trigger"

    def test_raw_sql_update_still_bumps_the_cursor(self, db, household):
        """The whole point of using a trigger rather than SQLAlchemy `onupdate`.

        The seed script, pgAdmin, and any future admin tool bypass the ORM. A
        write that escapes the ORM without bumping the cursor becomes a row
        that is permanently invisible to every device.
        """
        db.execute(
            text(
                """
                INSERT INTO seasons (id, household_id, name, crop_type, area_unit,
                                     start_date, status, created_at, updated_at)
                VALUES ('t-cursor-1', :hid, 'Vụ test', 'Lúa', 'sao',
                        1767225600000, 'active', 1767225600000, 1767225600000)
                """
            ),
            {"hid": household},
        )
        before = db.execute(
            text("SELECT server_updated_at FROM seasons WHERE id = 't-cursor-1'")
        ).scalar()

        db.execute(text("UPDATE seasons SET name = 'Vụ đổi tên' WHERE id = 't-cursor-1'"))
        after = db.execute(
            text("SELECT server_updated_at FROM seasons WHERE id = 't-cursor-1'")
        ).scalar()

        assert after > before, "raw UPDATE did not bump server_updated_at"


class TestGeneratedDayColumns:
    def test_day_column_matches_python_helper(self, db, household):
        from app.core.timeutils import local_day_index

        # 2026-09-12 20:00 Vietnam time == 13:00 UTC
        entry_ms = 1_789_218_000_000
        db.execute(
            text(
                """
                INSERT INTO seasons (id, household_id, name, crop_type, area_unit,
                                     start_date, status, created_at, updated_at)
                VALUES ('t-day-s', :hid, 'S', 'Lúa', 'sao', 1767225600000, 'active', 1, 1)
                """
            ),
            {"hid": household},
        )
        db.execute(
            text(
                """
                INSERT INTO diary_entries (id, household_id, season_id, work_type,
                                           entry_date, created_at, updated_at)
                VALUES ('t-day-d', :hid, 't-day-s', 'spraying', :ms, 1, 1)
                """
            ),
            {"hid": household, "ms": entry_ms},
        )
        sql_day = db.execute(
            text("SELECT entry_day_local FROM diary_entries WHERE id = 't-day-d'")
        ).scalar()
        assert sql_day == local_day_index(entry_ms), (
            "SQL and Python disagree about the local calendar day — the same "
            "season would render two different charts depending on the source"
        )

    def test_day_column_is_not_writable(self, db):
        """Generated columns are computed, never supplied."""
        from sqlalchemy.exc import DatabaseError

        with pytest.raises(DatabaseError):
            db.execute(
                text(
                    "INSERT INTO diary_entries (id, household_id, season_id, work_type, "
                    "entry_date, entry_day_local, created_at, updated_at) "
                    "VALUES ('x', gen_random_uuid(), 'y', 'other', 1, 1, 1, 1)"
                )
            )


class TestDataIsolation:
    def test_every_synced_table_requires_a_household(self, db):
        for name, model in SYNC_MODELS.items():
            col = model.__table__.columns["household_id"]
            assert not col.nullable, f"{name}.household_id must be NOT NULL (rule R4)"


@pytest.fixture
def household(db):
    """A minimal household row for tests that need a valid FK target."""
    hid = db.execute(
        text("INSERT INTO households (name) VALUES ('Hộ test') RETURNING id")
    ).scalar()
    return hid
