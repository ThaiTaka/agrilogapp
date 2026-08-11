# Error Report — PostgreSQL server not running (Windows service not registered)

**Date:** 11 Aug 2026
**Affects:** Issue #13 (PostgreSQL + Alembic pipeline), and every `@pytest.mark.db` test
**Severity:** Blocking for database work; non-blocking for the rest of the backend
**Status:** Server started manually and now reachable. **Service registration still pending** (needs an elevated shell) — see §3.2.

---

## 1. Error Description

Two distinct symptoms, one root cause plus one follow-on.

### Symptom A — nothing listening on 5432

```
Get-NetTCPConnection -LocalPort 5432 -State Listen
   (no output)
```

Any attempt to connect produced:

```
psycopg.OperationalError: connection failed: Connection refused
    Is the server running on that host and accepting TCP/IP connections?
```

The pytest suite reported this as **14 skipped** tests rather than failures, because `tests/conftest.py` probes the database at collection time and converts unreachability into a skip:

```
48 passed, 14 skipped in 2.46s
```

### Symptom B — the Windows service does not exist

```
sc.exe qc "postgresql-x64-18"
[SC] OpenService FAILED 1060:
The specified service does not exist as an installed service.
```

Only a *related* service is registered, and it is stopped:

```
Name          Status   DisplayName
----          ------   -----------
pgagent-pg18  Stopped  PostgreSQL Scheduling Agent - pgagent-pg18
```

---

## 2. Root Cause

**The PostgreSQL 18 *server* Windows service was never registered (or was later removed), so nothing starts the database at boot.**

The evidence rules out the more alarming explanations:

| Check | Result | Rules out |
|---|---|---|
| `C:\Program Files\PostgreSQL\18\data\PG_VERSION` | exists | Uninitialised cluster |
| `data\postmaster.opts` | exists, valid | Cluster never ran |
| `data\log\postgresql-2026-08-11_102422.log` | server ran 10:24 → 10:51 today | Corrupt installation |
| Last log lines | `LOG: shutting down` / `checkpoint complete: shutdown immediate` | Crash / unclean shutdown |
| `data\postmaster.pid` | absent | Stale lock file blocking startup |
| `(Get-Acl data).Owner` | `BUILTIN\Administrators`, writable by `Maxsys` | Permission problem |

The decisive line in the log is:

```
2026-08-11 10:51:27 +07 FATAL:  terminating connection due to administrator command
2026-08-11 10:51:27 +07 LOG:  shutting down
```

That is a **deliberate, clean administrative stop**, not a failure. The cluster is healthy in every respect; the only thing missing is the service entry that would bring it back up. The most likely history is that the PostGIS/pgAgent bundle installer (this installation carries PostGIS, pgRouting, MobilityDB and pgPointCloud — see `installation_summary.log`) registered pgAgent but the server service was removed or never created.

`pgagent-pg18` being present and stopped is a **red herring**. pgAgent is a job scheduler that *connects to* PostgreSQL; it is not the database. Starting it would not help, and it is why `Get-Service *postgres*` returns a row that makes the situation look better than it is.

### Follow-on: authentication

`data\pg_hba.conf` requires a password for every connection path:

```
local   all   all                     scram-sha-256
host    all   all   127.0.0.1/32      scram-sha-256
host    all   all   ::1/128           scram-sha-256
```

There is no `%APPDATA%\postgresql\pgpass.conf` and no `PG*` environment variable, so the `postgres` password is not recoverable from the machine — it must be supplied by the developer. This is **correct and desirable** (a trust-auth database on a laptop is a liability), so the fix supplies the password rather than weakening `pg_hba.conf`.

---

## 3. Exact Step-by-Step Fix

### 3.1 Start the server now — ✅ ALREADY DONE

```powershell
& "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" start -D "C:\Program Files\PostgreSQL\18\data" -w -t 30
```

Output:

```
waiting for server to start....LOG:  redirecting log output to logging collector process
HINT:  Future log output will appear in directory "log".
 done
server started
```

Verified:

```powershell
Get-NetTCPConnection -LocalPort 5432 -State Listen
# LocalAddress  LocalPort
# ::            5432
# 0.0.0.0       5432
```

**This does not survive a reboot.** Do §3.2 as well.

### 3.2 Register the service so it starts at boot — needs Administrator

Open PowerShell **as Administrator** (Win → type `powershell` → Ctrl+Shift+Enter), then:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" register `
    -N "postgresql-x64-18" `
    -D "C:\Program Files\PostgreSQL\18\data" `
    -S auto

Set-Service -Name "postgresql-x64-18" -StartupType Automatic
Start-Service -Name "postgresql-x64-18"
Get-Service -Name "postgresql-x64-18"
```

> If `Start-Service` reports *"the service did not respond in a timely fashion"*, the server started manually in §3.1 still holds port 5432. Stop it first:
> ```powershell
> & "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" stop -D "C:\Program Files\PostgreSQL\18\data" -m fast
> ```
> then `Start-Service` again.

> **Why `-S auto` and not the default:** without it the service is created as *Demand start* and the problem recurs silently on the next reboot — which, mid-thesis, looks exactly like "my code broke overnight".

### 3.3 Confirm the `postgres` password

```powershell
$env:PGPASSWORD = "<your postgres password>"
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -c "SELECT version();"
Remove-Item Env:\PGPASSWORD
```

If the password is unknown, reset it — this requires an elevated shell and briefly relaxes authentication, so put it back immediately:

1. Edit `C:\Program Files\PostgreSQL\18\data\pg_hba.conf`; change **only** the `127.0.0.1/32` line's method from `scram-sha-256` to `trust`.
2. `& "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" reload -D "C:\Program Files\PostgreSQL\18\data"`
3. `psql -U postgres -h localhost -c "ALTER USER postgres PASSWORD 'new_password';"`
4. **Change the line back to `scram-sha-256`** and reload again.

Do not skip step 4. A `trust`-authenticated PostgreSQL accepts any connection from localhost as superuser, including from any program you happen to run.

### 3.4 Create the two databases

```powershell
$env:PGPASSWORD = "<your postgres password>"
$psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
& $psql -U postgres -h localhost -c "CREATE DATABASE agrilog;"
& $psql -U postgres -h localhost -c "CREATE DATABASE agrilog_test;"
& $psql -U postgres -h localhost -l
Remove-Item Env:\PGPASSWORD
```

`agrilog_test` is separate on purpose: `tests/conftest.py` runs `DROP SCHEMA public CASCADE` at the start of every session. Pointing that at the development database would destroy your seed data on every `pytest` run.

### 3.5 Point the app at the database

```powershell
cd d:\agrilogapp\backend
Copy-Item .env.example .env
```

Edit `backend\.env` and replace `CHANGE_ME` in both URLs, and generate a real JWT secret:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
```

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/agrilog
TEST_DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/agrilog_test
JWT_SECRET=<paste the generated string>
```

> **If the password contains `@`, `:`, `/`, `#` or `?`** it must be percent-encoded, or the URL parser will misread where the host begins. `p@ss:w0rd` becomes `p%40ss%3Aw0rd`:
> ```powershell
> [uri]::EscapeDataString('p@ss:w0rd')
> ```

`.env` is git-ignored (`.gitignore` line 2). Never commit it.

### 3.6 Run the migration and confirm

```powershell
cd d:\agrilogapp\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m pytest
```

Expected: `alembic current` prints `0001 (head)`, and the previously-skipped tests now run — **62 passed, 0 skipped**.

---

## 4. Verification Checklist

- [x] Server process running and listening on 5432
- [ ] `postgresql-x64-18` service registered with `Automatic` start (needs Administrator — §3.2)
- [ ] Service survives a reboot
- [ ] `agrilog` and `agrilog_test` databases exist
- [ ] `backend\.env` created with real credentials and a generated `JWT_SECRET`
- [ ] `alembic upgrade head` succeeds; `alembic current` reports `0001 (head)`
- [ ] `alembic downgrade base` then `upgrade head` both succeed (Issue #7 acceptance criterion)
- [ ] `pytest` reports 0 skipped

---

## 5. Prevention

**`GET /health/db` exists for exactly this.** It is a readiness probe distinct from `/health`: the app can be perfectly healthy while the database behind it is not, and conflating the two makes an outage look like an application bug.

```powershell
curl http://localhost:8000/health/db
# {"status":"ok","database":"reachable"}
# 503 {"status":"error","database":"unreachable","detail":"..."}
```

**The test suite degrades rather than lying.** `conftest.py` probes once at collection and converts DB tests to skips with the reason attached, so a stopped server produces `14 skipped` with an explanation instead of 14 confusing connection-refused stack traces. Check the skip count, not just the green tick — 14 skips means the sync-critical trigger and generated-column tests did not actually run.

**Add a startup check to the daily routine:**

```powershell
Get-Service postgresql-x64-18 | Select-Object Status
```

---

*Related: `Data_Requirements_Database.md` §6.1 (the `touch_server_updated_at` trigger these tests verify), README §7 (backend setup).*
