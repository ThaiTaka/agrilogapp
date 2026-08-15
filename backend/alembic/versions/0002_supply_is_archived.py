"""Add supplies.is_archived and locale-independent supplies.name_key

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-11

Two changes to `supplies`.

1. `is_archived`. A supply that has movement history must never be
   tombstoned: deleting it would make WatermelonDB drop the row on every
   device, leaving last season's diary entries pointing at a supply whose
   name no longer exists locally, and it would rewrite the cost history of
   past seasons. Archiving hides it from the picker while the row keeps
   syncing normally. Deletion stays available only for supplies with no
   movements at all. (Data_Requirements_Database.md section 8.4.)

2. `name_key`, replacing the `lower(name)` unique index from 0001.
   PostgreSQL's lower() folds case according to the database collation. Under
   `C`, lower('Đạm Urê Phú Mỹ') returns 'Đạm urê phú mỹ' -- the Đ is
   untouched -- so the index accepted the same supply twice and the
   application's duplicate check never matched. name_key is folded in Python
   (NFC + casefold) and compared as bytes, which gives the same answer on
   every cluster regardless of how it was initdb'd.
   See docs/troubleshooting/Error_Postgres_Locale_Case_Folding.md.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "supplies",
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    # The inventory list filters on it every time it loads, alongside the
    # household scope the existing ix_supplies_household_cat already covers.
    op.create_index(
        "ix_supplies_active",
        "supplies",
        ["household_id", "category", "name"],
        postgresql_where=sa.text("deleted_at IS NULL AND is_archived = false"),
    )

    # ── name_key ───────────────────────────────────────────────────────────
    op.add_column("supplies", sa.Column("name_key", sa.String(160), nullable=True))
    # Best-effort backfill. lower() is the wrong fold for non-ASCII -- that is
    # the whole point of this migration -- but it is the only fold available
    # inside SQL, and any existing row is development data. The application
    # rewrites name_key correctly on the next update of each row.
    op.execute("UPDATE supplies SET name_key = lower(trim(name)) WHERE name_key IS NULL")
    op.alter_column("supplies", "name_key", nullable=False)

    op.drop_index("uq_supply_name_unit", table_name="supplies")
    op.create_index(
        "uq_supply_key_unit",
        "supplies",
        ["household_id", "name_key", "unit"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_supply_key_unit", table_name="supplies")
    op.create_index(
        "uq_supply_name_unit",
        "supplies",
        ["household_id", sa.text("lower(name)"), "unit"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_column("supplies", "name_key")

    op.drop_index("ix_supplies_active", table_name="supplies")
    op.drop_column("supplies", "is_archived")
