"""Authentication endpoints and service (Issue #14)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models import RefreshToken, User

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"

VALID = {
    "email": "nongho@agrilog.vn",
    "password": "matkhau123",
    "full_name": "Lê Văn A",
    "household_name": "Hộ ông Lê Văn A",
    "phone": "0912345678",
    "province": "Lâm Đồng",
    "commune": "Xã Hiệp An",
}


# ═══════════════════════════════════════════════════════════════════════════
#  Schema validation — no database required
# ═══════════════════════════════════════════════════════════════════════════


class TestPasswordPolicy:
    def test_short_password_rejected(self):
        from pydantic import ValidationError

        from app.schemas.auth import RegisterRequest

        with pytest.raises(ValidationError):
            RegisterRequest(**{**VALID, "password": "short"})

    def test_vietnamese_password_over_72_bytes_rejected(self):
        """40 Vietnamese characters is 120 bytes — past bcrypt's limit.

        Rejecting beats truncating: silent truncation means two different long
        passwords authenticate each other.
        """
        from pydantic import ValidationError

        from app.schemas.auth import RegisterRequest

        with pytest.raises(ValidationError, match="byte"):
            RegisterRequest(**{**VALID, "password": "ố" * 40})

    def test_normal_vietnamese_password_accepted(self):
        from app.schemas.auth import RegisterRequest

        req = RegisterRequest(**{**VALID, "password": "MùaVụĐôngXuân"})
        assert req.password == "MùaVụĐôngXuân"

    def test_email_normalisation(self):
        from app.services.auth_service import normalise_email

        assert normalise_email("  NongHo@AgriLog.VN ") == "nongho@agrilog.vn"


# ═══════════════════════════════════════════════════════════════════════════
#  Database-backed
# ═══════════════════════════════════════════════════════════════════════════

pytestmark_db = pytest.mark.db


@pytest.fixture
def registered(api):
    """A registered household; returns the parsed TokenPair."""
    r = api.post(REGISTER, json=VALID)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.db
class TestRegister:
    def test_creates_household_and_user(self, api, db):
        r = api.post(REGISTER, json=VALID)
        assert r.status_code == 201, r.text
        body = r.json()

        assert body["token_type"] == "bearer"
        assert body["access_token"] and body["refresh_token"]
        assert body["expires_in"] == 7 * 24 * 3600
        assert body["user"]["email"] == "nongho@agrilog.vn"
        assert body["household"]["name"] == "Hộ ông Lê Văn A"
        assert body["user"]["household_id"] == body["household"]["id"]

        assert db.execute(select(func.count()).select_from(User)).scalar_one() == 1

    def test_password_hash_never_returned(self, api):
        """The ORM object carries it; the response schema must not."""
        body = api.post(REGISTER, json=VALID).json()
        assert "password" not in str(body).lower() or "password_hash" not in body["user"]
        assert "password_hash" not in body["user"]

    def test_password_is_hashed_in_the_database(self, api, db):
        api.post(REGISTER, json=VALID)
        stored = db.execute(select(User.password_hash)).scalar_one()
        assert stored != VALID["password"]
        assert stored.startswith("$2b$12$")

    def test_email_stored_lowercase(self, api, db):
        api.post(REGISTER, json={**VALID, "email": "NongHo@AgriLog.VN"})
        assert db.execute(select(User.email)).scalar_one() == "nongho@agrilog.vn"

    def test_duplicate_email_conflicts(self, api):
        api.post(REGISTER, json=VALID)
        r = api.post(REGISTER, json=VALID)
        assert r.status_code == 409
        assert "đã được đăng ký" in r.json()["detail"]

    def test_duplicate_email_is_case_insensitive(self, api):
        """Otherwise A@x.vn and a@x.vn become two accounts for one person."""
        api.post(REGISTER, json=VALID)
        r = api.post(REGISTER, json={**VALID, "email": "NONGHO@AGRILOG.VN"})
        assert r.status_code == 409

    def test_registration_is_atomic(self, api, db):
        """A household with no user would be an orphan tenant."""
        api.post(REGISTER, json=VALID)
        api.post(REGISTER, json=VALID)   # fails
        from app.models import Household

        households = db.execute(select(func.count()).select_from(Household)).scalar_one()
        users = db.execute(select(func.count()).select_from(User)).scalar_one()
        assert households == 1 and users == 1

    def test_invalid_email_rejected(self, api):
        assert api.post(REGISTER, json={**VALID, "email": "not-an-email"}).status_code == 422

    def test_short_password_rejected(self, api):
        assert api.post(REGISTER, json={**VALID, "password": "abc"}).status_code == 422


@pytest.mark.db
class TestLogin:
    def test_success(self, api, registered):
        r = api.post(LOGIN, json={"email": VALID["email"], "password": VALID["password"]})
        assert r.status_code == 200
        assert r.json()["access_token"]

    def test_case_insensitive_email(self, api, registered):
        r = api.post(LOGIN, json={"email": "NONGHO@agrilog.vn", "password": VALID["password"]})
        assert r.status_code == 200

    def test_wrong_password_rejected(self, api, registered):
        r = api.post(LOGIN, json={"email": VALID["email"], "password": "wrongpassword"})
        assert r.status_code == 401

    def test_unknown_email_and_wrong_password_are_indistinguishable(self, api, registered):
        """Different messages turn the login form into an enumeration oracle."""
        unknown = api.post(LOGIN, json={"email": "nobody@agrilog.vn", "password": "whatever1"})
        wrong = api.post(LOGIN, json={"email": VALID["email"], "password": "wrongpassword"})
        assert unknown.status_code == wrong.status_code == 401
        assert unknown.json()["detail"] == wrong.json()["detail"]

    def test_inactive_account_rejected(self, api, db, registered):
        db.execute(User.__table__.update().values(is_active=False))
        db.flush()
        r = api.post(LOGIN, json={"email": VALID["email"], "password": VALID["password"]})
        assert r.status_code == 401

    def test_each_login_creates_a_session_row(self, api, db, registered):
        api.post(LOGIN, json={"email": VALID["email"], "password": VALID["password"]})
        count = db.execute(select(func.count()).select_from(RefreshToken)).scalar_one()
        assert count == 2   # one from register, one from login

    def test_refresh_token_stored_only_as_hash(self, api, db, registered):
        raw = registered["refresh_token"]
        stored = db.execute(select(RefreshToken.token_hash)).scalars().all()
        assert raw not in stored
        assert all(len(h) == 64 for h in stored)


@pytest.mark.db
class TestProtectedRoutes:
    def test_me_requires_a_token(self, api):
        assert api.get(ME).status_code == 401

    def test_me_returns_the_caller(self, api, registered):
        r = api.get(ME, headers={"Authorization": f"Bearer {registered['access_token']}"})
        assert r.status_code == 200
        assert r.json()["email"] == VALID["email"]

    def test_refresh_token_rejected_as_access_token(self, api, registered):
        """A 90-day credential must not silently become a 90-day session."""
        r = api.get(ME, headers={"Authorization": f"Bearer {registered['refresh_token']}"})
        assert r.status_code == 401

    def test_garbage_token_rejected(self, api):
        assert api.get(ME, headers={"Authorization": "Bearer nonsense"}).status_code == 401

    def test_tampered_token_rejected(self, api, registered):
        token = registered["access_token"]
        head, body, sig = token.split(".")
        r = api.get(ME, headers={"Authorization": f"Bearer {head}.{body}.{sig[:-4]}AAAA"})
        assert r.status_code == 401

    def test_deactivated_user_is_locked_out_immediately(self, api, db, registered):
        """A still-valid token must stop working the moment the account is disabled."""
        db.execute(User.__table__.update().values(is_active=False))
        db.flush()
        r = api.get(ME, headers={"Authorization": f"Bearer {registered['access_token']}"})
        assert r.status_code == 403


@pytest.mark.db
class TestRefreshRotation:
    def test_returns_a_new_pair(self, api, registered):
        r = api.post(REFRESH, json={"refresh_token": registered["refresh_token"]})
        assert r.status_code == 200
        assert r.json()["refresh_token"] != registered["refresh_token"]

    def test_old_token_stops_working(self, api, registered):
        """Refresh tokens are single-use."""
        old = registered["refresh_token"]
        api.post(REFRESH, json={"refresh_token": old})
        assert api.post(REFRESH, json={"refresh_token": old}).status_code == 401

    def test_reuse_revokes_every_session(self, api, db, registered):
        """Replay of a rotated token means theft or a client bug, and we cannot
        tell which. Losing a session is recoverable; an attacker holding a
        90-day credential is not."""
        old = registered["refresh_token"]
        fresh = api.post(REFRESH, json={"refresh_token": old}).json()["refresh_token"]

        r = api.post(REFRESH, json={"refresh_token": old})   # replay
        assert r.status_code == 401
        assert "dùng lại" in r.json()["detail"]

        # the token issued legitimately in between is now dead too
        assert api.post(REFRESH, json={"refresh_token": fresh}).status_code == 401
        live = db.execute(
            select(func.count()).select_from(RefreshToken).where(RefreshToken.revoked_at.is_(None))
        ).scalar_one()
        assert live == 0

    def test_new_access_token_works(self, api, registered):
        new = api.post(REFRESH, json={"refresh_token": registered["refresh_token"]}).json()
        r = api.get(ME, headers={"Authorization": f"Bearer {new['access_token']}"})
        assert r.status_code == 200

    def test_unknown_token_rejected(self, api, registered):
        from app.core.security import create_refresh_token

        orphan, _, _ = create_refresh_token("00000000-0000-0000-0000-000000000001")
        assert api.post(REFRESH, json={"refresh_token": orphan}).status_code == 401

    def test_access_token_rejected_here(self, api, registered):
        r = api.post(REFRESH, json={"refresh_token": registered["access_token"]})
        assert r.status_code == 401


@pytest.mark.db
class TestLogout:
    def test_revokes_the_session(self, api, registered):
        assert api.post(LOGOUT, json={"refresh_token": registered["refresh_token"]}).status_code == 204
        assert api.post(REFRESH, json={"refresh_token": registered["refresh_token"]}).status_code == 401

    def test_is_idempotent(self, api, registered):
        """Telling a caller 'that token was already invalid' is not actionable,
        and confirms token validity to anyone probing."""
        api.post(LOGOUT, json={"refresh_token": registered["refresh_token"]})
        assert api.post(LOGOUT, json={"refresh_token": registered["refresh_token"]}).status_code == 204

    def test_unknown_token_still_204(self, api):
        assert api.post(LOGOUT, json={"refresh_token": "never-existed"}).status_code == 204

    def test_access_token_survives_logout_until_expiry(self, api, registered):
        """Documented, accepted trade-off of stateless JWTs.

        Revoking access tokens would need a server-side blocklist checked on
        every request — which is precisely the always-online dependency this
        app is built to avoid. The access token is short-lived relative to the
        refresh token, and logout kills the ability to renew.
        """
        api.post(LOGOUT, json={"refresh_token": registered["refresh_token"]})
        r = api.get(ME, headers={"Authorization": f"Bearer {registered['access_token']}"})
        assert r.status_code == 200


@pytest.mark.db
class TestHouseholdScoping:
    def test_token_carries_the_household(self, registered):
        from app.core.security import decode_token

        payload = decode_token(registered["access_token"], expected_type="access")
        assert payload["hid"] == registered["household"]["id"]

    def test_two_households_are_separate_tenants(self, api):
        a = api.post(REGISTER, json=VALID).json()
        b = api.post(REGISTER, json={**VALID, "email": "khac@agrilog.vn",
                                     "household_name": "Hộ bà B"}).json()
        assert a["household"]["id"] != b["household"]["id"]

    def test_token_household_must_match_the_database(self, api, db, registered):
        """Defence in depth: if the two disagree, serving the request would
        scope it to the wrong tenant — the worst failure this API can have."""
        import uuid

        from app.models import Household

        other = Household(name="Hộ khác")
        db.add(other)
        db.flush()
        db.execute(User.__table__.update().values(household_id=other.id))
        db.flush()

        r = api.get(ME, headers={"Authorization": f"Bearer {registered['access_token']}"})
        assert r.status_code == 401
        assert uuid.UUID(str(other.id))
