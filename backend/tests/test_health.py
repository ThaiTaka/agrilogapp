"""App bootstrap and health endpoints (Issue #12)."""

from __future__ import annotations

import pytest


class TestHealth:
    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["version"]
        assert body["server_time_ms"] > 1_577_836_800_000

    def test_server_time_header_present(self, client):
        """The sync client reads the server clock from this header to detect
        its own drift without having to parse a response body."""
        r = client.get("/health")
        assert "X-Server-Time" in r.headers
        assert int(r.headers["X-Server-Time"]) > 0

    def test_openapi_schema_generates(self, client):
        """A broken response model shows up here before it shows up in Swagger."""
        r = client.get("/openapi.json")
        assert r.status_code == 200
        assert r.json()["info"]["title"] == "AgriLog API"

    def test_docs_available(self, client):
        assert client.get("/docs").status_code == 200

    def test_unknown_route_404(self, client):
        assert client.get("/no-such-route").status_code == 404


class TestReadiness:
    @pytest.mark.db
    def test_db_health_ok_when_reachable(self, api):
        # `api`, not `client`: the probe now runs through the `get_db`
        # dependency, so the test session is what gets exercised.
        r = api.get("/health/db")
        assert r.status_code == 200
        assert r.json()["database"] == "reachable"


class TestConfig:
    def test_bare_postgresql_scheme_rejected(self):
        """Fail fast on the single most common local-setup mistake.

        A bare `postgresql://` URL makes SQLAlchemy reach for psycopg2, which
        is not installed, producing a ModuleNotFoundError far from its cause.
        """
        from pydantic import ValidationError

        from app.core.config import Settings

        with pytest.raises(ValidationError, match="psycopg"):
            Settings(DATABASE_URL="postgresql://postgres:x@localhost:5432/agrilog")

    def test_cors_origins_parsed_from_comma_list(self):
        from app.core.config import Settings

        s = Settings(CORS_ORIGINS="http://a:1, http://b:2 ,")
        assert s.cors_origins_list == ["http://a:1", "http://b:2"]
