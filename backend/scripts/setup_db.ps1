<#
.SYNOPSIS
    Provisions the AgriLog PostgreSQL role and databases.

.DESCRIPTION
    Creates a dedicated `agrilog` login role and the `agrilog` /
    `agrilog_test` databases it owns, then runs the Alembic migrations.

    The application deliberately does NOT connect as the `postgres`
    superuser. It only ever needs to own its own two databases; running it as
    superuser turns any SQL-injection bug from a single-database problem into
    a full-cluster compromise.

    The role's password is read from backend/.env, so it lives in exactly one
    git-ignored place and is never hardcoded here.

.PARAMETER PostgresPassword
    Password for the `postgres` superuser. Prompted for securely if omitted.
    Used only to create the role and databases; never stored.

.EXAMPLE
    cd d:\agrilogapp\backend
    .\scripts\setup_db.ps1

.NOTES
    Idempotent. Safe to re-run; existing role and databases are left alone.
#>
[CmdletBinding()]
param(
    [securestring]$PostgresPassword,
    [string]$PgBin = "C:\Program Files\PostgreSQL\18\bin",
    [string]$PgHost = "localhost",
    [int]$PgPort = 5432
)

$ErrorActionPreference = "Stop"
$backend = Split-Path $PSScriptRoot -Parent
$envFile = Join-Path $backend ".env"

# ─── Read the app credentials out of .env ──────────────────────────────────
if (-not (Test-Path $envFile)) {
    throw "$envFile not found. Copy .env.example to .env first."
}

$dbUrl = (Get-Content $envFile | Where-Object { $_ -match '^DATABASE_URL=' }) -replace '^DATABASE_URL=', ''
if ($dbUrl -notmatch '://([^:]+):([^@]+)@') {
    throw "Could not parse a user:password pair out of DATABASE_URL in .env"
}
$appUser = $Matches[1]
$appPass = $Matches[2]
Write-Host "App role from .env: $appUser" -ForegroundColor Cyan

# ─── Superuser credentials ─────────────────────────────────────────────────
if (-not $PostgresPassword) {
    $PostgresPassword = Read-Host -AsSecureString "Password for the 'postgres' superuser"
}
$plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($PostgresPassword))

$psql = Join-Path $PgBin "psql.exe"
if (-not (Test-Path $psql)) { throw "psql not found at $psql" }

function Invoke-Psql {
    param([string]$Database = "postgres", [string]$Sql)
    $env:PGPASSWORD = $plain
    $env:PGCLIENTENCODING = "UTF8"
    try {
        $out = & $psql -U postgres -h $PgHost -p $PgPort -d $Database -v ON_ERROR_STOP=1 -t -A -c $Sql 2>&1
        if ($LASTEXITCODE -ne 0) { throw "psql failed: $out" }
        return $out
    } finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    }
}

Write-Host "`nChecking connection..." -ForegroundColor Cyan
$version = Invoke-Psql -Sql "SELECT version();"
Write-Host "  $($version -split ',' | Select-Object -First 1)"

# ─── Role ──────────────────────────────────────────────────────────────────
Write-Host "`nRole '$appUser'..." -ForegroundColor Cyan
$exists = Invoke-Psql -Sql "SELECT 1 FROM pg_roles WHERE rolname = '$appUser';"
if ($exists -eq "1") {
    # Re-sync the password to whatever .env currently says, so rotating the
    # secret is just an edit plus a re-run of this script.
    Invoke-Psql -Sql "ALTER ROLE $appUser WITH LOGIN PASSWORD '$appPass';" | Out-Null
    Write-Host "  = existed; password re-synced from .env"
} else {
    Invoke-Psql -Sql "CREATE ROLE $appUser WITH LOGIN PASSWORD '$appPass';" | Out-Null
    Write-Host "  + created"
}

# ─── Databases ─────────────────────────────────────────────────────────────
foreach ($dbName in @("agrilog", "agrilog_test")) {
    Write-Host "`nDatabase '$dbName'..." -ForegroundColor Cyan
    $found = Invoke-Psql -Sql "SELECT 1 FROM pg_database WHERE datname = '$dbName';"
    if ($found -eq "1") {
        Write-Host "  = already exists"
    } else {
        # OWNER matters: from PostgreSQL 15 the public schema is owned by
        # pg_database_owner, so making the app role the database owner is what
        # lets Alembic create tables without extra GRANTs.
        Invoke-Psql -Sql "CREATE DATABASE $dbName OWNER $appUser ENCODING 'UTF8';" | Out-Null
        Write-Host "  + created, owned by $appUser"
    }
}

# ─── Collation warning ─────────────────────────────────────────────────────
# Not fatal -- name_key exists precisely so correctness does not depend on
# this -- but worth surfacing, because a C-collation cluster sorts Vietnamese
# names by byte value in any ORDER BY that is not explicitly collated.
$collate = Invoke-Psql -Database "agrilog" -Sql `
    "SELECT datcollate FROM pg_database WHERE datname = current_database();"
Write-Host "`nCollation: $collate" -ForegroundColor Cyan
if ($collate -match '^C$|^POSIX$') {
    Write-Host "  ! This cluster uses the C collation." -ForegroundColor Yellow
    Write-Host "    Vietnamese names will sort by byte value, and PostgreSQL's" -ForegroundColor Yellow
    Write-Host "    lower() will not fold accented characters. AgriLog does not" -ForegroundColor Yellow
    Write-Host "    rely on either (see Error_Postgres_Locale_Case_Folding.md)," -ForegroundColor Yellow
    Write-Host "    but any new query that does will misbehave here." -ForegroundColor Yellow
}

# ─── Migrations ────────────────────────────────────────────────────────────
Write-Host "`nRunning migrations..." -ForegroundColor Cyan
Push-Location $backend
try {
    & .\.venv\Scripts\python.exe -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "alembic upgrade failed" }
    & .\.venv\Scripts\python.exe -m alembic current
} finally {
    Pop-Location
}

Write-Host "`nDone." -ForegroundColor Green
Write-Host "  Seed sample data : .\.venv\Scripts\python.exe -m app.seed"
Write-Host "  Run the API      : .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
Write-Host "  Run the tests    : .\.venv\Scripts\python.exe -m pytest"
