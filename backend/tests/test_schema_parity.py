"""Guard against ORM / migration drift.

If `app/models/*` and `alembic/versions/*` disagree, `alembic upgrade head`
builds one schema while the ORM assumes another. The failures that follow are
maddening — a column that exists in Python and not in PostgreSQL surfaces as a
random UndefinedColumn deep inside an unrelated request.

This test renders both to SQL and compares them structurally. It needs **no
database**, so it runs in CI on every push (Issue #18) whether or not a
PostgreSQL service is available.

Once a live database is reachable, `test_schema_integrity.py` adds the
complementary check against the real, migrated schema.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest
from sqlalchemy import create_mock_engine

from alembic import command
from alembic.config import Config
from app.models import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Alembic's own bookkeeping table; it is intentionally absent from the ORM.
IGNORED_TABLES = {"alembic_version"}


def _normalise(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip().rstrip(";").strip()


def _split_top_level(body: str) -> list[str]:
    parts, depth, current = [], 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    return [_normalise(p) for p in parts if _normalise(p)]


def _parse(sql_text: str) -> tuple[dict[str, set[str]], dict[str, str]]:
    """Replay the DDL into {table: {column/constraint lines}} and {index: stmt}.

    The migration stream is a *sequence* of statements, not a snapshot: a later
    revision adds columns and swaps indexes that an earlier one created. The
    parser therefore has to apply ALTER and DROP too, or every migration after
    0001 reads as drift against the models.
    """
    tables: dict[str, set[str]] = {}
    indexes: dict[str, str] = {}

    for m in re.finditer(r"CREATE TABLE (\w+)\s*\((.*?)\n\)", sql_text, re.S):
        name = m.group(1)
        if name in IGNORED_TABLES:
            continue
        tables[name] = set(_split_top_level(m.group(2)))

    for m in re.finditer(r"ALTER TABLE (\w+) ADD COLUMN ([^;]+);", sql_text):
        table = m.group(1)
        if table in tables:
            tables[table].add(_normalise(m.group(2)))

    for m in re.finditer(r"ALTER TABLE (\w+) DROP COLUMN (\w+);", sql_text):
        table, column = m.group(1), m.group(2)
        tables[table] = {c for c in tables.get(table, set()) if not c.startswith(f"{column} ")}

    # ALTER COLUMN ... SET/DROP NOT NULL — rewrite the recorded line so an
    # add-nullable-then-backfill-then-tighten sequence matches the model.
    for m in re.finditer(r"ALTER TABLE (\w+) ALTER COLUMN (\w+) (SET|DROP) NOT NULL;", sql_text):
        table, column, action = m.group(1), m.group(2), m.group(3)
        current = tables.get(table, set())
        for line in list(current):
            if line.startswith(f"{column} "):
                current.discard(line)
                stripped = line.replace(" NOT NULL", "")
                current.add(f"{stripped} NOT NULL" if action == "SET" else stripped)
        tables[table] = current

    for m in re.finditer(r"CREATE (?:UNIQUE )?INDEX (\w+) ON .*", sql_text):
        indexes[m.group(1)] = _normalise(m.group(0))

    for m in re.finditer(r"DROP INDEX (\w+);", sql_text):
        indexes.pop(m.group(1), None)

    return tables, indexes


@pytest.fixture(scope="module")
def metadata_sql() -> str:
    statements: list[str] = []
    engine = create_mock_engine(
        "postgresql+psycopg://",
        lambda sql, *a, **kw: statements.append(str(sql.compile(dialect=engine.dialect))),
    )
    Base.metadata.create_all(engine, checkfirst=False)
    return "\n\n".join(s.strip() for s in statements if s.strip())


@pytest.fixture(scope="module")
def migration_sql() -> str:
    # `output_buffer`, not `stdout`: in offline mode the MigrationContext
    # writes rendered DDL to output_buffer, while `stdout` only receives
    # alembic's own log chatter.
    buffer = io.StringIO()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"), output_buffer=buffer, stdout=io.StringIO())
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head", sql=True)   # offline mode: renders, never connects
    rendered = buffer.getvalue()
    assert "CREATE TABLE" in rendered, "offline render produced no DDL"
    return rendered


class TestMigrationMatchesModels:
    def test_same_tables(self, metadata_sql, migration_sql):
        meta, _ = _parse(metadata_sql)
        migr, _ = _parse(migration_sql)
        assert set(meta) == set(migr)

    def test_same_columns_and_constraints(self, metadata_sql, migration_sql):
        meta, _ = _parse(metadata_sql)
        migr, _ = _parse(migration_sql)
        problems = []
        for table in sorted(set(meta) & set(migr)):
            for line in sorted(meta[table] - migr[table]):
                problems.append(f"{table}: in models, missing from migration -> {line}")
            for line in sorted(migr[table] - meta[table]):
                problems.append(f"{table}: in migration, missing from models  -> {line}")
        assert not problems, "ORM/migration drift:\n  " + "\n  ".join(problems)

    def test_same_indexes(self, metadata_sql, migration_sql):
        _, meta = _parse(metadata_sql)
        _, migr = _parse(migration_sql)
        assert set(meta) == set(migr)
        differing = {k: (meta[k], migr[k]) for k in meta if meta[k] != migr[k]}
        assert not differing, f"Index definitions differ: {differing}"


class TestConstraintNamesAreValid:
    def test_no_identifier_exceeds_postgres_limit(self, migration_sql):
        """PostgreSQL truncates identifiers at 63 bytes, silently.

        A truncated constraint name still works, but `alembic downgrade` and
        any later `op.drop_constraint` reference a name that no longer exists.
        """
        names = re.findall(r"CONSTRAINT (\w+)", migration_sql)
        names += re.findall(r"CREATE (?:UNIQUE )?INDEX (\w+)", migration_sql)
        too_long = [n for n in names if len(n) > 63]
        assert not too_long, f"Identifiers over 63 chars: {too_long}"

    def test_no_double_prefixed_check_constraints(self, migration_sql):
        """The `ck` naming convention interpolates the supplied name as a token.

        Passing an already-prefixed name yields `ck_seasons_ck_seasons_...`,
        which then collides with the 63-char limit. Regression guard.
        """
        doubled = [n for n in re.findall(r"CONSTRAINT (\w+)", migration_sql) if "_ck_" in n]
        assert not doubled, f"Double-prefixed constraint names: {doubled}"


class TestSyncSchemaContract:
    """Structural rules the sync engine depends on (no database needed)."""

    def test_every_synced_model_carries_the_sync_block(self):
        from app.models import SYNC_MODELS

        required = {
            "id",
            "household_id",
            "created_at",
            "updated_at",
            "server_updated_at",
            "deleted_at",
            "last_device_id",
        }
        for name, model in SYNC_MODELS.items():
            missing = required - set(model.__table__.columns.keys())
            assert not missing, f"{name} is missing sync columns: {missing}"

    def test_every_synced_table_has_the_pull_cursor_index(self):
        from app.models import SYNC_MODELS

        for name, model in SYNC_MODELS.items():
            cols = {
                tuple(c.name for c in idx.columns) for idx in model.__table__.indexes
            }
            assert ("household_id", "server_updated_at") in cols, (
                f"{name} lacks ix_{name}_sync — the pull query would seq-scan it"
            )

    def test_sync_tables_are_declared_in_dependency_order(self):
        """A batch must never insert a child before its parent."""
        from app.models import SYNC_MODELS

        seen: set[str] = set()
        for table_name, model in SYNC_MODELS.items():
            for fk in model.__table__.foreign_keys:
                target = fk.column.table.name
                if target in SYNC_MODELS and target != table_name:
                    assert target in seen, (
                        f"{table_name} references {target}, which is applied later. "
                        "Reorder SYNC_MODELS."
                    )
            seen.add(table_name)

    def test_cross_table_sync_foreign_keys_are_deferrable(self):
        """A single batch can contain a child and its parent.

        Ordering handles the common case; deferring to COMMIT means the batch
        is validated as a whole, which is the correct semantics because the
        batch is the unit of atomicity.
        """
        from app.models import SYNC_MODELS

        offenders = []
        for table_name, model in SYNC_MODELS.items():
            for fk in model.__table__.foreign_keys:
                if fk.column.table.name in SYNC_MODELS and not fk.constraint.deferrable:
                    offenders.append(f"{table_name}.{fk.parent.name}")
        assert not offenders, f"Non-deferrable FKs between synced tables: {offenders}"

    def test_auto_expense_link_is_unique(self):
        """The structural half of the Issue #29 idempotency guarantee."""
        from app.models import Expense

        unique_single = {
            tuple(c.name for c in idx.columns)
            for idx in Expense.__table__.indexes
            if idx.unique
        }
        assert ("stock_transaction_id",) in unique_single

    def test_supplies_has_no_stored_stock_column(self):
        """On-hand is derived from the ledger, never stored (D1).

        A cached counter decremented independently by two offline devices is
        undetectably wrong after sync. This asserts nobody 'optimises' it back.
        """
        from app.models import Supply

        forbidden = {"current_stock", "stock", "quantity_on_hand", "on_hand"}
        assert not (forbidden & set(Supply.__table__.columns.keys()))
