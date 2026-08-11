"""Canonical enumerations.

Stored as TEXT + CHECK rather than as PostgreSQL ENUM types, because:

  * WatermelonDB has no enum type -- the value crosses the wire as a plain
    string regardless, so a native PG enum buys nothing at the boundary;
  * extending a native enum needs an ALTER TYPE migration, which is awkward to
    keep in lockstep with a mobile schema version bump.

`tests/test_schema_integrity.py` asserts that every CHECK constraint in the
live database matches the tuples here, so a value added on one side and
forgotten on the other fails CI rather than production.

Vietnamese labels live here too, and are served to the mobile app so the two
never disagree about what `land_prep` is called.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """`str`-valued enum. (`enum.StrEnum` proper is 3.11+.)"""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)

    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(m.value for m in cls)


class WorkType(StrEnum):
    LAND_PREP = "land_prep"
    SOWING = "sowing"
    FERTILIZING = "fertilizing"
    SPRAYING = "spraying"
    WATERING = "watering"
    WEEDING = "weeding"
    HARVESTING = "harvesting"
    OTHER = "other"


class SupplyCategory(StrEnum):
    FERTILIZER = "fertilizer"
    PESTICIDE = "pesticide"
    SEED = "seed"
    FUEL = "fuel"
    TOOL = "tool"
    OTHER = "other"


class TxnType(StrEnum):
    IN = "in"
    OUT = "out"
    ADJUST = "adjust"


class ExpenseCategory(StrEnum):
    SUPPLY = "supply"
    LABOR = "labor"
    MACHINERY = "machinery"
    TRANSPORT = "transport"
    LAND_RENT = "land_rent"
    IRRIGATION = "irrigation"
    OTHER = "other"


class ExpenseSource(StrEnum):
    MANUAL = "manual"
    DIARY_AUTO = "diary_auto"


class SeasonStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    HARVESTED = "harvested"
    CLOSED = "closed"


class SyncDirection(StrEnum):
    PULL = "pull"
    PUSH = "push"


class SyncStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    ERROR = "error"


# ═══════════════════════════════════════════════════════════════════════════
#  Vietnamese UI labels
# ═══════════════════════════════════════════════════════════════════════════

WORK_TYPE_LABELS_VI: dict[str, str] = {
    WorkType.LAND_PREP: "Làm đất",
    WorkType.SOWING: "Gieo/Trồng",
    WorkType.FERTILIZING: "Bón phân",
    WorkType.SPRAYING: "Phun thuốc",
    WorkType.WATERING: "Tưới nước",
    WorkType.WEEDING: "Làm cỏ",
    WorkType.HARVESTING: "Thu hoạch",
    WorkType.OTHER: "Khác",
}

SUPPLY_CATEGORY_LABELS_VI: dict[str, str] = {
    SupplyCategory.FERTILIZER: "Phân bón",
    SupplyCategory.PESTICIDE: "Thuốc BVTV",
    SupplyCategory.SEED: "Giống",
    SupplyCategory.FUEL: "Nhiên liệu",
    SupplyCategory.TOOL: "Dụng cụ",
    SupplyCategory.OTHER: "Khác",
}

TXN_TYPE_LABELS_VI: dict[str, str] = {
    TxnType.IN: "Nhập kho",
    TxnType.OUT: "Xuất kho",
    TxnType.ADJUST: "Điều chỉnh",
}

EXPENSE_CATEGORY_LABELS_VI: dict[str, str] = {
    ExpenseCategory.SUPPLY: "Vật tư",
    ExpenseCategory.LABOR: "Nhân công",
    ExpenseCategory.MACHINERY: "Máy móc",
    ExpenseCategory.TRANSPORT: "Vận chuyển",
    ExpenseCategory.LAND_RENT: "Thuê đất",
    ExpenseCategory.IRRIGATION: "Thủy lợi",
    ExpenseCategory.OTHER: "Khác",
}

SEASON_STATUS_LABELS_VI: dict[str, str] = {
    SeasonStatus.PLANNING: "Chuẩn bị",
    SeasonStatus.ACTIVE: "Đang canh tác",
    SeasonStatus.HARVESTED: "Đã thu hoạch",
    SeasonStatus.CLOSED: "Đã kết thúc",
}


def sql_in_list(values: tuple[str, ...]) -> str:
    """Render a tuple as a SQL IN-list literal for a CHECK constraint."""
    return ", ".join(f"'{v}'" for v in values)
