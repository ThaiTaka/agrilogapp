"""Shared pytest fixtures.

The test schema is provisioned by running the real Alembic migrations against
TEST_DATABASE_URL, not by `metadata.create_all`. That matters: `create_all`
would skip the `touch_server_updated_at` trigger, and the trigger is what keeps
the sync pull cursor correct. Testing against a schema the migrations did not
build would test a schema that does not exist in production.

Tests needing a database are marked `@pytest.mark.db` and SKIP (not fail) when
PostgreSQL is unreachable, so the pure-logic suite still runs on a machine
where the server is down.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings

BACKEND_DIR = Path(__file__).resolve().parents[1]


# ═══════════════════════════════════════════════════════════════════════════
#  Database availability
# ═══════════════════════════════════════════════════════════════════════════


def _probe(url: str) -> str | None:
    """Return None if reachable, else the reason it is not."""
    try:
        eng = create_engine(url, connect_args={"connect_timeout": 3})
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        eng.dispose()
        return None
    except Exception as exc:  # noqa: BLE001 - any failure means "unavailable"
        return f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"


_DB_UNAVAILABLE_REASON = _probe(settings.TEST_DATABASE_URL)

requires_db = pytest.mark.skipif(
    _DB_UNAVAILABLE_REASON is not None,
    reason=(
        f"PostgreSQL test database unreachable ({_DB_UNAVAILABLE_REASON}). "
        "See Error_PostgreSQL_Service_Missing.md."
    ),
)


def pytest_collection_modifyitems(config, items) -> None:
    """Apply the skip automatically to everything marked `db`."""
    if _DB_UNAVAILABLE_REASON is None:
        return
    skip = pytest.mark.skip(
        reason=f"PostgreSQL test DB unreachable ({_DB_UNAVAILABLE_REASON})"
    )
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


# ═══════════════════════════════════════════════════════════════════════════
#  Schema provisioning
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    """Drop and rebuild the test schema from migrations, once per session."""
    if _DB_UNAVAILABLE_REASON is not None:
        pytest.skip(_DB_UNAVAILABLE_REASON)

    from alembic import command
    from alembic.config import Config

    admin = create_engine(settings.TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        # A clean slate every session. Cheaper and far more reliable than
        # `downgrade base`, which cannot run if a previous session died
        # mid-migration and left a partial schema.
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    admin.dispose()

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    os.environ["ALEMBIC_TARGET"] = "test"
    try:
        command.upgrade(cfg, "head")
    finally:
        os.environ.pop("ALEMBIC_TARGET", None)

    eng = create_engine(settings.TEST_DATABASE_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Generator[Session, None, None]:
    """A session wrapped in a transaction that is always rolled back.

    Every test therefore starts from the same clean schema without paying to
    rebuild it, and tests cannot leak state into one another.
    """
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
#  HTTP client
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """TestClient with no database override — for routes that need none."""
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def api(db: Session) -> Generator[TestClient, None, None]:
    """TestClient whose `get_db` dependency yields the rolled-back test session."""
    from app.db.session import get_db
    from app.main import app

    def _override() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════════════════
#  Authenticated households
# ═══════════════════════════════════════════════════════════════════════════


class Tenant:
    """A registered household plus the headers to act as it."""

    def __init__(self, api: TestClient, data: dict):
        self._api = api
        self.token: str = data["access_token"]
        self.refresh_token: str = data["refresh_token"]
        self.user_id: str = data["user"]["id"]
        self.household_id: str = data["household"]["id"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def get(self, url, **kw):
        return self._api.get(url, headers=self.headers, **kw)

    def post(self, url, **kw):
        return self._api.post(url, headers=self.headers, **kw)

    def patch(self, url, **kw):
        return self._api.patch(url, headers=self.headers, **kw)

    def delete(self, url, **kw):
        return self._api.delete(url, headers=self.headers, **kw)


@pytest.fixture
def make_tenant(api: TestClient):
    """Factory for registered households.

    Two independent tenants is the setup every isolation test needs, so it is
    a factory rather than a single fixture.
    """
    counter = {"n": 0}

    def _make(email: str | None = None, household_name: str | None = None) -> Tenant:
        counter["n"] += 1
        n = counter["n"]
        payload = {
            "email": email or f"ho{n}@agrilog.vn",
            "password": "matkhau123",
            "full_name": f"Chủ hộ {n}",
            "household_name": household_name or f"Hộ số {n}",
        }
        r = api.post("/api/v1/auth/register", json=payload)
        assert r.status_code == 201, r.text
        return Tenant(api, r.json())

    return _make


@pytest.fixture
def tenant(make_tenant) -> Tenant:
    return make_tenant()
