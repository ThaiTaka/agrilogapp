# Error Report — `lower()` does not lowercase Vietnamese, so duplicate supplies slipped through

**Date:** 11 Aug 2026
**Affects:** Issue #23 (supply/inventory), and any future case-insensitive match
**Severity:** High — a silent correctness failure in the app's primary language
**Status:** Fixed in migration `0002`. Two regression tests added.

---

## 1. Error Description

Two tests failed together:

```
FAILED tests/test_supplies.py::TestCatalogue::test_duplicate_name_and_unit_conflicts
  AssertionError: assert 'đã có trong danh mục' in 'The request conflicts with existing data.'

FAILED tests/test_supplies.py::TestCatalogue::test_duplicate_check_is_case_insensitive
  AssertionError: assert 201 == 409
```

The first says the friendly Vietnamese message never appeared — the request was rejected by the generic `IntegrityError` handler instead, meaning the *database* caught the duplicate while the *service* did not.

The second is worse: creating `"đạm urê phú mỹ"` after `"Đạm Urê Phú Mỹ"` returned **201 Created**. Neither the service check nor the unique index caught it. Two inventory lines now exist for one physical sack of fertiliser, and every stock level derived from them is split in half.

---

## 2. Root Cause

**PostgreSQL's `lower()` folds case according to the database's collation. Under the `C` collation it only touches ASCII `A-Z`.**

Measured directly:

```
db collate/ctype : ('C', 'C')
pg  lower()      : 'Đạm urê phú mỹ'      ← Đ untouched
py  .lower()     : 'đạm urê phú mỹ'
AGREE            : False
```

Both failures follow from that one line:

| Layer | What it did | Why it failed |
|---|---|---|
| Service | `WHERE lower(name) = :python_lowered` | Compared `'Đạm urê phú mỹ'` (PG) against `'đạm urê phú mỹ'` (Python). Never matches, so the readable error never fires. |
| Unique index | `UNIQUE (household_id, lower(name), unit)` | `lower('Đạm Urê…')` and `lower('đạm urê…')` are *different strings*, so both rows are accepted. |

In test 1 the two names were byte-identical, so the index did catch it — via `IntegrityError`, hence the generic message. In test 2 the names differed only in case, so nothing caught it at all.

### Why this is not just a test-environment quirk

The throwaway test cluster was created with `initdb --locale=C`, which is what exposed it. A developer might reasonably conclude "use a proper locale and move on."

That conclusion is wrong, for three reasons:

1. **It makes application correctness depend on an `initdb` flag** chosen once, years ago, by whoever installed PostgreSQL. Nothing in the codebase asserts it. The next machine, the next CI container, the next deployment is a coin flip.
2. **CI containers commonly default to `C`.** The GitHub Actions workflow in Issue #18 runs `postgres:18` as a service container; `C`/`C.UTF-8` is a very live possibility. The bug would then appear only in CI, or only in production, but not on the developer's laptop — the worst possible distribution.
3. **`lower()` is not the correct operation anyway.** Unicode defines `casefold()` for caseless comparison; `lower()` is for display. They differ for real scripts.

### Why it was caught

Only because the tests use realistic Vietnamese data. `test_duplicate_check_is_case_insensitive` with `"Urea"`/`"urea"` — pure ASCII — passes against the broken code on every locale. Writing tests in the language the application is actually used in was the thing that made this visible.

---

## 3. Exact Step-by-Step Fix

**Stop asking the database to fold case.** Fold it in Python, store the result, and let the index compare bytes.

### 3.1 The normalisation function

`backend/app/core/text.py`:

```python
def normalise_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().casefold()
```

- **`casefold()`, not `lower()`** — the Unicode-defined operation for caseless comparison.
- **NFC first** — `â` can arrive as one code point (U+00E2) or as `a` + U+0302 depending on the keyboard and OS. Same character to a human; different bytes without normalisation.

### 3.2 Store the key

`supplies.name_key VARCHAR(160) NOT NULL`, maintained by `SupplyService` on every create and update. Derived from `name`, so it is **server-side only** and never enters a sync payload (the client keeps computing its own local hint with `toLowerCase()`).

### 3.3 Swap the index — migration `0002`

```python
op.add_column("supplies", sa.Column("name_key", sa.String(160), nullable=True))
op.execute("UPDATE supplies SET name_key = lower(trim(name)) WHERE name_key IS NULL")
op.alter_column("supplies", "name_key", nullable=False)

op.drop_index("uq_supply_name_unit", table_name="supplies")
op.create_index(
    "uq_supply_key_unit", "supplies",
    ["household_id", "name_key", "unit"],
    unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
)
```

> The backfill uses `lower()` — the very function this migration exists to stop trusting. That is deliberate and acceptable: it is the only fold available inside SQL, any existing row is development data, and the application rewrites `name_key` correctly the next time each row is updated. On a real dataset the backfill would instead be a one-off Python script iterating rows through `normalise_key`.

### 3.4 Compare on the key

```python
name_key = normalise_key(payload.name)
duplicate = db.execute(
    _scoped(household_id).where(Supply.name_key == name_key, Supply.unit == payload.unit)
).scalar_one_or_none()
```

Plain byte equality. Same answer on every cluster, whatever its collation.

### 3.5 Also fixed: the seed script

`app/seed.py` constructed `Supply(...)` directly and would have hit `name_key NOT NULL`. It now goes through `supply_service.create_supply`, which is the correct fix regardless — seeding via a parallel path is how a seed script ends up producing rows the application itself could never create.

---

## 4. Verification

```
184 passed in 29.12s
alembic downgrade base -> upgrade head -> current = 0002 (head)
ruff check app tests: All checks passed!
```

Two regression tests, both against a `C`-collation database:

- `test_duplicate_check_survives_a_c_locale_database` — asserts the stored key is exactly `"đạm urê phú mỹ"`, then rejects `"ĐẠM URÊ PHÚ MỸ"`, `"đạm urê phú mỹ"` and `"  Đạm Urê Phú Mỹ  "` with 409.
- `test_unicode_composition_is_normalised` — builds NFC and NFD forms of the same name with `unicodedata` and asserts they collide. Built programmatically on purpose: typed as literals, an editor would silently re-normalise the source file and the test would pass without testing anything.

---

## 5. Lesson for the Thesis Report

**Test with the data the application will actually hold.** An ASCII test fixture (`"Urea"`, `"Fertilizer A"`) passes against this bug on every locale, on every machine, forever. The bug is only reachable through Vietnamese text — which is to say, through every single real row this system will ever store. A test suite written in English would have shipped a Vietnamese app that cannot tell `Đạm Urê` from `đạm urê`.

**Locale is configuration, and correctness must not depend on configuration.** Anything decided at `initdb` time, in a Dockerfile, or by an installer's default is not a property of the code. It differs between the laptop, CI, and the server — so a bug that depends on it appears in exactly one of those three places, which is the hardest failure mode to diagnose. Where behaviour must be identical everywhere, compute it in the application and store the result.

This is the same principle already applied twice elsewhere in the project, which is worth noting as a pattern rather than three coincidences:

- **Dates** are stored as epoch-ms integers rather than `DATE`, so no timezone interpretation sits between the device and the server (§7.2).
- **The local calendar day** is fixed integer arithmetic on a UTC+7 constant rather than a `timezone()` call, so it is immutable and indexable (§7.2).
- **Case folding** is now Python `casefold()` stored in a column rather than SQL `lower()` evaluated per query.

In each case the rule is the same: *push ambiguity out of the database boundary and pin it down in code that is versioned, tested, and identical on both sides of the sync.*

---

*Related: [Data_Requirements_Database.md](Data_Requirements_Database.md) §5.5 (supplies), §8.3 (duplicate policy), §10.3 (uniqueness); [Error_Sync_Cursor_Transaction_Timestamp.md](Error_Sync_Cursor_Transaction_Timestamp.md) (the same class of "the database does not mean what you think" bug).*
