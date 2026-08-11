"""Text normalisation for case-insensitive matching.

PostgreSQL's `lower()` folds case according to the **database's collation**.
Under the `C` collation it only touches ASCII A-Z, so `lower('Đạm Urê Phú Mỹ')`
returns `'Đạm urê phú mỹ'` — the Đ survives. Python's `str.lower()` folds the
full Unicode range and returns `'đạm urê phú mỹ'`.

For an application written in Vietnamese, that disagreement is not a corner
case: it means a duplicate check comparing `lower(column)` in SQL against
`value.lower()` in Python matches nothing, and a unique index on `lower(name)`
happily accepts `Đạm Urê` twice.

The fix is to stop asking the database to fold case at all. `name_key` is
computed here, stored as an ordinary column, and indexed as-is — so the
comparison is byte equality and gives the same answer on every cluster
regardless of how it was initdb'd.

See Error_Postgres_Locale_Case_Folding.md.
"""

from __future__ import annotations

import unicodedata


def normalise_key(value: str) -> str:
    """Fold a display name into a stable, locale-independent match key.

    `casefold()` rather than `lower()`: it is the Unicode-defined operation
    for caseless comparison, and unlike `lower()` it is designed for exactly
    this use.

    NFC normalisation first, because 'ế' can arrive either as one code point
    (U+1EBF) or as 'e' + two combining marks depending on the keyboard and OS
    the farmer typed it on. Those are the same character to a human and must
    be the same key.
    """
    return unicodedata.normalize("NFC", value).strip().casefold()
