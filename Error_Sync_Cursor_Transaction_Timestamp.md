# Error Report — Sync pull cursor could silently skip records forever

**Date:** 11 Aug 2026
**Affects:** Issues #9 (sync contract), #31/#32 (push/pull), #40 (multi-device conflict testing)
**Severity:** **Critical** — silent, permanent data loss. Caught before any client existed.
**Status:** Fixed in migration `0001`. Regression test added. Residual window closed by a documented cursor safety margin.

---

## 1. Error Description

The failing test:

```
FAILED tests/test_schema_integrity.py::TestTriggerKeepsPullCursorHonest
       ::test_raw_sql_update_still_bumps_the_cursor

AssertionError: raw UPDATE did not bump server_updated_at
assert datetime(2026, 8, 11, 15, 7, 1, 815884, tzinfo=ZoneInfo('Asia/Bangkok'))
     > datetime(2026, 8, 11, 15, 7, 1, 815884, tzinfo=ZoneInfo('Asia/Bangkok'))
```

The two timestamps are **identical to the microsecond**. An `INSERT` followed by an `UPDATE` on the same row, in the same transaction, produced the same `server_updated_at`.

The first instinct — "the trigger is not firing" — is wrong. The trigger fires correctly. The value it writes is wrong.

---

## 2. Root Cause

**`now()` in PostgreSQL is `transaction_timestamp()`, not the current time.**

Every statement inside one transaction receives the moment the *transaction* began. This is documented, standard-mandated behaviour, and it is exactly what you want for `created_at`-style bookkeeping. It is exactly wrong for a cursor-based change feed.

The original trigger:

```sql
CREATE OR REPLACE FUNCTION touch_server_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.server_updated_at := now();   -- transaction start time
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### Why this is data loss, not cosmetics

`server_updated_at` is the **pull cursor** (`Data_Requirements_Database.md` §6.5). The pull endpoint answers "give me everything changed since T", and the client stores the returned timestamp as its next cursor. A row whose `server_updated_at` is older than a cursor the client has already stored **will never be returned again**.

```
             T1        T2      T3        T4         T5      T6
Txn A     starts ───────────────────────────── writes ──── commits
                                                (stamped T1)
Txn B                starts ─── commits
                                (stamped T2, visible from T3)

Client PULL at T4  →  sees B's rows, stores cursor = T4
Txn A commits at T6 →  its rows carry server_updated_at = T1

Next PULL asks for  server_updated_at > T4
   → A's rows (T1) do not match. They never will.
```

The farmer's diary entry exists in PostgreSQL, is visible in pgAdmin, and is **permanently invisible to every device**. Nothing errors. Nothing logs. The only symptom is a farmer insisting they recorded something that is not in the app — the least debuggable class of bug this project can produce.

### Why it was caught

Only because the test harness runs each test inside a single transaction that is rolled back afterwards. That made the INSERT and the UPDATE share a transaction, which is precisely the condition that exposes the flaw. Under manual testing — one HTTP request per transaction — `now()` and `clock_timestamp()` are indistinguishable, and this would have shipped.

A per-request transaction is short. But a sync **push** applies an entire batch in one transaction by design (§6.6, atomicity requirement), and a device offline for three weeks can push hundreds of records. That transaction is long enough for a concurrent pull to step over it.

---

## 3. Exact Step-by-Step Fix

### 3.1 Use statement time, not transaction time

`backend/alembic/versions/0001_initial_schema.py`:

```python
op.execute(
    """
    CREATE OR REPLACE FUNCTION touch_server_updated_at() RETURNS trigger AS $$
    BEGIN
        NEW.server_updated_at := clock_timestamp();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)
```

| Function | Returns | Constant within a transaction? |
|---|---|---|
| `now()` / `transaction_timestamp()` | when the transaction began | yes ← the bug |
| `statement_timestamp()` | when the current statement began | no |
| `clock_timestamp()` | actual current time, per call | no ← correct |

`clock_timestamp()` is right rather than `statement_timestamp()` because a single `UPDATE ... WHERE` statement touching many rows should not stamp them all identically; per-row real time keeps the feed strictly ordered.

> **Migration 0001 was edited in place rather than superseded by 0002.** This is normally poor practice, but the migration had not been applied to any real database at the time of the fix — only to a throwaway test cluster. A follow-up revision would have left every future developer's `agrilog` database carrying a broken trigger for one revision. If you have already run `alembic upgrade head` against a database you care about, do **not** re-pull and assume you are fixed; run §3.4 instead.

### 3.2 Close the residual window with a cursor safety margin

`clock_timestamp()` fixes the long-transaction case but not a subtler one: a row is *stamped* when written and only becomes *visible* when its transaction commits. A transaction that writes at T5 and commits at T8 is invisible to a pull running at T6 — which then stores cursor T6 and skips it.

The pull endpoint therefore rewinds its cursor before querying. Added to `backend/app/core/config.py`:

```python
SYNC_CURSOR_SAFETY_MARGIN_MS: int = 2_000
```

and the pull query (Issue #32) uses:

```python
effective_cursor = last_pulled_at - settings.SYNC_CURSOR_SAFETY_MARGIN_MS
```

**Re-delivering a row is harmless.** Record IDs are client-generated (rule R1) and the client applies changes as an upsert, so a duplicate pull is a no-op. The design trades a few redundant rows per sync for the impossibility of a lost one — the same trade already made in §6.5 for capturing `now_ts` before reading rather than after.

The margin must exceed the longest write transaction. 2 seconds comfortably covers a 500-record push batch; Issue #39's load test measures this and the value is revisited there.

### 3.3 Regression test

`backend/tests/test_schema_integrity.py::test_cursor_advances_within_a_single_transaction`
inserts two rows in one transaction and asserts their timestamps differ. It fails immediately if anyone reverts the trigger to `now()`.

### 3.4 If you already migrated a database

The trigger is replaced without touching data:

```powershell
cd d:\agrilogapp\backend
$env:PGPASSWORD = "<your postgres password>"
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -d agrilog -c @"
CREATE OR REPLACE FUNCTION touch_server_updated_at() RETURNS trigger AS `$`$
BEGIN
    NEW.server_updated_at := clock_timestamp();
    RETURN NEW;
END;
`$`$ LANGUAGE plpgsql;
"@
Remove-Item Env:\PGPASSWORD
```

`CREATE OR REPLACE FUNCTION` updates the function in place; the six triggers already point at it by name and need no changes.

Verify:

```sql
SELECT prosrc FROM pg_proc WHERE proname = 'touch_server_updated_at';
-- must contain clock_timestamp(), not now()
```

---

## 4. Verification

```
102 passed in 10.64s          (was: 100 passed, 2 failed)
alembic downgrade base -> upgrade head -> current = 0001 (head)
ruff check app tests: All checks passed!
```

---

## 5. Lesson for the Thesis Report

This belongs in the report's *testing* chapter, because it is the clearest available evidence that the test strategy earns its cost.

The bug is invisible to every form of manual testing. Click through the app and it works. Sync a device and it works. It only appears when two operations share one transaction and a third party reads in between — a race that manual testing cannot reliably produce, and whose only symptom in production is a farmer saying "I definitely wrote that down."

Two properties of the harness turned an unfindable production bug into a two-line diff:

1. **Tests run inside a transaction that is rolled back.** Chosen for isolation and speed. It happened to reproduce the exact condition that exposes the flaw — a reminder that a good harness catches things it was not designed to catch.
2. **The assertion was on behaviour, not existence.** A weaker test — "does a trigger named `trg_seasons_...` exist?" — passes against the broken version. Asserting that the timestamp *actually advances* is what caught it.

**Generalisable rule, now applied across the sync engine:** never assume a timestamp function returns the current time. In PostgreSQL, `now()` does not. Any monotonic-cursor design must state which clock it uses and why, and must tolerate re-delivery — because a feed that can skip is unfixable after the fact, while a feed that occasionally repeats is merely slightly wasteful.

---

*Related: [Data_Requirements_Database.md](Data_Requirements_Database.md) §6.1 (sync block), §6.5 (pull cursor contract), §6.6 (push atomicity).*
