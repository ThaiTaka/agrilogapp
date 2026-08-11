# AgriLog

> **Ứng dụng quản lý nhật ký canh tác cây ngắn ngày, vật tư và chi phí nông nghiệp cho nông hộ**
> An offline-first mobile application that lets smallholder farming households log daily field work, track agricultural supply inventory, and measure cost / revenue / profit per crop season — with **full functionality while completely offline** and **automatic two-way synchronisation** when connectivity returns.

Graduation project — Faculty of Information Technology, Đà Lạt University (Trường Đại học Đà Lạt).
Advisor: **TS. Nguyễn Thị Lương** · Defense window: **13 – 15 Nov 2026**

---

## Table of Contents

1. [The Problem](#1-the-problem)
2. [Objectives & Feature Map](#2-objectives--feature-map)
3. [Architecture Overview](#3-architecture-overview)
4. [Technology Stack](#4-technology-stack)
5. [Repository Structure](#5-repository-structure)
6. [Prerequisites](#6-prerequisites)
7. [Backend Setup (FastAPI + PostgreSQL)](#7-backend-setup-fastapi--postgresql)
8. [Mobile Setup (React Native + WatermelonDB)](#8-mobile-setup-react-native--watermelondb)
9. [How Offline-First Sync Works](#9-how-offline-first-sync-works)
10. [Reports & Visualisation](#10-reports--visualisation)
11. [Project Roadmap (Milestones)](#11-project-roadmap-milestones)
12. [Branching Strategy & Workflow](#12-branching-strategy--workflow)
13. [Testing Strategy](#13-testing-strategy)
14. [Documentation Index](#14-documentation-index)
15. [AI Contribution Statement](#15-ai-contribution-statement)
16. [Author](#16-author)
17. [Getting This README onto GitHub](#17-getting-this-readme-onto-github)

---

## 1. The Problem

Short-cycle crop farming (cây ngắn ngày) is the primary, recurring income source for the majority of Vietnamese farming households. Yet record-keeping is still done manually or in scattered notebooks, which causes three concrete losses:

| Problem | Consequence |
|---|---|
| Work logs are handwritten or not kept at all | No traceable history of fertilising / spraying / harvesting |
| Supply usage is never reconciled against stock | Silent inventory shrinkage, unplanned re-purchasing |
| Costs and revenue are never tied to a season | Impossible to know whether a season was actually profitable |

**And the hard constraint:** the field is where the data is created, and the field usually has no stable mobile signal. Any solution that *requires* a network connection to record data will simply not be used — entry gets deferred to the evening, and deferred entry is inaccurate entry.

AgriLog therefore treats the **local device database as the source of truth for writing**, and the server as a durable, shareable mirror that reconciles later.

---

## 2. Objectives & Feature Map

The five objectives from the project proposal (Mục tiêu đề tài), mapped to what the app delivers:

| # | Objective (proposal) | Delivered feature |
|---|---|---|
| 1 | Quản lý nhật ký canh tác theo mùa vụ | Season CRUD + diary entries typed by work kind (bón phân / phun thuốc / thu hoạch / khác), filterable by season and work type |
| 2 | Quản lý vật tư (nhập – xuất – tồn kho thời gian thực) | Supply catalogue, stock-in / stock-out transactions, live computed on-hand level, low-stock flagging |
| 3 | Quản lý thu chi, tự động tính lợi nhuận theo mùa vụ | Expense & revenue records, auto-generated expense when a diary entry consumes supplies, per-season cost / revenue / profit summary |
| 4 | Hoạt động đầy đủ khi mất mạng + đồng bộ hai chiều chính xác | 100 % of CRUD runs against local SQLite; WatermelonDB `synchronize()` against a FastAPI push/pull contract with dedup + conflict resolution |
| 5 | Trực quan hóa báo cáo hỗ trợ ra quyết định | 3 charts: Income vs Expense over time, Supply Consumption by type, Season Profit Comparison |

**Plus the explicit content requirement from §3 of the proposal:** *tự động hoàn kho khi sửa/xóa nhật ký* — when a diary entry that consumed supplies is edited or deleted, the consumed stock is automatically reversed/adjusted. This is implemented **twice and symmetrically**: once in the FastAPI service layer, once in the WatermelonDB writer layer, so the inventory number is correct whether the edit happened online or in airplane mode.

---

## 3. Architecture Overview

```mermaid
graph TB
    subgraph Device["📱 Android Device (works with zero connectivity)"]
        UI["React Native UI<br/>Diary · Supplies · Finance · Reports"]
        HOOKS["Observable queries<br/>(withObservables)"]
        WDB["WatermelonDB<br/>Model + Query layer"]
        SQLITE[("SQLite<br/>local source of truth")]
        SYNC["Sync Adapter<br/>synchronize()"]

        UI <--> HOOKS
        HOOKS <--> WDB
        WDB <--> SQLITE
        WDB <--> SYNC
    end

    NET{{"🌐 Intermittent<br/>connectivity"}}
    SYNC <-.->|"push / pull batches"| NET

    subgraph Server["☁️ Backend"]
        API["FastAPI<br/>REST + Sync API"]
        AUTH["JWT auth<br/>household scoping"]
        SVC["Service layer<br/>stock restore · financial rollups"]
        ORM["SQLAlchemy 2.0 ORM<br/>+ Alembic migrations"]
        PG[("PostgreSQL<br/>durable system of record")]

        API --> AUTH
        API --> SVC
        SVC --> ORM
        ORM --> PG
    end

    NET <-.-> API
```

### Design principles

1. **Local-first writes.** No screen ever blocks on the network. Every create/update/delete commits to SQLite inside a WatermelonDB `writer` and returns immediately; the UI re-renders from an observable query, not from an HTTP response.
2. **The server never invents IDs.** Record IDs are generated on the client. This is what makes retrying a sync safe: re-sending a batch cannot produce duplicates because the primary key already exists.
3. **Schema parity.** The WatermelonDB schema mirrors the PostgreSQL schema table-for-table and field-for-field. Divergence is the #1 source of sync bugs, so any intentional difference (e.g. local denormalisation for fast list queries) must be recorded in `docs/database-schema.md`.
4. **Symmetric business logic.** Stock restore and expense auto-generation exist on both sides and must produce identical numbers. Any asymmetry surfaces as data drift after a sync.
5. **Server clock is the sync clock.** Sync cursors use the PostgreSQL server's time, never the device clock — a farmer's phone with a wrong date must not be able to poison the change feed.

---

## 4. Technology Stack

| Layer | Choice | One-line reason |
|---|---|---|
| Mobile framework | **React Native** (CLI, not Expo) | Needs native SQLite/JSI modules that Expo Go cannot load |
| Local database | **WatermelonDB** | The only RN persistence layer with a *built-in* two-way sync protocol and record-level change tracking |
| Local storage engine | **SQLite** (via WatermelonDB adapter) | Durable, transactional, ships with Android |
| Charts | **react-native-chart-kit** + react-native-svg | Covers all 3 required chart types, tiny API surface |
| Backend framework | **FastAPI** | Async, auto-generates the OpenAPI spec that documents the sync contract |
| ORM | **SQLAlchemy 2.0** | Explicit control over the transaction boundary the sync push handler needs |
| Migrations | **Alembic** | Versioned schema — required to keep the mobile schema version and server schema in lockstep |
| Database | **PostgreSQL** | Transactional integrity for batched sync writes; strong aggregate query support for reports |
| Auth | **JWT** (PyJWT) + **bcrypt** (called directly) | Stateless tokens work naturally with an intermittently-connected client |

> **Two deliberate substitutions inside the auth layer**, both made during implementation:
> - **PyJWT instead of python-jose.** python-jose has been effectively unmaintained since 2021; PyJWT is the actively maintained reference implementation.
> - **bcrypt called directly instead of via passlib.** passlib 1.7.4 reads `bcrypt.__about__.__version__`, which bcrypt 4.x removed — producing a noisy `AttributeError` traceback on every single hash. Calling bcrypt directly is a smaller dependency surface and sidesteps a known-broken interaction. The cost is handling bcrypt's 72-byte input limit ourselves, which `app/core/security.py` does explicitly rather than letting it truncate silently (see the test `test_diacritics_count_as_multiple_bytes` — a 40-character Vietnamese password is 120 bytes).

> ⚠️ **This differs from the original proposal on purpose.** The proposal listed Drift ORM (Flutter/Dart), fl_chart (Flutter), and "Prisma Schema" (Node.js ORM) — none of which run in a React Native + FastAPI stack. The substitutions and their rationale are documented in **[Tech_Stack_Overview.md](Tech_Stack_Overview.md)** and formalised as an ADR in `docs/adr/0001-tech-stack.md` (Issue #11).

---

## 5. Repository Structure

```
agrilogapp/
├── backend/                       # FastAPI service
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py            # DB session + current_household dependencies
│   │   │   └── v1/
│   │   │       ├── auth.py        # register / login          (Issue #14)
│   │   │       ├── seasons.py     # season CRUD               (Issue #19)
│   │   │       ├── diary.py       # diary entry CRUD          (Issue #21)
│   │   │       ├── supplies.py    # supplies + stock moves    (Issue #23)
│   │   │       ├── finance.py     # expenses / revenues       (Issue #27)
│   │   │       ├── reports.py     # 3 aggregation endpoints   (Issue #42)
│   │   │       └── sync.py        # push / pull               (Issues #31, #32)
│   │   ├── core/
│   │   │   ├── config.py          # pydantic-settings, reads .env
│   │   │   └── security.py        # hashing + JWT issue/verify
│   │   ├── db/
│   │   │   ├── base.py            # declarative Base + SyncMixin
│   │   │   └── session.py         # engine + SessionLocal
│   │   ├── models/                # SQLAlchemy ORM models     (Issue #7)
│   │   ├── schemas/               # Pydantic request/response models
│   │   ├── services/              # business logic: stock restore, rollups, sync
│   │   └── main.py                # app factory, /health, router wiring
│   ├── alembic/versions/          # migration history
│   ├── tests/                     # pytest suite
│   ├── alembic.ini
│   ├── requirements.txt
│   └── .env.example
│
├── mobile/                        # React Native app
│   ├── src/
│   │   ├── db/
│   │   │   ├── schema.ts          # WatermelonDB tableSchemas (Issue #8)
│   │   │   ├── migrations.ts      # schemaMigrations
│   │   │   ├── models/            # Model classes with decorators
│   │   │   └── index.ts           # Database + SQLiteAdapter singleton
│   │   ├── navigation/            # root stack + bottom tabs   (Issue #17)
│   │   ├── screens/
│   │   │   ├── auth/  seasons/  diary/  supplies/  finance/  reports/
│   │   ├── components/            # shared UI (SyncStatusBar, EmptyState, …)
│   │   ├── services/
│   │   │   ├── api.ts             # fetch wrapper + JWT header
│   │   │   ├── sync.ts            # synchronize() adapter      (Issue #34)
│   │   │   └── stock.ts           # local stock-restore logic  (Issue #26)
│   │   └── hooks/
│   ├── android/
│   └── package.json
│
├── docs/                          # design & thesis artefacts
│   ├── requirements.md            erd.png              database-schema.md
│   ├── sync-api.md                tech-stack.md        qa-checklist.md
│   └── adr/0001-tech-stack.md
│
├── .github/workflows/             # backend-ci.yml, mobile-ci.yml (Issue #18)
├── AgriLog_GitHub_Issues_and_Kanban.md   # 55 issues, 11 milestones
├── Tech_Stack_Overview.md
└── README.md
```

---

## 6. Prerequisites

Already installed on the development machine — listed here for reproducibility:

| Tool | Verified version | Notes |
|---|---|---|
| Python | 3.12.10 | 3.10+ required |
| PostgreSQL Server | 18 (verified) | 13+ required for built-in `gen_random_uuid()`; plus pgAdmin 4 |
| Node.js | 24.18.0 | 20+ required by current React Native |
| npm | 11.16.0 | |
| Android Studio | latest | with an AVD + Android SDK Platform 34/35 |
| Git | 2.54.0 | |
| JDK | 17 | bundled with Android Studio |

> **Note on Node 24:** React Native's supported range moves slower than Node's release cadence. If `npx react-native` throws an engine/`ERR_REQUIRE_ESM` error during Issue #15, install Node 20 LTS alongside via `nvm-windows` and pin it for the `mobile/` folder. Record the fix in `Error_Resolution_NodeVersion.md` per the project's error protocol.

---

## 7. Backend Setup (FastAPI + PostgreSQL)

All commands are **PowerShell** (the project's primary shell), run from the repo root.

### 7.1 Create the database

First confirm the server is actually running — on this machine the Windows service was never registered, so it does **not** start at boot:

```powershell
Get-NetTCPConnection -LocalPort 5432 -State Listen    # expect two rows
```

If that returns nothing, follow **[Error_PostgreSQL_Service_Missing.md](Error_PostgreSQL_Service_Missing.md)** before continuing.

```powershell
$psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"   # not on PATH by default
$env:PGPASSWORD = "<your postgres password>"
& $psql -U postgres -h localhost -c "CREATE DATABASE agrilog;"
& $psql -U postgres -h localhost -c "CREATE DATABASE agrilog_test;"   # used by pytest
Remove-Item Env:\PGPASSWORD
```

`agrilog_test` must be a **separate** database: the pytest session fixture runs `DROP SCHEMA public CASCADE` before applying migrations, so pointing it at `agrilog` would destroy your development data on every test run.

### 7.2 Create the virtual environment

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> If PowerShell blocks the activation script with *"running scripts is disabled on this system"*, unblock it for the current session only:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> ```

### 7.3 Install dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 7.4 Configure environment

```powershell
Copy-Item .env.example .env
```

Then edit `backend/.env`:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/agrilog
TEST_DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/agrilog_test
JWT_SECRET=change-me-to-a-long-random-string
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
CORS_ORIGINS=http://localhost:8081
```

> `ACCESS_TOKEN_EXPIRE_MINUTES` is deliberately long (7 days). A farmer may be offline for a week; forcing re-login before a sync is possible would defeat the entire premise of the app.

### 7.5 Run migrations & start the server

```powershell
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API docs (Swagger): <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

> `--host 0.0.0.0` matters: the Android emulator reaches the host machine at `10.0.2.2`, not `127.0.0.1`, so the server must not bind to loopback only.

### 7.6 Useful backend commands

```powershell
alembic revision --autogenerate -m "add stock_transactions"   # new migration
alembic downgrade -1                                          # roll back one
python -m app.seed                                            # sample dev data
pytest -q                                                     # run test suite
ruff check app tests                                          # lint
```

---

## 8. Mobile Setup (React Native + WatermelonDB)

```powershell
cd mobile
npm install
```

Point the app at the backend — `mobile/.env`:

```dotenv
API_BASE_URL=http://10.0.2.2:8000     # Android emulator → host machine
# API_BASE_URL=http://192.168.1.x:8000  # physical device on the same LAN
```

Start Metro and build to the emulator (launch the AVD from Android Studio first):

```powershell
npm start            # terminal 1 — Metro bundler
npm run android      # terminal 2 — build & install
```

### Verifying the offline guarantee

The single most important manual test in this project:

1. Launch the app and log in **once** while online (this caches the JWT).
2. Enable **airplane mode** on the emulator/device.
3. Create a season, log 3 diary entries with supply consumption, record an expense and a revenue, open all 3 report charts.
4. Everything must work with **no spinners, no errors, no empty states**.
5. Disable airplane mode, tap **Sync now**, and confirm the rows appear in pgAdmin.

If any step in (3) fails, the offline-first requirement is not met — that is the acceptance bar for Issues #38 and #47.

---

## 9. How Offline-First Sync Works

### 9.1 The write path (always local)

```
User taps Save
   └─> database.write(async () => { … })       // WatermelonDB writer block
         └─> row committed to SQLite
               ├─> _status = 'created' | 'updated'
               ├─> _changed = 'quantity,note'   // which fields changed locally
               └─> observable query re-emits → UI updates
```

The network is never on this path. `_status` and `_changed` are WatermelonDB's internal bookkeeping columns — they are what turn "the local DB" into "a queue of pending changes" without needing a separate outbox table.

### 9.2 The sync path

`synchronize()` runs a strict pull-then-push cycle:

```
┌── PULL ────────────────────────────────────────────────┐
│ GET /sync/pull?last_pulled_at=<ms>&schema_version=<n>   │
│   → server returns everything changed since the cursor  │
│   → client applies it, per-field-merging any record     │
│     that also has local edits                           │
└─────────────────────────────────────────────────────────┘
                          ↓
┌── PUSH ────────────────────────────────────────────────┐
│ POST /sync/push  { changes, lastPulledAt }              │
│   → server applies the whole batch in ONE transaction   │
│   → on success, client marks records _status='synced'   │
└─────────────────────────────────────────────────────────┘
```

**Pull response** (exactly the shape WatermelonDB's `synchronize()` expects):

```jsonc
{
  "changes": {
    "seasons": {
      "created": [ { "id": "a1b2…", "name": "Vụ Đông Xuân 2026", "crop_type": "Lúa",
                     "start_date": 1767225600000, "end_date": 1775001600000,
                     "created_at": 1767225600000, "updated_at": 1767225600000 } ],
      "updated": [ ],
      "deleted": [ ]
    },
    "diary_entries": { "created": [], "updated": [], "deleted": ["c3d4…"] },
    "supplies":      { "created": [], "updated": [], "deleted": [] },
    "stock_transactions": { "created": [], "updated": [], "deleted": [] },
    "expenses":      { "created": [], "updated": [], "deleted": [] },
    "revenues":      { "created": [], "updated": [], "deleted": [] }
  },
  "timestamp": 1767312000000
}
```

`timestamp` is the **server's** clock in epoch milliseconds and becomes the client's next `last_pulled_at`. `deleted` carries bare ID strings, which is why the server keeps tombstones (a `deleted_at` column) rather than hard-deleting rows — a hard delete is invisible to a device that was offline when it happened.

**Push request** is the same `changes` envelope, sent from the client.

### 9.3 Deduplication

Every record's primary key is a **client-generated ID**, created on the device at insert time. The push handler therefore does an *upsert keyed on that ID*:

- Sync succeeds but the response is lost to a dropped connection → the client retries the identical batch → the server upserts the same IDs → **zero duplicates**.

This is why the ID strategy is a design decision (Issue #9), not an implementation detail. With server-assigned IDs, an interrupted push is genuinely ambiguous and duplicates become unavoidable.

### 9.4 Conflict resolution

Two devices editing the same record while both offline is resolved at two layers:

| Layer | Rule |
|---|---|
| **Server** (`/sync/push`) | **Last-write-wins by `updated_at`.** An incoming record whose `updated_at` is older than the stored row is rejected for that row and reported back per-record — it never silently clobbers newer data. |
| **Client** (on pull) | **Per-field merge.** For a record with local unsynced edits, WatermelonDB keeps the locally-changed fields listed in `_changed` and applies the server's values only to the untouched fields. The farmer never loses the note they just typed because someone else edited the quantity. |

The full contract, including per-record error reporting and the retry/backoff policy for flaky rural connectivity, lives in `docs/sync-api.md` (Issue #9) and is exercised by the two-device tests in Issue #40.

### 9.5 Atomicity

The push handler wraps the entire batch in a single database transaction. A connection dropped mid-push leaves PostgreSQL **exactly as it was before**; the client still holds every record at `_status = 'created'/'updated'` and retries the whole batch. There is no partial-apply state to reconcile — the design deliberately trades a little wasted bandwidth for the guarantee that the database is never half-updated (Issue #36).

---

## 10. Reports & Visualisation

Three charts, all computed from **local** WatermelonDB data so they render in airplane mode, with the backend aggregation endpoints (Issue #42) available as a cross-check and for a future web view:

| Chart | Type | Question it answers | Local query | API |
|---|---|---|---|---|
| Income vs Expense | Line / Bar | *Am I spending faster than I'm earning this season?* | expenses + revenues grouped by period, filtered by season | `GET /reports/income-expense` |
| Supply Consumption | Pie / Bar | *Which inputs are eating my budget?* | stock_transactions of type `out` grouped by supply category | `GET /reports/supply-consumption` |
| Season Comparison | Bar | *Which season actually performed best?* | per-season Σrevenue − Σexpense | `GET /reports/season-comparison` |

---

## 11. Project Roadmap (Milestones)

Dates come directly from the *Kế hoạch thực hiện* table in the proposal. Full issue breakdown: **[AgriLog_GitHub_Issues_and_Kanban.md](AgriLog_GitHub_Issues_and_Kanban.md)**.

| Milestone | Scope | Dates (2026) | Issues |
|---|---|---|---|
| M1 | Requirements Analysis & Planning | Aug 10 – Aug 16 | #1 – #5 |
| M2 | Detailed Design | Aug 17 – Aug 26 | #6 – #11 |
| M3 | Backend & Mobile Foundation | Aug 27 – Sep 9 | #12 – #18 |
| M4 | Farming Diary & Cost Module | Sep 10 – Sep 23 | #19 – #29 |
| M5 | Progress Report 1 | Sep 24 – Sep 28 | #30 |
| M6 | Sync Engine | Sep 29 – Oct 12 | #31 – #36 |
| M7 | Offline & Sync Testing | Oct 13 – Oct 22 | #37 – #41 |
| M8 | Reports & Visualisation | Oct 23 – Nov 1 | #42 – #47 |
| M9 | Progress Report 2 | Nov 2 – Nov 5 | #48 |
| M10 | Optimization & Final Documentation | Nov 6 – Nov 12 | #49 – #54 |
| M11 | Final Defense | Nov 13 – Nov 15 | #55 |

> **Single-owner note.** The issue document assigns work across two developers (Thai / Khoa). This implementation is being carried out by a single developer, so every issue is single-owner; the assignee column should be read as *"which side of the stack this touches"* rather than *"who does it."*

---

## 12. Branching Strategy & Workflow

```
main      ← protected. Only receives reviewed PRs from develop. Always demo-ready.
develop   ← integration branch. All feature branches merge here first.
feature/* ← one branch per issue, e.g. feature/21-diary-log-api
fix/*     ← bug fixes from the QA milestone, e.g. fix/41-stock-restore-rounding
docs/*    ← documentation-only changes
```

Commit convention (Conventional Commits):

```
<type>(<scope>): <subject>       #<issue>

feat(sync): implement push endpoint with transactional batch apply   #31
fix(mobile): restore stock on diary entry delete while offline       #26
docs(readme): document sync contract                                 #1
```

Types: `feat` · `fix` · `docs` · `test` · `refactor` · `perf` · `chore`
Scopes: `backend` · `mobile` · `db` · `sync` · `reports` · `auth` · `ci`

Closing an issue from a PR: put `Closes #21` in the PR body — GitHub closes the issue and the Projects board auto-moves the card to **Done**.

---

## 13. Testing Strategy

| Level | Tooling | What it protects |
|---|---|---|
| Schema parity | `pytest` (no DB needed) | ORM models vs Alembic migrations rendered to SQL and compared structurally — catches the drift that otherwise surfaces as a random `UndefinedColumn` in an unrelated request |
| Backend unit | `pytest` | Stock-restore arithmetic, financial rollups, conflict resolution rules |
| Backend integration | `pytest` + `TestClient` + test DB | Auth scoping, full sync push/pull round-trip, idempotent re-push |
| Backend load | custom script (Issue #39) | 500+ queued changes from a device offline for weeks |
| Mobile unit | `jest` | Local stock-restore logic, chart data reducers |
| Manual offline | airplane-mode checklist (Issue #38) | The core promise: every module works with no network |
| Manual multi-device | 2 emulators (Issue #40) | Conflict resolution behaves as documented, with no silent data loss |

CI runs lint + tests on every push and PR for both codebases (Issue #18) and is required to pass before merging to `main`.

---

## 14. Documentation Index

| Document | Contents | Issue |
|---|---|---|
| [Tech_Stack_Overview.md](Tech_Stack_Overview.md) | Why each technology was chosen, and the AI collaboration record | #5, #11 |
| [Data_Requirements_Database.md](Data_Requirements_Database.md) | **Authoritative data model** — ERD, table specs, sync metadata, PG ↔ WatermelonDB parity, invariants, index plan | #6, #7, #8, #9 |
| [AgriLog_GitHub_Issues_and_Kanban.md](AgriLog_GitHub_Issues_and_Kanban.md) | All 55 issues, 11 milestones, Kanban setup guide | #1 |
| `docs/requirements.md` | Functional & non-functional requirements | #2 |
| `docs/personas.md` | Personas and user stories | #3 |
| `docs/architecture.md` + `docs/erd.png` | Architecture write-up and ERD | #4, #6 |
| `docs/database-schema.md` | Table-by-table schema decisions, PG ↔ WatermelonDB parity | #6, #8 |
| `docs/sync-api.md` | Full sync contract, conflict & dedup strategy | #9 |
| `docs/adr/0001-tech-stack.md` | Architecture Decision Record | #11 |
| `docs/qa-checklist.md` | Regression checklist | #51 |
| `Data_Requirements_*.md` | Per-module data model specs, written before each module starts | — |
| [Error_PostgreSQL_Service_Missing.md](Error_PostgreSQL_Service_Missing.md) | PostgreSQL 18 server service not registered — diagnosis and fix | #13 |
| [Error_Sync_Cursor_Transaction_Timestamp.md](Error_Sync_Cursor_Transaction_Timestamp.md) | `now()` vs `clock_timestamp()` — a silent data-loss bug in the pull cursor | #9, #32 |
| [Error_Postgres_Locale_Case_Folding.md](Error_Postgres_Locale_Case_Folding.md) | `lower()` does not lowercase Vietnamese under the `C` collation | #23 |
| `Error_*.md` | Error description → root cause → exact fix, one file per incident | — |

---

## 15. AI Contribution Statement

This project was developed with **Claude (Anthropic)**, operating inside VS Code as a pair-programming and architecture assistant. In the interest of academic honesty, the division of labour is stated explicitly:

**AI-assisted:**
- System architecture design (offline-first topology, sync data flow, conflict-resolution strategy)
- Database schema design and the PostgreSQL ↔ WatermelonDB parity mapping
- Implementation code across the FastAPI backend and React Native client, including the sync engine
- Test design and troubleshooting, captured in `Error_Resolution_*.md` files
- Technical documentation, including this README

**Developer-owned (Lê Thành Thái):**
- Problem definition, scope, and all requirements originating from the thesis proposal
- Every technical decision — accepting, rejecting, or amending AI-proposed designs
- Environment setup, execution, debugging, and verification on real hardware
- All testing and validation against the acceptance criteria
- The thesis report, defense presentation, and defense itself

A fuller account of the AI's role appears in [Tech_Stack_Overview.md § AI Contribution](Tech_Stack_Overview.md#8-ai-contribution--collaboration-record) and will be reproduced in the final thesis report (Issue #52).

---

## 16. Author

| Name | Student ID | Role |
|---|---|---|
| **Lê Thành Thái** | 2212456 | Full-stack implementation — backend, mobile, sync engine, documentation |

Original proposal co-author: Nguyễn Hoàng Anh Khoa (2212394)
Advisor: TS. Nguyễn Thị Lương — Faculty of Information Technology, Đà Lạt University

---

## 17. Getting This README onto GitHub

This folder is **not yet a Git repository**. Run these commands **exactly as written**, from `d:\agrilogapp` in PowerShell.

### Step 1 — One-time Git identity (skip if already configured)

```powershell
git config --global user.name "Le Thanh Thai"
git config --global user.email "lethanhthai0805@gmail.com"
```

### Step 2 — Initialise the repository

```powershell
git init
git branch -M main
```

### Step 3 — Stage and commit

```powershell
git add README.md Tech_Stack_Overview.md .gitignore AgriLog_GitHub_Issues_and_Kanban.md
git status
```

Check the `git status` output before committing — nothing unexpected (no `.venv`, no `node_modules`, no `.env`) should be listed. Then:

```powershell
git commit -m @'
docs: add project README and tech stack overview

Adds the foundational documentation for AgriLog: project overview,
architecture, setup instructions for the FastAPI backend and React
Native client, and a description of the offline-first sync design.

Closes #1
'@
```

> The `@'` … `'@` block is a PowerShell **here-string** for multi-line commit messages. The closing `'@` **must** be at the very start of its line with no leading spaces, or PowerShell throws a parse error.
> Prefer a single line? Use `git commit -m "docs: add project README and tech stack overview"` instead.

### Step 4 — Connect to GitHub and push

Create the empty repository at <https://github.com/new> named **`agrilogapp`** under the `ThaiTaka` account first — **without** a README, `.gitignore`, or licence, so the first push isn't rejected for divergent history.

```powershell
git remote add origin https://github.com/ThaiTaka/agrilogapp.git
git remote -v
git push -u origin main
```

### Step 5 — Create the `develop` branch (required by Issue #1)

```powershell
git checkout -b develop
git push -u origin develop
git checkout main
```

Then on GitHub: **Settings → Branches → Add branch protection rule** for `main` — enable *Require a pull request before merging*, and later *Require status checks to pass* once CI exists (Issue #18).

---

### Troubleshooting the push

| Symptom | Cause | Fix |
|---|---|---|
| `remote origin already exists` | Remote configured previously | `git remote set-url origin https://github.com/ThaiTaka/agrilogapp.git` |
| `Updates were rejected because the remote contains work you do not have` | GitHub auto-created a README | `git pull --rebase origin main` then push again |
| Browser opens asking to authenticate | Git Credential Manager | Sign in to GitHub in the browser; credentials are cached afterwards |
| `Support for password authentication was removed` | Using an account password | Generate a Personal Access Token (Settings → Developer settings → PAT → *Fine-grained*, `Contents: Read and write`) and use it as the password |
| `src refspec main does not match any` | No commit exists yet | Step 3 was skipped or failed — run `git log --oneline` to confirm |

---

*This README is a living document. As modules land, update §5 (structure), §9 (sync behaviour) and §13 (testing) to reflect what was actually built — the thesis report in Issue #52 draws directly from this file.*
