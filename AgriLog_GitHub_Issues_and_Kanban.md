# AgriLog App — GitHub Issues & Kanban Setup Guide

Repo: https://github.com/ThaiTaka/agrilogapp

Source: `Thai_Khoa_DeCuongDeTai.docx` ("Xây dựng ứng dụng quản lý nhật ký canh tác cây ngắn ngày, vật tư và chi phí nông nghiệp cho nông hộ")

---

## Assumptions & Stack Notes (please confirm)

- **Local offline storage:** WatermelonDB (replacing the "Drift ORM" mentioned in the original doc, which is a Flutter/Dart library).
- **Charts:** `react-native-chart-kit` for the 3 required report charts (replacing "fl_chart"). If you later want richer interactivity/animation, `Victory Native` is a drop-in alternative — swap it in Issue #43 only, nothing else changes.
- **"Prisma Schema" in the original design phase:** Prisma is a Node.js/TypeScript ORM, which doesn't match a FastAPI + PostgreSQL backend. I've assumed this really means "design the backend data schema," and mapped it to **SQLAlchemy models + Alembic migrations** (Issue #7). Flag this if you intended something else.
- **Dates** are taken directly from the "Kế hoạch thực hiện" table in the doc (all in 2026).
- **"Both" as assignee** means either genuine pair work, or a task that needs sign-off/integration from both sides (e.g. connecting backend and mobile, testing, documentation, defense prep). Split these however works for your schedules.
- Backend stack throughout: **FastAPI + PostgreSQL**. Mobile stack throughout: **React Native + WatermelonDB**.

---

## Milestones Overview

| # | Milestone (GitHub) | Dates | Source Phase |
|---|---|---|---|
| M1 | Requirements Analysis & Planning | Aug 10 – Aug 16, 2026 | Phân tích đề tài |
| M2 | Detailed Design | Aug 17 – Aug 26, 2026 | Thiết kế chi tiết |
| M3 | Backend & Mobile Foundation | Aug 27 – Sep 9, 2026 | Xây dựng nền tảng |
| M4 | Farming Diary & Cost Module | Sep 10 – Sep 23, 2026 | Module Nhật ký & Chi phí |
| M5 | Progress Report 1 | Sep 24 – Sep 28, 2026 | Báo cáo tiến độ lần 1 |
| M6 | Sync Engine | Sep 29 – Oct 12, 2026 | Sync Engine |
| M7 | Offline & Sync Testing | Oct 13 – Oct 22, 2026 | Kiểm thử ngoại tuyến & đồng bộ |
| M8 | Reports & Visualization | Oct 23 – Nov 1, 2026 | Module Báo cáo & Trực quan hóa |
| M9 | Progress Report 2 | Nov 2 – Nov 5, 2026 | Báo cáo tiến độ lần 2 |
| M10 | Optimization & Final Documentation | Nov 6 – Nov 12, 2026 | Tối ưu & hoàn thiện báo cáo |
| M11 | Final Defense | Nov 13 – Nov 15, 2026 | Báo cáo bảo vệ đồ án |

**How to use this doc:** for each issue below, copy the **Title** as-is into GitHub's "Title" field, and copy everything inside the fenced ```` ```markdown ```` block into the "Leave a comment" body field. Assign the person listed, add the labels listed (create any that don't exist yet — GitHub lets you create labels on the fly from the issue sidebar), and attach it to the matching milestone.

---

## M1 — Requirements Analysis & Planning (Aug 10 – Aug 16, 2026)

### Issue 1 — Set up GitHub repository structure, branch strategy & project board
**Assignee:** Both
**Labels:** `chore`, `project-setup`

```markdown
## Description
Establish the repository conventions the team will use for the rest of the project: branching model, PR process, issue/label taxonomy, and the initial GitHub Projects board.

## Acceptance Criteria
- [ ] Repo has a documented branching strategy (e.g. `main` + `develop` + feature branches) in the README or CONTRIBUTING.md
- [ ] Branch protection enabled on `main` (require PR review before merge)
- [ ] Standard label set created (backend, mobile, database, api, sync, offline, testing, documentation, bug, enhancement, chore)
- [ ] GitHub Projects board created with To-do / In Progress / Done columns

## Sub-tasks
- [ ] Create `main` and `develop` branches
- [ ] Add branch protection rules
- [ ] Create CONTRIBUTING.md with commit message & PR conventions
- [ ] Create labels listed above
- [ ] Create GitHub Projects (v2) board
```

### Issue 2 — Write functional & non-functional requirements document
**Assignee:** Both
**Labels:** `documentation`, `planning`

```markdown
## Description
Consolidate the goals from the project proposal (season/diary logging, supply/inventory tracking, income-expense tracking, offline-first + two-way sync, reporting) into a concrete requirements document that both developers can build against.

## Acceptance Criteria
- [ ] Functional requirements cover all 5 goals from the proposal (diary, supplies, finance, offline-first, reports)
- [ ] Non-functional requirements defined (offline availability target, sync latency target, data consistency guarantees)
- [ ] Document reviewed and agreed by both Thai and Khoa

## Sub-tasks
- [ ] List functional requirements per module
- [ ] List non-functional requirements (performance, offline reliability, data integrity)
- [ ] Add document to `/docs/requirements.md`
```

### Issue 3 — Define user personas & user stories for farming households
**Assignee:** Both
**Labels:** `documentation`, `planning`, `ux`

```markdown
## Description
Define who the app is for (smallholder farming households managing short-term crop seasons) and write user stories that will drive screen design and acceptance criteria for later issues.

## Acceptance Criteria
- [ ] At least 1-2 primary personas documented
- [ ] User stories written for each core module (diary, supplies, finance, reports)
- [ ] Stories follow "As a [user], I want [goal], so that [benefit]" format

## Sub-tasks
- [ ] Draft persona(s)
- [ ] Write user stories for diary logging
- [ ] Write user stories for supply/inventory management
- [ ] Write user stories for income/expense tracking
- [ ] Write user stories for reports
```

### Issue 4 — Design high-level system architecture (offline-first + sync)
**Assignee:** Thai
**Labels:** `architecture`, `backend`, `documentation`

```markdown
## Description
Produce a high-level architecture diagram and write-up covering the mobile client (React Native + WatermelonDB), the backend (FastAPI + PostgreSQL), and how they communicate via the Sync API. This becomes the reference doc for Milestone 2's detailed design work.

## Acceptance Criteria
- [ ] Architecture diagram shows client, API layer, database, and sync flow
- [ ] Document explains offline-first data flow (local write → queued → synced)
- [ ] Document explains conflict-resolution approach at a high level

## Sub-tasks
- [ ] Draw architecture diagram (e.g. in draw.io / Excalidraw, export to `/docs`)
- [ ] Write architecture overview doc
- [ ] Review with Khoa for mobile-side feasibility
```

### Issue 5 — Evaluate & finalize React Native offline-storage and chart libraries
**Assignee:** Khoa
**Labels:** `research`, `mobile`, `documentation`

```markdown
## Description
Confirm WatermelonDB as the offline storage layer and react-native-chart-kit as the charting library (replacing the Drift ORM / fl_chart references from the original Flutter-based proposal), and document the decision with rationale.

## Acceptance Criteria
- [ ] WatermelonDB spike: confirm it supports the schema/sync patterns needed
- [ ] Chart library spike: confirm react-native-chart-kit (or alternative) supports the 3 required chart types
- [ ] Decision documented in `/docs/tech-stack.md`

## Sub-tasks
- [ ] Build a throwaway RN app with WatermelonDB and verify basic CRUD + sync hooks
- [ ] Prototype one chart with react-native-chart-kit
- [ ] Document findings and final library choices
```

---

## M2 — Detailed Design (Aug 17 – Aug 26, 2026)

### Issue 6 — Design PostgreSQL database schema
**Assignee:** Thai
**Labels:** `database`, `backend`, `design`

```markdown
## Description
Design the full relational schema covering households/users, crop seasons, diary entries, supplies/inventory, stock transactions, and financial records (costs, revenue, profit).

## Acceptance Criteria
- [ ] ERD covers: users/households, seasons, diary_entries, supplies, stock_transactions, expenses, revenues
- [ ] Relationships and foreign keys defined (e.g. diary_entry → supply consumption → stock_transaction)
- [ ] Schema supports per-season profit calculation
- [ ] Schema reviewed with Khoa so the WatermelonDB schema can mirror it

## Sub-tasks
- [ ] Draft ERD (tool of choice, export to `/docs/erd.png`)
- [ ] Define tables, columns, types, constraints
- [ ] Define indexes for common queries (by season, by date)
- [ ] Document schema decisions in `/docs/database-schema.md`
```

### Issue 7 — Set up SQLAlchemy models & Alembic migrations skeleton
**Assignee:** Thai
**Labels:** `database`, `backend`

```markdown
## Description
Translate the ERD from Issue #6 into SQLAlchemy ORM models, and set up Alembic for version-controlled migrations. This is the FastAPI/PostgreSQL equivalent of the "Prisma Schema" step mentioned in the original proposal.

## Acceptance Criteria
- [ ] SQLAlchemy models created for all core tables
- [ ] Alembic initialized and configured against the PostgreSQL instance
- [ ] Initial migration generates the full schema successfully
- [ ] `alembic upgrade head` / `alembic downgrade base` both work cleanly

## Sub-tasks
- [ ] Install & configure SQLAlchemy + Alembic
- [ ] Write models for users, seasons, diary_entries, supplies, stock_transactions, expenses, revenues
- [ ] Generate and review initial migration
- [ ] Add migration instructions to README
```

### Issue 8 — Design WatermelonDB local schema (mirrors backend schema)
**Assignee:** Khoa
**Labels:** `database`, `mobile`, `offline`

```markdown
## Description
Design the local WatermelonDB schema and model classes so they mirror the backend PostgreSQL schema closely enough to keep the future sync engine simple.

## Acceptance Criteria
- [ ] WatermelonDB schema defined for all tables needed on-device (seasons, diary_entries, supplies, stock_transactions, expenses, revenues)
- [ ] Each table includes the metadata WatermelonDB needs for sync (`_status`, `_changed`, server `id` mapping)
- [ ] Schema reviewed against Thai's PostgreSQL schema for field-name/type parity

## Sub-tasks
- [ ] Define WatermelonDB `schema.js`/`schema.ts`
- [ ] Define Model classes per table
- [ ] Cross-check field names/types against backend schema
- [ ] Document any intentional differences (e.g. denormalization for local queries)
```

### Issue 9 — Design Sync API contract (push/pull, conflict resolution)
**Assignee:** Thai
**Labels:** `api`, `backend`, `sync`, `design`

```markdown
## Description
Specify the Sync API contract that the mobile app will call to push local changes and pull remote changes, including how conflicts and duplicates are handled. This is the foundation for Milestone 6's Sync Engine work.

## Acceptance Criteria
- [ ] `POST /sync/push` and `GET /sync/pull` (or WatermelonDB-compatible equivalents) specified with request/response shapes
- [ ] Conflict resolution strategy chosen and documented (e.g. last-write-wins with timestamps, or per-field merge)
- [ ] Deduplication strategy documented (idempotency keys / client-generated UUIDs)
- [ ] Contract reviewed with Khoa against WatermelonDB's `synchronize()` expectations

## Sub-tasks
- [ ] Write OpenAPI spec / doc for push and pull endpoints
- [ ] Decide on conflict-resolution algorithm
- [ ] Decide on ID strategy (client UUID vs server-assigned)
- [ ] Document contract in `/docs/sync-api.md`
```

### Issue 10 — Design UI/UX wireframes for core screens
**Assignee:** Both
**Labels:** `design`, `ux`, `mobile`

```markdown
## Description
Produce wireframes for the core app screens: season list/detail, diary entry form/list, supply inventory, income/expense entry, and the reports dashboard.

## Acceptance Criteria
- [ ] Wireframes cover: onboarding/login, season list, diary entry form, supply inventory, income/expense entry, reports dashboard
- [ ] Wireframes reflect offline-first cues (e.g. sync status indicator, pending-change badges)
- [ ] Reviewed and agreed by both developers before mobile build starts

## Sub-tasks
- [ ] Wireframe season management screens
- [ ] Wireframe diary logging screens
- [ ] Wireframe supply/inventory screens
- [ ] Wireframe income/expense screens
- [ ] Wireframe reports/charts screens
```

### Issue 11 — Finalize & document tech stack decisions (ADR)
**Assignee:** Both
**Labels:** `documentation`, `architecture`

```markdown
## Description
Write a short Architecture Decision Record confirming the final stack: React Native + WatermelonDB on mobile, FastAPI + PostgreSQL on backend, and react-native-chart-kit for charts — explicitly noting the departure from the original Flutter/Drift/fl_chart proposal.

## Acceptance Criteria
- [ ] ADR document created listing each technology choice and rationale
- [ ] Explicitly documents the substitution of React Native for Flutter, WatermelonDB for Drift ORM, and react-native-chart-kit for fl_chart

## Sub-tasks
- [ ] Write `/docs/adr/0001-tech-stack.md`
- [ ] Link ADR from README
```

---

## M3 — Backend & Mobile Foundation (Aug 27 – Sep 9, 2026)

### Issue 12 — Initialize FastAPI project structure
**Assignee:** Thai
**Labels:** `backend`, `setup`

```markdown
## Description
Scaffold the FastAPI backend with a clean, scalable project layout (routers, services, schemas, models, config, dependency injection) ready for feature development.

## Acceptance Criteria
- [ ] FastAPI app runs locally with `uvicorn`
- [ ] Project structure separates routers / services / models / schemas / core config
- [ ] `.env`-based configuration for DB connection, secrets
- [ ] Health-check endpoint (`GET /health`) returns 200

## Sub-tasks
- [ ] Scaffold folder structure
- [ ] Add FastAPI app entrypoint
- [ ] Add environment/config loading (pydantic-settings)
- [ ] Add `/health` endpoint
- [ ] Document local run instructions in README
```

### Issue 13 — Set up PostgreSQL + Alembic migration pipeline
**Assignee:** Thai
**Labels:** `backend`, `database`, `setup`

```markdown
## Description
Wire the FastAPI app to the local PostgreSQL database (already installed) and make sure Alembic migrations from Issue #7 run cleanly against it as part of a repeatable setup process.

## Acceptance Criteria
- [ ] App connects to local PostgreSQL via SQLAlchemy session
- [ ] `alembic upgrade head` provisions a working schema from scratch
- [ ] Seed script (optional but recommended) creates sample data for local dev

## Sub-tasks
- [ ] Configure SQLAlchemy engine/session against local PostgreSQL
- [ ] Verify migrations run cleanly on a fresh database
- [ ] Write a basic seed script for local development
- [ ] Document DB setup steps in README
```

### Issue 14 — Implement authentication & farm/household account model (JWT)
**Assignee:** Thai
**Labels:** `backend`, `auth`, `api`

```markdown
## Description
Implement account registration/login for farming households, issuing JWTs that both the API and the Sync API will use to scope data per household.

## Acceptance Criteria
- [ ] `POST /auth/register` and `POST /auth/login` implemented
- [ ] JWT issued on login, validated on protected routes
- [ ] All season/diary/supply/finance data is scoped to the authenticated household
- [ ] Passwords stored hashed (e.g. bcrypt/argon2)

## Sub-tasks
- [ ] Implement User/Household model
- [ ] Implement password hashing
- [ ] Implement register/login endpoints
- [ ] Implement JWT issuance & validation dependency
- [ ] Write basic auth tests
```

### Issue 15 — Initialize React Native project (navigation, structure, linting)
**Assignee:** Khoa
**Labels:** `mobile`, `setup`

```markdown
## Description
Scaffold the React Native app with a clean folder structure, navigation library, and linting/formatting rules consistent with the team's tooling.

## Acceptance Criteria
- [ ] RN app builds and runs on Android Studio emulator
- [ ] Folder structure separates screens / components / navigation / db / services
- [ ] React Navigation installed and configured
- [ ] ESLint + Prettier configured and passing

## Sub-tasks
- [ ] Scaffold RN project (React Native CLI)
- [ ] Install & configure React Navigation
- [ ] Set up folder structure
- [ ] Configure ESLint/Prettier
- [ ] Document local run instructions in README
```

### Issue 16 — Integrate WatermelonDB into RN app
**Assignee:** Khoa
**Labels:** `mobile`, `database`, `offline`

```markdown
## Description
Wire the WatermelonDB schema and models designed in Issue #8 into the React Native app, with local SQLite storage working end-to-end.

## Acceptance Criteria
- [ ] WatermelonDB adapter configured for the app
- [ ] All models from Issue #8 registered and functional
- [ ] Basic local CRUD (create a season, read it back) verified on device/emulator

## Sub-tasks
- [ ] Install & configure `@nozbe/watermelondb`
- [ ] Register schema and models
- [ ] Write a smoke-test screen/script for local CRUD
- [ ] Document WatermelonDB setup in README
```

### Issue 17 — Build core app navigation shell (tabs: Diary / Supplies / Finance / Reports)
**Assignee:** Khoa
**Labels:** `mobile`, `ux`

```markdown
## Description
Build the top-level navigation shell (bottom tab bar or drawer) connecting the four core modules, plus login/onboarding flow, based on the wireframes from Issue #10.

## Acceptance Criteria
- [ ] Bottom tab navigation with Diary, Supplies, Finance, Reports
- [ ] Login/onboarding screen routes into the tab navigator on success
- [ ] Placeholder screens render for each tab

## Sub-tasks
- [ ] Implement tab navigator
- [ ] Implement login/onboarding screen shell
- [ ] Wire auth state to navigation (logged-in vs logged-out stack)
```

### Issue 18 — Set up CI pipelines for backend & mobile (lint + test)
**Assignee:** Both
**Labels:** `chore`, `ci-cd`

```markdown
## Description
Add GitHub Actions workflows that run linting and automated tests on every push/PR for both the backend and mobile codebases, so regressions are caught early.

## Acceptance Criteria
- [ ] Backend workflow runs `pytest` + linter on push/PR
- [ ] Mobile workflow runs ESLint + any unit tests on push/PR
- [ ] Both workflows show status checks on PRs

## Sub-tasks
- [ ] Add `.github/workflows/backend-ci.yml`
- [ ] Add `.github/workflows/mobile-ci.yml`
- [ ] Require CI to pass before merge (branch protection)
```

---

## M4 — Farming Diary & Cost Module (Sep 10 – Sep 23, 2026)

### Issue 19 — Build Season Management API (CRUD)
**Assignee:** Thai
**Labels:** `backend`, `api`

```markdown
## Description
Implement CRUD endpoints for crop seasons (e.g. "Vụ Đông Xuân 2026"), scoped per household.

## Acceptance Criteria
- [ ] `POST/GET/PUT/DELETE /seasons` implemented and scoped to the authenticated household
- [ ] Validation on required fields (crop type, start date, end date)
- [ ] Endpoints covered by tests

## Sub-tasks
- [ ] Implement Season schema (Pydantic) and endpoints
- [ ] Add validation rules
- [ ] Write API tests
- [ ] Update API docs (auto-generated Swagger is fine, verify it's accurate)
```

### Issue 20 — Build Season Management UI
**Assignee:** Khoa
**Labels:** `mobile`, `frontend`

```markdown
## Description
Build the screens for creating, listing, and editing crop seasons, working fully against local WatermelonDB data.

## Acceptance Criteria
- [ ] Season list screen shows all seasons for the household
- [ ] Create/edit season form with validation
- [ ] All operations persist to WatermelonDB immediately (no network dependency)

## Sub-tasks
- [ ] Build season list screen
- [ ] Build create/edit season form
- [ ] Wire screens to WatermelonDB models
```

### Issue 21 — Build Farming Diary Log API (CRUD)
**Assignee:** Thai
**Labels:** `backend`, `api`

```markdown
## Description
Implement CRUD endpoints for diary/work-log entries (fertilizing, spraying, harvesting, etc.), linked to a season.

## Acceptance Criteria
- [ ] `POST/GET/PUT/DELETE /seasons/{season_id}/diary-entries` implemented
- [ ] Entry supports work type, date, notes, and optional linked supply usage
- [ ] Endpoints covered by tests

## Sub-tasks
- [ ] Implement DiaryEntry schema and endpoints
- [ ] Support linking a diary entry to supply consumption
- [ ] Write API tests
```

### Issue 22 — Build Farming Diary Log UI (offline-first)
**Assignee:** Khoa
**Labels:** `mobile`, `frontend`, `offline`

```markdown
## Description
Build the diary logging screens (list + entry form) that read/write exclusively to local WatermelonDB, so the feature works with zero network connectivity.

## Acceptance Criteria
- [ ] Diary entries can be created, edited, deleted fully offline
- [ ] Diary list filterable by season and work type
- [ ] Form supports selecting work type (fertilizing/spraying/harvesting/other) and optional supply usage

## Sub-tasks
- [ ] Build diary entry list screen (per season)
- [ ] Build create/edit diary entry form
- [ ] Add work-type filter
- [ ] Verify full offline operation (airplane mode test)
```

### Issue 23 — Build Supply/Inventory Management API (stock in/out)
**Assignee:** Thai
**Labels:** `backend`, `api`, `database`

```markdown
## Description
Implement endpoints for managing agricultural supplies and their stock movements (stock-in/purchase, stock-out/consumption), with real-time inventory levels.

## Acceptance Criteria
- [ ] CRUD for supply items (name, unit, category)
- [ ] Endpoints to record stock-in and stock-out transactions
- [ ] Current inventory level computable/queryable per supply item
- [ ] Endpoints covered by tests

## Sub-tasks
- [ ] Implement Supply and StockTransaction models/endpoints
- [ ] Implement inventory-level calculation (sum of in minus out)
- [ ] Write API tests
```

### Issue 24 — Build Supply/Inventory Management UI
**Assignee:** Khoa
**Labels:** `mobile`, `frontend`

```markdown
## Description
Build screens for managing supply items and recording stock-in/stock-out, with a live inventory list, working fully offline.

## Acceptance Criteria
- [ ] Inventory list shows current stock level per supply item
- [ ] Stock-in and stock-out forms update inventory immediately (local-first)
- [ ] Low-stock items are visually flagged

## Sub-tasks
- [ ] Build inventory list screen
- [ ] Build stock-in form
- [ ] Build stock-out form
- [ ] Add low-stock visual indicator
```

### Issue 25 — Implement server-side auto stock-restore on edit/delete diary entry
**Assignee:** Thai
**Labels:** `backend`, `enhancement`

```markdown
## Description
When a diary entry that consumed supplies is edited or deleted, automatically reverse/adjust the associated stock transaction(s) ("hoàn kho") so inventory levels stay accurate.

## Acceptance Criteria
- [ ] Editing a diary entry's supply usage correctly adjusts inventory (reverses old amount, applies new amount)
- [ ] Deleting a diary entry restores the consumed stock back to inventory
- [ ] Covered by unit tests for edit, delete, and edge cases (partial quantity changes)

## Sub-tasks
- [ ] Implement stock-restore logic on diary entry update
- [ ] Implement stock-restore logic on diary entry delete
- [ ] Write tests for restore logic, including edge cases
```

### Issue 26 — Implement client-side auto stock-restore in WatermelonDB
**Assignee:** Khoa
**Labels:** `mobile`, `offline`, `enhancement`

```markdown
## Description
Mirror the server-side stock-restore logic (Issue #25) on-device, so inventory stays correct even when a diary entry is edited/deleted entirely offline.

## Acceptance Criteria
- [ ] Editing a diary entry's supply usage locally adjusts local inventory correctly
- [ ] Deleting a diary entry locally restores consumed stock
- [ ] Behavior verified in airplane mode, and remains correct after a later sync

## Sub-tasks
- [ ] Implement local stock-restore on diary entry update
- [ ] Implement local stock-restore on diary entry delete
- [ ] Manually test offline edit/delete scenarios
```

### Issue 27 — Build Income/Expense API (cost, revenue, profit per season)
**Assignee:** Thai
**Labels:** `backend`, `api`

```markdown
## Description
Implement endpoints to record expenses and revenue entries, and compute total cost, revenue, and profit per season.

## Acceptance Criteria
- [ ] CRUD endpoints for expense and revenue records
- [ ] `GET /seasons/{season_id}/summary` returns total cost, total revenue, and profit
- [ ] Endpoints covered by tests

## Sub-tasks
- [ ] Implement Expense and Revenue models/endpoints
- [ ] Implement season financial summary calculation
- [ ] Write API tests
```

### Issue 28 — Build Income/Expense UI
**Assignee:** Khoa
**Labels:** `mobile`, `frontend`

```markdown
## Description
Build screens for recording expenses and revenue, and a per-season summary view showing cost, revenue, and profit — working fully offline.

## Acceptance Criteria
- [ ] Expense entry form and list
- [ ] Revenue entry form and list
- [ ] Season summary screen shows cost/revenue/profit computed locally

## Sub-tasks
- [ ] Build expense entry form/list
- [ ] Build revenue entry form/list
- [ ] Build season financial summary screen
```

### Issue 29 — Link diary entries to auto-generated expense records
**Assignee:** Both
**Labels:** `backend`, `mobile`, `enhancement`

```markdown
## Description
When a diary entry consumes supplies, automatically generate a corresponding expense record (based on supply cost), on both backend and mobile, so farmers don't have to double-enter costs.

## Acceptance Criteria
- [ ] Recording supply usage in a diary entry automatically creates/updates a linked expense record
- [ ] Editing/deleting the diary entry correctly updates/removes the linked expense
- [ ] Behavior consistent between backend-computed and locally-computed values after sync

## Sub-tasks
- [ ] Backend: auto-generate expense on supply-linked diary entry (Thai)
- [ ] Mobile: auto-generate expense locally (Khoa)
- [ ] Joint test: create/edit/delete flow end-to-end, then verify after sync
```

---

## M5 — Progress Report 1 (Sep 24 – Sep 28, 2026)

### Issue 30 — Prepare & submit Progress Report 1
**Assignee:** Both
**Labels:** `documentation`, `milestone`

```markdown
## Description
Prepare and deliver the first progress report/demo to the advisor (TS. Nguyễn Thị Lương), covering season management, diary logging, supply/inventory, and income/expense modules built so far.

## Acceptance Criteria
- [ ] Demo script covering all modules built through Milestone 4
- [ ] Progress report document written (status, blockers, next steps)
- [ ] Report submitted / demo delivered by Sep 28, 2026

## Sub-tasks
- [ ] Prepare demo build (backend + mobile)
- [ ] Write progress report document
- [ ] Rehearse demo
- [ ] Submit / present to advisor
```

---

## M6 — Sync Engine (Sep 29 – Oct 12, 2026)

### Issue 31 — Implement Sync Push API
**Assignee:** Thai
**Labels:** `backend`, `sync`, `api`

```markdown
## Description
Implement the push side of the Sync API (per the contract from Issue #9): accept batched local changes from the mobile client and apply them to PostgreSQL.

## Acceptance Criteria
- [ ] Endpoint accepts a batch of created/updated/deleted records across all synced tables
- [ ] Changes applied transactionally; partial failures reported per-record
- [ ] Endpoint covered by tests, including duplicate/idempotent submission

## Sub-tasks
- [ ] Implement push endpoint per contract
- [ ] Implement transactional batch apply
- [ ] Handle idempotency (safe to retry)
- [ ] Write tests
```

### Issue 32 — Implement Sync Pull API
**Assignee:** Thai
**Labels:** `backend`, `sync`, `api`

```markdown
## Description
Implement the pull side of the Sync API: return changes since a given timestamp/cursor so the client can update its local WatermelonDB.

## Acceptance Criteria
- [ ] Endpoint returns created/updated/deleted records since last sync cursor
- [ ] Response format matches what WatermelonDB's `synchronize()` expects
- [ ] Endpoint covered by tests, including empty-diff and large-diff cases

## Sub-tasks
- [ ] Implement pull endpoint per contract
- [ ] Implement change-tracking query (updated_at / version-based)
- [ ] Write tests
```

### Issue 33 — Implement server-side conflict resolution & deduplication
**Assignee:** Thai
**Labels:** `backend`, `sync`, `enhancement`

```markdown
## Description
Implement the conflict-resolution and deduplication strategy decided in Issue #9, so simultaneous edits from multiple devices don't corrupt data or create duplicates.

## Acceptance Criteria
- [ ] Conflicting updates resolved per the documented strategy (e.g. last-write-wins by timestamp)
- [ ] Duplicate record submission (same client UUID) does not create duplicate rows
- [ ] Covered by tests simulating concurrent edits from two "devices"

## Sub-tasks
- [ ] Implement conflict-resolution logic in push handler
- [ ] Implement dedup-by-client-UUID logic
- [ ] Write concurrency/conflict tests
```

### Issue 34 — Implement WatermelonDB sync adapter
**Assignee:** Khoa
**Labels:** `mobile`, `sync`, `offline`

```markdown
## Description
Wire WatermelonDB's `synchronize()` to the backend push/pull endpoints, so local changes upload and remote changes download correctly.

## Acceptance Criteria
- [ ] `synchronize()` configured with `pushChanges`/`pullChanges` calling the backend Sync API
- [ ] Successful round-trip verified: create offline → go online → data appears on backend, and vice versa
- [ ] Errors during sync are caught and surfaced (not silently swallowed)

## Sub-tasks
- [ ] Implement `pullChanges` against `GET /sync/pull`
- [ ] Implement `pushChanges` against `POST /sync/push`
- [ ] Add error handling/retry hooks
- [ ] Manual round-trip test
```

### Issue 35 — Build sync status UI
**Assignee:** Khoa
**Labels:** `mobile`, `frontend`, `ux`

```markdown
## Description
Give farmers visibility into sync state: whether there are unsynced local changes, when the last successful sync happened, and a manual "sync now" action.

## Acceptance Criteria
- [ ] UI indicator shows pending (unsynced) change count
- [ ] UI shows "last synced at [time]"
- [ ] Manual sync button triggers `synchronize()` and shows success/failure feedback

## Sub-tasks
- [ ] Build sync status indicator component
- [ ] Track and display last-synced timestamp
- [ ] Build manual sync trigger with loading/success/error states
```

### Issue 36 — Implement sync retry/queue mechanism for unstable network
**Assignee:** Both
**Labels:** `backend`, `mobile`, `sync`, `enhancement`

```markdown
## Description
Farmland areas often have unstable connectivity. Ensure sync attempts that fail mid-way (dropped connection) retry safely without data loss or duplication, on both client and server.

## Acceptance Criteria
- [ ] Mobile: interrupted sync attempts are retried automatically (e.g. exponential backoff) without duplicating data
- [ ] Backend: partial/interrupted push batches don't leave the database in an inconsistent state
- [ ] Verified with a simulated flaky-network test (e.g. throttled/dropped connection mid-sync)

## Sub-tasks
- [ ] Mobile: implement retry/backoff around `synchronize()` (Khoa)
- [ ] Backend: ensure push handler is safely re-runnable (Thai)
- [ ] Joint test: simulate network drop mid-sync and verify data integrity
```

---

## M7 — Offline & Sync Testing (Oct 13 – Oct 22, 2026)

### Issue 37 — Write offline/sync test plan
**Assignee:** Both
**Labels:** `testing`, `qa`

```markdown
## Description
Write a structured test plan covering offline usage, network transitions, and multi-device sync/conflict scenarios before executing the QA pass.

## Acceptance Criteria
- [ ] Test plan covers: full offline usage per module, online→offline→online transitions, multi-device conflicting edits, large-batch sync
- [ ] Each scenario has clear expected behavior and pass/fail criteria

## Sub-tasks
- [ ] List offline scenarios per module
- [ ] List sync/conflict scenarios
- [ ] Document expected outcomes for each
```

### Issue 38 — Test offline CRUD across all modules
**Assignee:** Khoa
**Labels:** `mobile`, `testing`, `offline`

```markdown
## Description
Execute the offline portion of the test plan (Issue #37): verify seasons, diary entries, supplies, and finance records can be fully created/read/updated/deleted with the device in airplane mode.

## Acceptance Criteria
- [ ] All CRUD operations for all 4 modules verified working with no network connection
- [ ] Any bugs found are logged as separate issues (linked to Issue #41)

## Sub-tasks
- [ ] Test season CRUD offline
- [ ] Test diary entry CRUD offline
- [ ] Test supply/inventory CRUD offline
- [ ] Test income/expense CRUD offline
- [ ] Log bugs found
```

### Issue 39 — Load/stress test Sync API
**Assignee:** Thai
**Labels:** `backend`, `testing`, `sync`

```markdown
## Description
Verify the Sync API handles realistic and worst-case batch sizes (e.g. a device that's been offline for weeks accumulating many changes) without timing out or corrupting data.

## Acceptance Criteria
- [ ] Sync API tested with large batch payloads (e.g. 500+ queued changes)
- [ ] Response times measured and documented
- [ ] No data corruption or partial-apply issues under load

## Sub-tasks
- [ ] Write a script to generate large synthetic change batches
- [ ] Run push/pull load tests
- [ ] Document results and fix any bottlenecks found
```

### Issue 40 — Test multi-device sync & conflict resolution
**Assignee:** Both
**Labels:** `testing`, `sync`, `qa`

```markdown
## Description
Verify the conflict-resolution strategy (Issue #33) behaves correctly when the same record is edited on two devices while both are offline, then both come back online.

## Acceptance Criteria
- [ ] Two-device conflicting edit scenario tested and resolves per documented strategy
- [ ] No data loss or silent overwrite that surprises the user
- [ ] Any gaps found are logged as bugs

## Sub-tasks
- [ ] Set up two test devices/emulators
- [ ] Execute conflicting-edit scenarios from the test plan
- [ ] Document actual vs expected behavior
- [ ] Log bugs found
```

### Issue 41 — Fix bugs found during offline/sync QA
**Assignee:** Both
**Labels:** `bug`, `testing`

```markdown
## Description
Tracking issue for triaging and fixing the bugs surfaced by Issues #38–#40 before moving on to the reporting module.

## Acceptance Criteria
- [ ] All critical/high-severity bugs from the QA pass are fixed and verified
- [ ] Regression check performed after fixes

## Sub-tasks
- [ ] Triage bugs by severity
- [ ] Fix backend-side bugs (Thai)
- [ ] Fix mobile-side bugs (Khoa)
- [ ] Re-run affected test scenarios
```

---

## M8 — Reports & Visualization Module (Oct 23 – Nov 1, 2026)

### Issue 42 — Build reporting/aggregation API
**Assignee:** Thai
**Labels:** `backend`, `api`, `reports`

```markdown
## Description
Implement backend endpoints that aggregate data for the 3 required reports: income vs. expense over time, supply consumption by type, and profit comparison across seasons.

## Acceptance Criteria
- [ ] `GET /reports/income-expense` returns time-series cost/revenue/profit data
- [ ] `GET /reports/supply-consumption` returns supply usage aggregated by type/season
- [ ] `GET /reports/season-comparison` returns profit per season
- [ ] Endpoints covered by tests

## Sub-tasks
- [ ] Implement income/expense aggregation query + endpoint
- [ ] Implement supply consumption aggregation query + endpoint
- [ ] Implement season comparison aggregation query + endpoint
- [ ] Write tests
```

### Issue 43 — Integrate RN chart library (react-native-chart-kit)
**Assignee:** Khoa
**Labels:** `mobile`, `frontend`, `reports`

```markdown
## Description
Install and configure `react-native-chart-kit` (the React Native equivalent of fl_chart from the original proposal) and verify it renders correctly on Android.

## Acceptance Criteria
- [ ] Library installed and a sample chart renders correctly on the Android emulator
- [ ] Confirmed the library supports the chart types needed: line/bar (income vs expense), pie/bar (supply consumption), bar (season comparison)

## Sub-tasks
- [ ] Install `react-native-chart-kit` (and `react-native-svg` dependency)
- [ ] Render a proof-of-concept chart with sample data
- [ ] Confirm all 3 required chart types are supported
```

### Issue 44 — Build Income vs Expense chart screen
**Assignee:** Khoa
**Labels:** `mobile`, `frontend`, `reports`

```markdown
## Description
Build the report screen visualizing income, expense, and profit trends over time for a selected season, backed by local (offline-capable) data.

## Acceptance Criteria
- [ ] Chart displays revenue, cost, and profit trend for a selected season
- [ ] Season selector available
- [ ] Renders correctly with both small and larger datasets

## Sub-tasks
- [ ] Build data-fetching hook (local WatermelonDB query, with API fallback/refresh)
- [ ] Build chart component
- [ ] Build season selector
```

### Issue 45 — Build Supply Consumption chart screen
**Assignee:** Khoa
**Labels:** `mobile`, `frontend`, `reports`

```markdown
## Description
Build the report screen visualizing supply consumption by type/season, to help farmers spot which inputs cost them the most.

## Acceptance Criteria
- [ ] Chart displays supply usage broken down by supply type
- [ ] Filterable by season
- [ ] Renders correctly with both small and larger datasets

## Sub-tasks
- [ ] Build data-fetching logic for supply consumption
- [ ] Build chart component
- [ ] Build season filter
```

### Issue 46 — Build Season Comparison (profit) chart screen
**Assignee:** Khoa
**Labels:** `mobile`, `frontend`, `reports`

```markdown
## Description
Build the report screen comparing profit/cost across multiple seasons, so farmers can see which seasons performed best.

## Acceptance Criteria
- [ ] Chart compares profit (and optionally cost/revenue) across all of the household's seasons
- [ ] Renders correctly with 1 season and with many seasons

## Sub-tasks
- [ ] Build data-fetching logic for cross-season comparison
- [ ] Build chart component
```

### Issue 47 — Verify charts render correctly from offline/local data
**Assignee:** Both
**Labels:** `mobile`, `offline`, `reports`

```markdown
## Description
Confirm all 3 report screens (Issues #44-46) compute and render correctly purely from local WatermelonDB data when offline, and refresh correctly after a sync.

## Acceptance Criteria
- [ ] All 3 charts render correct data in airplane mode
- [ ] Charts update correctly after new data syncs in from another device

## Sub-tasks
- [ ] Test all 3 charts offline
- [ ] Test chart refresh after sync
- [ ] Fix any discrepancies found
```

---

## M9 — Progress Report 2 (Nov 2 – Nov 5, 2026)

### Issue 48 — Prepare & submit Progress Report 2
**Assignee:** Both
**Labels:** `documentation`, `milestone`

```markdown
## Description
Prepare and deliver the second progress report/demo to the advisor, covering the sync engine and the reporting/visualization module.

## Acceptance Criteria
- [ ] Demo script covering sync engine and all 3 report charts
- [ ] Progress report document written (status, blockers, next steps)
- [ ] Report submitted / demo delivered by Nov 5, 2026

## Sub-tasks
- [ ] Prepare demo build (backend + mobile)
- [ ] Write progress report document
- [ ] Rehearse demo
- [ ] Submit / present to advisor
```

---

## M10 — Optimization & Final Documentation (Nov 6 – Nov 12, 2026)

### Issue 49 — Optimize backend API performance
**Assignee:** Thai
**Labels:** `backend`, `performance`

```markdown
## Description
Profile and optimize the FastAPI backend: query performance (especially the reporting/aggregation and sync endpoints), pagination, and indexing.

## Acceptance Criteria
- [ ] Slow endpoints identified via profiling
- [ ] Appropriate indexes added to PostgreSQL
- [ ] Pagination added to list endpoints returning large datasets
- [ ] Before/after performance numbers documented

## Sub-tasks
- [ ] Profile key endpoints (sync pull/push, reports)
- [ ] Add/verify database indexes
- [ ] Add pagination where missing
- [ ] Document performance improvements
```

### Issue 50 — Optimize RN app performance
**Assignee:** Khoa
**Labels:** `mobile`, `performance`

```markdown
## Description
Profile and optimize the React Native app: list rendering (virtualization for long diary/inventory lists), startup time, and bundle size.

## Acceptance Criteria
- [ ] Long lists (diary entries, stock transactions) use virtualization (e.g. `FlatList` tuning)
- [ ] App startup time measured and improved where possible
- [ ] Bundle size reviewed for obviously removable bloat

## Sub-tasks
- [ ] Profile list rendering performance
- [ ] Apply virtualization/optimization to long lists
- [ ] Measure and document startup time
- [ ] Review bundle size
```

### Issue 51 — Full regression testing across all modules
**Assignee:** Both
**Labels:** `testing`, `qa`

```markdown
## Description
Run a complete regression pass across every module (auth, seasons, diary, supplies, finance, sync, reports) before finalizing documentation, to catch anything broken by the optimization work.

## Acceptance Criteria
- [ ] Every module manually verified against its acceptance criteria from earlier issues
- [ ] All critical bugs found are fixed
- [ ] Regression checklist stored in `/docs/qa-checklist.md`

## Sub-tasks
- [ ] Build regression checklist from all prior acceptance criteria
- [ ] Execute checklist against latest build
- [ ] Fix any regressions found
```

### Issue 52 — Write final thesis report (Đồ án)
**Assignee:** Both
**Labels:** `documentation`

```markdown
## Description
Write the final thesis/graduation project report documenting the problem, architecture, implementation, and results, per the university's submission requirements.

## Acceptance Criteria
- [ ] Report covers overview, objectives, architecture, implementation details, testing, results, and references
- [ ] Reviewed by both authors before submission

## Sub-tasks
- [ ] Draft report outline
- [ ] Write architecture & implementation sections (Thai: backend/sync; Khoa: mobile/offline/UI)
- [ ] Write testing & results sections
- [ ] Final review and formatting pass
```

### Issue 53 — Prepare defense presentation slides
**Assignee:** Both
**Labels:** `documentation`

```markdown
## Description
Prepare the slide deck for the final defense in front of the committee, summarizing the problem, solution, architecture, and demo.

## Acceptance Criteria
- [ ] Slides cover: problem statement, objectives, architecture, key features, offline/sync demo, results, lessons learned
- [ ] Rehearsed at least once before the defense date

## Sub-tasks
- [ ] Draft slide outline
- [ ] Build slides
- [ ] Rehearse presentation
```

### Issue 54 — Record product demo video
**Assignee:** Both
**Labels:** `documentation`

```markdown
## Description
Record a demo video showing the app's core flows, including the offline-first experience and sync, for inclusion in the final submission package.

## Acceptance Criteria
- [ ] Video demonstrates: season creation, diary logging offline, supply/inventory tracking, income/expense tracking, sync in action, and all 3 report charts
- [ ] Video is clear, reasonably paced, and exported in a submittable format

## Sub-tasks
- [ ] Write a demo script/storyboard
- [ ] Record screen capture (mobile + backend where relevant)
- [ ] Edit and export final video
```

---

## M11 — Final Defense (Nov 13 – Nov 15, 2026)

### Issue 55 — Final defense presentation to committee
**Assignee:** Both
**Labels:** `milestone`

```markdown
## Description
Present the completed project to the graduation committee.

## Acceptance Criteria
- [ ] All submission materials (report, slides, demo video, source code) finalized and submitted ahead of the defense
- [ ] Presentation delivered within the defense window (Nov 13–15, 2026)

## Sub-tasks
- [ ] Confirm all submission materials are finalized
- [ ] Deliver presentation
- [ ] Answer committee questions
```

---

## Task 2 — GitHub Projects Kanban Guide

A short, step-by-step guide to turn the issues above into a visual Kanban board on your repo, https://github.com/ThaiTaka/agrilogapp.

1. **Create the labels first (if not already).** Go to `Issues` → `Labels` → `New label`, and add: `backend`, `mobile`, `database`, `api`, `sync`, `offline`, `auth`, `testing`, `qa`, `bug`, `enhancement`, `documentation`, `design`, `ux`, `planning`, `research`, `architecture`, `performance`, `reports`, `chore`, `ci-cd`, `project-setup`, `milestone`.

2. **Create milestones.** Go to `Issues` → `Milestones` → `New milestone`, and create M1 through M11 using the names and date ranges from the table near the top of this doc (e.g. "M4 — Farming Diary & Cost Module", due Sep 23, 2026). This lets you filter/track progress by phase later.

3. **Create the issues.** For each issue above: go to `Issues` → `New issue`, paste the Title, paste the fenced body content into the description box, set the Assignee (Thai/Khoa/both), add the Labels, and attach the matching Milestone from step 2. Repeat for all 55 issues (this is tedious but one-time — you can also do it faster via the GitHub CLI, see the tip at the bottom).

4. **Create the Project board.** Go to your repo's `Projects` tab → `New project` → choose the **Board** layout (this is the "Projects (v2)" experience with drag-and-drop cards). Name it something like "AgriLog Roadmap".

5. **Set up the three columns.** A new board ships with `Todo`, `In Progress`, and `Done` columns by default — if not, click `+ Add column` and create exactly those three (matching your requested workflow).

6. **Add the issues to the board.** Inside the project, click `+ Add item` → `Add item from repository`, then search and select all 55 issues (you can multi-select). They'll land in the `Todo` column by default.

7. **(Optional but recommended) Group by Milestone.** Click the view options (`⚙️` or the `Group by` control) and group cards by "Milestone" — this gives you a quick way to see each of the 11 phases as its own swimlane, on top of the To-do/In Progress/Done columns.

8. **Establish the daily workflow.** As Thai or Khoa start work on an issue, drag its card to `In Progress` (or set the auto-workflow: `Project settings` → `Workflows` → enable "Item added to project" → auto-set status, and "Issue closed" → auto-move to `Done`). When a PR closes an issue (e.g. commit message `Closes #21`), GitHub will auto-close it and, with the workflow enabled, the card auto-moves to `Done`.

9. **Review weekly against the timeline.** Since columns are grouped by milestone, at the end of each week you can sanity-check the board against the dates in the Milestones Overview table to see if you're on pace for Progress Report 1, Progress Report 2, and the final defense.

**Speed tip:** if entering 55 issues by hand through the UI is too slow, install the GitHub CLI (`gh`) and use `gh issue create --title "..." --body-file issue-N.md --label backend,api --assignee ThaiUsername --milestone "M1"` in a loop — you can save each issue's body to its own `.md` file first (this document is already broken into copy-pasteable chunks for that).
