"""System-wide administrative state.

Server-only, like the account tables: nothing here crosses the sync boundary.
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, SmallInteger, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AppSetting(Base, TimestampMixin):
    """Global switches. Exactly one row, forever.

    A single row rather than a key/value table. The scope agreed with Thái is
    one flag, and a key/value store would make every read stringly-typed and
    every new switch a silent schema-less addition — the kind of table that
    ends up holding six things nobody can enumerate.

    `CHECK (id = 1)` is what makes "exactly one row" a database fact rather
    than a convention the application is trusted to keep. Without it a second
    row is one stray INSERT away, and then "is maintenance on?" has two
    answers depending on which row a query happens to read first.
    """

    __tablename__ = "app_settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)

    maintenance_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # Shown verbatim by the mobile app, so it is written for a farmer, not for
    # an operator: "đang bảo trì, thử lại sau 30 phút" rather than a ticket ID.
    maintenance_message: Mapped[str | None] = mapped_column(Text, nullable=True)
