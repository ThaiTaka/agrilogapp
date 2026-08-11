"""Model package.

Importing this module registers every mapper with `Base.metadata`. Alembic's
`env.py` and the test harness both rely on that side effect, so nothing here
may be lazily imported.
"""

from app.db.base import SYNC_TABLE_ORDER, Base
from app.models.account import Household, RefreshToken, User
from app.models.diary import DiaryEntry
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
from app.models.finance import Expense, Revenue
from app.models.inventory import StockTransaction, Supply
from app.models.season import Season
from app.models.sync import SyncSession

# Table name -> ORM class, for the generic sync engine. Order matters: both
# push and pull apply tables in this sequence, and deletes in reverse.
SYNC_MODELS: dict[str, type[Base]] = {
    "seasons": Season,
    "supplies": Supply,
    "diary_entries": DiaryEntry,
    "stock_transactions": StockTransaction,
    "expenses": Expense,
    "revenues": Revenue,
}

assert tuple(SYNC_MODELS.keys()) == SYNC_TABLE_ORDER, (
    "SYNC_MODELS must be declared in the dependency order given by "
    "SYNC_TABLE_ORDER, or a sync batch can insert a child before its parent."
)

__all__ = [
    "SYNC_MODELS",
    "SYNC_TABLE_ORDER",
    "Base",
    "DiaryEntry",
    "Expense",
    "ExpenseCategory",
    "ExpenseSource",
    "Household",
    "RefreshToken",
    "Revenue",
    "Season",
    "SeasonStatus",
    "StockTransaction",
    "Supply",
    "SupplyCategory",
    "SyncDirection",
    "SyncSession",
    "SyncStatus",
    "TxnType",
    "User",
    "WorkType",
]
