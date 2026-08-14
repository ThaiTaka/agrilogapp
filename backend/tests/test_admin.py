"""Web Admin Dashboard API (Phase 2, Bước 0).

The tests that matter most here are the refusals. Every other router in this
codebase is confined to one household by construction, so a scoping mistake
shows up as a 404. /admin is the deliberate exception: a bug in the guard does
not fail loudly, it quietly hands one farmer every other farmer's data.
"""

from __future__ import annotations

import uuid

import pytest

ADMIN = "/api/v1/admin"


def promote(db, user_id: str):
    """Grant admin the only way the system allows — out of band."""
    from app.models import User

    user = db.get(User, uuid.UUID(user_id))
    user.is_admin = True
    db.flush()
    return user


@pytest.fixture
def admin_tenant(db, make_tenant):
    """A registered household whose user has been promoted to admin."""
    t = make_tenant(email="quantri@agrilog.vn", household_name="Hộ quản trị")
    promote(db, t.user_id)
    return t


# ═══════════════════════════════════════════════════════════════════════════
#  The guard
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.db
class TestAdminGuard:
    def test_unauthenticated_is_401(self, api):
        assert api.get(f"{ADMIN}/overview").status_code == 401

    def test_ordinary_user_is_403(self, tenant):
        """Authenticated but not an admin. 403, not 404 — we are refusing a
        known caller, not hiding a route."""
        for path in ("/overview", "/users", "/households", "/maintenance"):
            r = tenant.get(f"{ADMIN}{path}")
            assert r.status_code == 403, f"{path} -> {r.status_code}"
            assert "quyền quản trị" in r.json()["detail"]

    def test_ordinary_user_cannot_patch_users(self, tenant, make_tenant):
        victim = make_tenant()
        r = tenant.patch(f"{ADMIN}/users/{victim.user_id}", json={"is_active": False})
        assert r.status_code == 403

    def test_admin_flag_is_read_from_the_database_not_the_token(
        self, db, admin_tenant, api
    ):
        """The token was issued before promotion and still works; revoking the
        flag stops it immediately, without waiting for expiry."""
        from app.models import User

        assert admin_tenant.get(f"{ADMIN}/overview").status_code == 200

        user = db.get(User, uuid.UUID(admin_tenant.user_id))
        user.is_admin = False
        db.flush()

        assert admin_tenant.get(f"{ADMIN}/overview").status_code == 403

    def test_locked_admin_is_rejected(self, db, admin_tenant):
        from app.models import User

        user = db.get(User, uuid.UUID(admin_tenant.user_id))
        user.is_active = False
        db.flush()

        r = admin_tenant.get(f"{ADMIN}/overview")
        assert r.status_code == 403
        assert "vô hiệu hoá" in r.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════════
#  Users
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.db
class TestAdminUsers:
    def test_lists_across_every_household(self, admin_tenant, make_tenant):
        """The whole point of this endpoint: it is NOT household-scoped."""
        a = make_tenant(email="ho_a@agrilog.vn", household_name="Hộ A")
        b = make_tenant(email="ho_b@agrilog.vn", household_name="Hộ B")

        body = admin_tenant.get(f"{ADMIN}/users").json()
        emails = {item["email"] for item in body["items"]}

        assert {"ho_a@agrilog.vn", "ho_b@agrilog.vn", "quantri@agrilog.vn"} <= emails
        assert body["total"] >= 3
        assert a.household_id != b.household_id

    def test_row_carries_household_name(self, admin_tenant, make_tenant):
        make_tenant(email="tenho@agrilog.vn", household_name="Hộ Nguyễn Văn A")
        items = admin_tenant.get(f"{ADMIN}/users", params={"search": "tenho"}).json()["items"]
        assert len(items) == 1
        assert items[0]["household_name"] == "Hộ Nguyễn Văn A"

    def test_never_exposes_password_hash(self, admin_tenant, make_tenant):
        make_tenant()
        raw = admin_tenant.get(f"{ADMIN}/users").text
        assert "password" not in raw.lower()
        assert "$2b$" not in raw

    def test_search_is_case_insensitive(self, admin_tenant, make_tenant):
        make_tenant(email="Hoa.Mai@agrilog.vn", household_name="Hộ Mai")
        items = admin_tenant.get(f"{ADMIN}/users", params={"search": "HOA.MAI"}).json()["items"]
        assert [i["email"] for i in items] == ["hoa.mai@agrilog.vn"]

    def test_filter_by_active(self, db, admin_tenant, make_tenant):
        from app.models import User

        victim = make_tenant(email="bikhoa@agrilog.vn")
        db.get(User, uuid.UUID(victim.user_id)).is_active = False
        db.flush()

        locked = admin_tenant.get(f"{ADMIN}/users", params={"is_active": False}).json()
        assert [i["email"] for i in locked["items"]] == ["bikhoa@agrilog.vn"]

    def test_pagination_reports_total_before_limit(self, admin_tenant, make_tenant):
        for i in range(3):
            make_tenant(email=f"phantrang{i}@agrilog.vn")

        page = admin_tenant.get(f"{ADMIN}/users", params={"limit": 2}).json()
        assert len(page["items"]) == 2
        assert page["total"] >= 4

    def test_lock_then_unlock(self, admin_tenant, make_tenant):
        victim = make_tenant(email="khoamo@agrilog.vn")

        r = admin_tenant.patch(f"{ADMIN}/users/{victim.user_id}", json={"is_active": False})
        assert r.status_code == 200
        assert r.json()["is_active"] is False

        r = admin_tenant.patch(f"{ADMIN}/users/{victim.user_id}", json={"is_active": True})
        assert r.json()["is_active"] is True

    def test_locking_blocks_login_immediately(self, api, admin_tenant, make_tenant):
        """Not at token expiry — the locked user is refused on the next call."""
        victim = make_tenant(email="chan@agrilog.vn")

        assert victim.get("/api/v1/seasons").status_code == 200

        admin_tenant.patch(f"{ADMIN}/users/{victim.user_id}", json={"is_active": False})

        assert victim.get("/api/v1/seasons").status_code == 403
        r = api.post(
            "/api/v1/auth/login",
            json={"email": "chan@agrilog.vn", "password": "matkhau123"},
        )
        assert r.status_code == 401

    def test_cannot_lock_yourself_out(self, admin_tenant):
        r = admin_tenant.patch(
            f"{ADMIN}/users/{admin_tenant.user_id}", json={"is_active": False}
        )
        assert r.status_code == 409
        assert "chính mình" in r.json()["detail"]

    def test_cannot_lock_the_last_active_admin(self, db, admin_tenant, make_tenant):
        """A second admin locking the first is fine only while one remains."""
        other = make_tenant(email="quantri2@agrilog.vn")
        promote(db, other.user_id)

        # Two admins: locking one is allowed.
        r = admin_tenant.patch(f"{ADMIN}/users/{other.user_id}", json={"is_active": False})
        assert r.status_code == 200

        # One left, and it is not the caller: refused.
        third = make_tenant(email="quantri3@agrilog.vn")
        promote(db, third.user_id)
        db.get_bind()  # keep the session flushed state explicit
        admin_tenant.patch(f"{ADMIN}/users/{third.user_id}", json={"is_active": False})

        r = admin_tenant.patch(
            f"{ADMIN}/users/{admin_tenant.user_id}", json={"is_active": False}
        )
        assert r.status_code == 409

    def test_patch_cannot_grant_admin(self, admin_tenant, make_tenant):
        """`is_admin` is not in the update schema, so a forged field is ignored
        rather than honoured — the mass-assignment case."""
        victim = make_tenant(email="leo@agrilog.vn")
        r = admin_tenant.patch(
            f"{ADMIN}/users/{victim.user_id}",
            json={"is_active": True, "is_admin": True},
        )
        assert r.status_code == 200
        assert r.json()["is_admin"] is False

    def test_unknown_user_is_404(self, admin_tenant):
        r = admin_tenant.patch(f"{ADMIN}/users/{uuid.uuid4()}", json={"is_active": False})
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
#  Households
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.db
class TestAdminHouseholds:
    def test_lists_every_household_with_user_counts(self, admin_tenant, make_tenant):
        make_tenant(household_name="Hộ Trần")
        body = admin_tenant.get(f"{ADMIN}/households").json()

        names = {h["name"] for h in body["items"]}
        assert {"Hộ quản trị", "Hộ Trần"} <= names
        assert all(h["user_count"] >= 1 for h in body["items"])

    def test_search_by_name(self, admin_tenant, make_tenant):
        make_tenant(household_name="Hộ Đặc Biệt")
        items = admin_tenant.get(
            f"{ADMIN}/households", params={"search": "đặc biệt"}
        ).json()["items"]
        assert [h["name"] for h in items] == ["Hộ Đặc Biệt"]


# ═══════════════════════════════════════════════════════════════════════════
#  Overview
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.db
class TestAdminOverview:
    def test_counts_reflect_reality(self, admin_tenant, make_tenant):
        make_tenant()
        make_tenant()

        body = admin_tenant.get(f"{ADMIN}/overview").json()
        assert body["total_households"] >= 3
        assert body["total_users"] >= 3
        assert body["active_users"] + body["locked_users"] == body["total_users"]
        assert body["maintenance_enabled"] is False

    def test_locked_users_counted_separately(self, admin_tenant, make_tenant):
        victim = make_tenant()
        before = admin_tenant.get(f"{ADMIN}/overview").json()

        admin_tenant.patch(f"{ADMIN}/users/{victim.user_id}", json={"is_active": False})

        after = admin_tenant.get(f"{ADMIN}/overview").json()
        assert after["locked_users"] == before["locked_users"] + 1
        assert after["active_users"] == before["active_users"] - 1

    def test_soft_deleted_seasons_are_not_counted(self, admin_tenant, tenant):
        """A dashboard counting tombstones reports a busier system than exists."""
        created = tenant.post(
            "/api/v1/seasons",
            json={
                "name": "Vụ sẽ xoá",
                "crop_type": "Lúa",
                "start_date": 1786665600000,
                "status": "active",
            },
        )
        assert created.status_code == 201
        season_id = created.json()["id"]

        before = admin_tenant.get(f"{ADMIN}/overview").json()["total_seasons"]
        tenant.delete(f"/api/v1/seasons/{season_id}")
        after = admin_tenant.get(f"{ADMIN}/overview").json()["total_seasons"]

        assert after == before - 1


# ═══════════════════════════════════════════════════════════════════════════
#  Maintenance
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.db
class TestMaintenanceMode:
    def test_defaults_to_off(self, admin_tenant):
        body = admin_tenant.get(f"{ADMIN}/maintenance").json()
        assert body["maintenance_enabled"] is False
        assert body["maintenance_message"] is None

    def test_turn_on_with_a_message(self, admin_tenant):
        r = admin_tenant.put(
            f"{ADMIN}/maintenance",
            json={
                "maintenance_enabled": True,
                "maintenance_message": "Hệ thống đang bảo trì, thử lại sau 30 phút.",
            },
        )
        assert r.status_code == 200
        assert r.json()["maintenance_enabled"] is True
        assert "30 phút" in r.json()["maintenance_message"]

    def test_turning_off_clears_the_message(self, admin_tenant):
        admin_tenant.put(
            f"{ADMIN}/maintenance",
            json={"maintenance_enabled": True, "maintenance_message": "Đang bảo trì"},
        )
        r = admin_tenant.put(f"{ADMIN}/maintenance", json={"maintenance_enabled": False})
        assert r.json()["maintenance_enabled"] is False
        assert r.json()["maintenance_message"] is None

    def test_public_endpoint_needs_no_auth(self, api, admin_tenant):
        """The app must be able to read this with an expired token — that is
        exactly when the user most needs the explanation."""
        admin_tenant.put(
            f"{ADMIN}/maintenance",
            json={"maintenance_enabled": True, "maintenance_message": "Bảo trì"},
        )
        r = api.get("/api/v1/maintenance")
        assert r.status_code == 200
        assert r.json() == {
            "maintenance_enabled": True,
            "maintenance_message": "Bảo trì",
        }

    def test_ordinary_user_cannot_change_it(self, tenant):
        r = tenant.put(f"{ADMIN}/maintenance", json={"maintenance_enabled": True})
        assert r.status_code == 403

    def test_overview_reports_the_flag(self, admin_tenant):
        admin_tenant.put(f"{ADMIN}/maintenance", json={"maintenance_enabled": True})
        assert admin_tenant.get(f"{ADMIN}/overview").json()["maintenance_enabled"] is True


# ═══════════════════════════════════════════════════════════════════════════
#  Model-level guarantees — no HTTP
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.db
class TestAppSettingsSingleRow:
    def test_second_row_is_refused_by_the_database(self, db):
        """`CHECK (id = 1)` makes "exactly one row" a database fact, not a
        convention the application is trusted to keep."""
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            db.execute(
                text("INSERT INTO app_settings (id, maintenance_enabled) VALUES (2, true)")
            )
            db.flush()

    def test_migration_seeded_the_row(self, db):
        from app.models import AppSetting

        assert db.get(AppSetting, 1) is not None


class TestSchemas:
    """No database needed."""

    def test_update_schema_has_no_is_admin_field(self):
        from app.schemas.admin import AdminUserUpdate

        assert set(AdminUserUpdate.model_fields) == {"is_active"}

    def test_maintenance_message_is_length_capped(self):
        from pydantic import ValidationError

        from app.schemas.admin import MaintenanceUpdate

        with pytest.raises(ValidationError):
            MaintenanceUpdate(maintenance_enabled=True, maintenance_message="x" * 501)
