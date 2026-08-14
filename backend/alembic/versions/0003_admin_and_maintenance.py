"""Add users.is_admin and the single-row app_settings table

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-14

Groundwork for the Web Admin Dashboard (Phase 2).

1. `users.is_admin`. Every endpoint until now has been scoped to the household
   in the JWT, which is exactly the property that makes the API safe for
   tenants and useless for administration. `/admin/*` is the one deliberate
   exception, and this column is what gates it. Defaults to false, so applying
   this migration grants nobody anything -- the first admin is promoted out of
   band with scripts/make_admin.py.

2. `app_settings`, holding the system maintenance flag. One row, enforced by
   `CHECK (id = 1)` rather than by convention: a second row would give
   "is maintenance on?" two answers depending on read order. The row is
   inserted here so that every later read can assume it exists and no code
   path has to invent a default.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.create_table(
        "app_settings",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column(
            "maintenance_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("maintenance_message", sa.Text(), nullable=True),
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
        sa.CheckConstraint("id = 1", name="single_row"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Seeded now so reads never have to cope with an empty table. Idempotent
    # against a database where the row somehow already exists.
    op.execute(
        "INSERT INTO app_settings (id, maintenance_enabled) "
        "VALUES (1, false) ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_column("users", "is_admin")
