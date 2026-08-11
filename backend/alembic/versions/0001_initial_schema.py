"""Initial schema: accounts, seasons, inventory, diary, finance, sync audit.

Revision ID: 0001
Revises:
Create Date: 2026-08-11

Implements Data_Requirements_Database.md in full:
  * 6 synced tables carrying the SyncMixin block (section 6.1)
  * 4 server-only tables (accounts + sync audit)
  * the `touch_server_updated_at` trigger that keeps the pull cursor honest
  * STORED generated `*_day_local` columns for indexable report grouping
    (section 7.2)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# UTC+7 in milliseconds. Duplicated as a literal here on purpose: a migration
# must describe the schema as it was at this revision, not as the current
# settings object happens to define it.
TZ_OFFSET_MS = 25_200_000

SYNCED_TABLES = (
    "seasons",
    "supplies",
    "diary_entries",
    "stock_transactions",
    "expenses",
    "revenues",
)


def _sync_columns() -> list[sa.Column]:
    """The SyncMixin block. Mirrors app/db/base.py:SyncMixin."""
    return [
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.Column(
            "server_updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_device_id", sa.Text(), nullable=True),
        sa.Column("household_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
    ]


def _day_local(date_column: str) -> str:
    return f"(({date_column} + {TZ_OFFSET_MS}) / 86400000)::INTEGER"


def upgrade() -> None:
    # ═══════════════════════════════════════════════════════════════════════
    #  Accounts (server-only)
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "households",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("province", sa.Text(), nullable=True),
        sa.Column("commune", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_households"),
    )

    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("household_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.ForeignKeyConstraint(
            ["household_id"], ["households.id"], name="fk_users_household_id", ondelete="CASCADE"
        ),
    )
    # Case-insensitive uniqueness without the citext extension.
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)
    op.create_index("ix_users_household_id", "users", ["household_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_refresh_tokens_user_id", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_refresh_tokens_user_active", "refresh_tokens", ["user_id", "expires_at"])

    # ═══════════════════════════════════════════════════════════════════════
    #  Seasons
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "seasons",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("crop_type", sa.Text(), nullable=False),
        sa.Column("area_size", sa.Numeric(10, 3), nullable=True),
        sa.Column("area_unit", sa.String(16), server_default=sa.text("'sao'"), nullable=False),
        sa.Column("start_date", sa.BigInteger(), nullable=False),
        sa.Column("end_date", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(16), server_default=sa.text("'active'"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        *_sync_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_seasons"),
        sa.CheckConstraint(
            "status IN ('planning', 'active', 'harvested', 'closed')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date", name="date_range_valid"
        ),
        sa.CheckConstraint(
            "area_size IS NULL OR area_size >= 0", name="area_non_negative"
        ),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 120", name="name_length"),
        sa.CheckConstraint(
            "length(crop_type) BETWEEN 1 AND 80", name="crop_type_length"
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_seasons_household_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_seasons_sync", "seasons", ["household_id", "server_updated_at"])
    op.create_index(
        "ix_seasons_household_start",
        "seasons",
        ["household_id", sa.text("start_date DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ═══════════════════════════════════════════════════════════════════════
    #  Supplies
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "supplies",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("unit_cost", sa.Numeric(16, 2), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "low_stock_threshold", sa.Numeric(14, 3), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("note", sa.Text(), nullable=True),
        *_sync_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_supplies"),
        sa.CheckConstraint(
            "category IN ('fertilizer', 'pesticide', 'seed', 'fuel', 'tool', 'other')",
            name="category_valid",
        ),
        sa.CheckConstraint("unit_cost >= 0", name="unit_cost_non_negative"),
        sa.CheckConstraint("low_stock_threshold >= 0", name="low_stock_non_negative"),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 120", name="name_length"),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_supplies_household_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_supplies_sync", "supplies", ["household_id", "server_updated_at"])
    op.create_index(
        "ix_supplies_household_cat",
        "supplies",
        ["household_id", "category", "name"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_supply_name_unit",
        "supplies",
        ["household_id", sa.text("lower(name)"), "unit"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ═══════════════════════════════════════════════════════════════════════
    #  Diary entries
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "diary_entries",
        sa.Column("season_id", sa.String(36), nullable=False),
        sa.Column("work_type", sa.String(24), nullable=False),
        sa.Column("entry_date", sa.BigInteger(), nullable=False),
        sa.Column(
            "entry_day_local",
            sa.Integer(),
            sa.Computed(_day_local("entry_date"), persisted=True),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("weather", sa.String(32), nullable=True),
        sa.Column("labor_hours", sa.Numeric(6, 2), nullable=True),
        *_sync_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_diary_entries"),
        sa.CheckConstraint(
            "work_type IN ('land_prep', 'sowing', 'fertilizing', 'spraying', "
            "'watering', 'weeding', 'harvesting', 'other')",
            name="work_type_valid",
        ),
        sa.CheckConstraint(
            "labor_hours IS NULL OR labor_hours >= 0", name="labor_hours_valid"
        ),
        sa.CheckConstraint(
            "title IS NULL OR length(title) <= 160", name="title_length"
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_diary_entries_household_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["seasons.id"],
            name="fk_diary_entries_season_id",
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    op.create_index("ix_diary_entries_sync", "diary_entries", ["household_id", "server_updated_at"])
    op.create_index(
        "ix_diary_season_date",
        "diary_entries",
        ["season_id", sa.text("entry_date DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_diary_worktype",
        "diary_entries",
        ["household_id", "work_type", sa.text("entry_date DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ═══════════════════════════════════════════════════════════════════════
    #  Stock transactions (the inventory ledger)
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "stock_transactions",
        sa.Column("supply_id", sa.String(36), nullable=False),
        sa.Column("season_id", sa.String(36), nullable=True),
        sa.Column("diary_entry_id", sa.String(36), nullable=True),
        sa.Column("txn_type", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(16, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("total_cost", sa.Numeric(16, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("txn_date", sa.BigInteger(), nullable=False),
        sa.Column(
            "txn_day_local",
            sa.Integer(),
            sa.Computed(_day_local("txn_date"), persisted=True),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        *_sync_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_stock_transactions"),
        sa.CheckConstraint(
            "txn_type IN ('in', 'out', 'adjust')", name="txn_type_valid"
        ),
        sa.CheckConstraint(
            "(txn_type IN ('in','out') AND quantity > 0) "
            "OR (txn_type = 'adjust' AND quantity <> 0)",
            name="quantity_sign_valid",
        ),
        sa.CheckConstraint("unit_cost >= 0", name="unit_cost_non_negative"),
        sa.CheckConstraint("total_cost >= 0", name="total_cost_non_negative"),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_stock_transactions_household_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supply_id"],
            ["supplies.id"],
            name="fk_stock_transactions_supply_id",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["seasons.id"],
            name="fk_stock_transactions_season_id",
            ondelete="SET NULL",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["diary_entry_id"],
            ["diary_entries.id"],
            name="fk_stock_transactions_diary_entry_id",
            ondelete="SET NULL",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    op.create_index(
        "ix_stock_transactions_sync", "stock_transactions", ["household_id", "server_updated_at"]
    )
    op.create_index(
        "ix_stock_supply_date",
        "stock_transactions",
        ["supply_id", sa.text("txn_date DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_stock_diary",
        "stock_transactions",
        ["diary_entry_id"],
        postgresql_where=sa.text("deleted_at IS NULL AND diary_entry_id IS NOT NULL"),
    )
    op.create_index(
        "ix_stock_season_type",
        "stock_transactions",
        ["season_id", "txn_type"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ═══════════════════════════════════════════════════════════════════════
    #  Expenses
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "expenses",
        sa.Column("season_id", sa.String(36), nullable=False),
        sa.Column("stock_transaction_id", sa.String(36), nullable=True),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("expense_date", sa.BigInteger(), nullable=False),
        sa.Column(
            "expense_day_local",
            sa.Integer(),
            sa.Computed(_day_local("expense_date"), persisted=True),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(16), server_default=sa.text("'manual'"), nullable=False),
        *_sync_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_expenses"),
        sa.CheckConstraint(
            "category IN ('supply', 'labor', 'machinery', 'transport', "
            "'land_rent', 'irrigation', 'other')",
            name="category_valid",
        ),
        sa.CheckConstraint("source IN ('manual', 'diary_auto')", name="source_valid"),
        sa.CheckConstraint("amount >= 0", name="amount_non_negative"),
        sa.CheckConstraint(
            "(source = 'diary_auto') = (stock_transaction_id IS NOT NULL)",
            name="source_matches_link",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_expenses_household_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["seasons.id"],
            name="fk_expenses_season_id",
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["stock_transaction_id"],
            ["stock_transactions.id"],
            name="fk_expenses_stock_transaction_id",
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    op.create_index("ix_expenses_sync", "expenses", ["household_id", "server_updated_at"])
    # The Issue #29 idempotency guarantee.
    op.create_index(
        "uq_expense_per_stock_txn",
        "expenses",
        ["stock_transaction_id"],
        unique=True,
        postgresql_where=sa.text("stock_transaction_id IS NOT NULL"),
    )
    op.create_index(
        "ix_expenses_season_date",
        "expenses",
        ["season_id", "expense_date"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ═══════════════════════════════════════════════════════════════════════
    #  Revenues
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "revenues",
        sa.Column("season_id", sa.String(36), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("unit", sa.String(16), nullable=True),
        sa.Column("unit_price", sa.Numeric(16, 2), nullable=True),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("revenue_date", sa.BigInteger(), nullable=False),
        sa.Column(
            "revenue_day_local",
            sa.Integer(),
            sa.Computed(_day_local("revenue_date"), persisted=True),
            nullable=False,
        ),
        sa.Column("buyer", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        *_sync_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_revenues"),
        sa.CheckConstraint("amount >= 0", name="amount_non_negative"),
        sa.CheckConstraint(
            "quantity IS NULL OR quantity >= 0", name="quantity_non_negative"
        ),
        sa.CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0", name="unit_price_non_negative"
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_revenues_household_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["seasons.id"],
            name="fk_revenues_season_id",
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    op.create_index("ix_revenues_sync", "revenues", ["household_id", "server_updated_at"])
    op.create_index(
        "ix_revenues_season_date",
        "revenues",
        ["season_id", "revenue_date"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ═══════════════════════════════════════════════════════════════════════
    #  Sync audit log (server-only)
    # ═══════════════════════════════════════════════════════════════════════
    op.create_table(
        "sync_sessions",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("household_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=True),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_pulled_at", sa.BigInteger(), nullable=True),
        sa.Column("records_pulled", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("records_pushed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("records_rejected", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_sync_sessions"),
        sa.CheckConstraint(
            "direction IN ('pull', 'push')", name="direction_valid"
        ),
        sa.CheckConstraint(
            "status IN ('ok', 'partial', 'error')", name="status_valid"
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_sync_sessions_household_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_sync_sessions_household_started",
        "sync_sessions",
        ["household_id", sa.text("started_at DESC")],
    )

    # ═══════════════════════════════════════════════════════════════════════
    #  The pull-cursor trigger
    # ═══════════════════════════════════════════════════════════════════════
    # Enforced in the database rather than via SQLAlchemy's `onupdate=`,
    # because the seed script, a manual UPDATE in pgAdmin, and any future admin
    # tool all bypass the ORM. A write that escapes the ORM without bumping the
    # cursor becomes a row that is permanently invisible to every device -- the
    # data is present on the server and simply never arrives. Putting it in the
    # database makes that unrepresentable.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION touch_server_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.server_updated_at := now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in SYNCED_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_touch_server_updated_at
            BEFORE INSERT OR UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION touch_server_updated_at();
            """
        )


def downgrade() -> None:
    for table in SYNCED_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_touch_server_updated_at ON {table};")
    op.execute("DROP FUNCTION IF EXISTS touch_server_updated_at();")

    # Reverse dependency order.
    op.drop_table("sync_sessions")
    op.drop_table("revenues")
    op.drop_table("expenses")
    op.drop_table("stock_transactions")
    op.drop_table("diary_entries")
    op.drop_table("supplies")
    op.drop_table("seasons")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.drop_table("households")
