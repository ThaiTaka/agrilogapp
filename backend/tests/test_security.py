"""Password hashing and JWT. No database required."""

from __future__ import annotations

import time
import uuid

import pytest

from app.core.security import (
    BCRYPT_MAX_BYTES,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_then_verify_roundtrip(self):
        h = hash_password("m@tKh@u123")
        assert verify_password("m@tKh@u123", h)

    def test_wrong_password_rejected(self):
        h = hash_password("m@tKh@u123")
        assert not verify_password("m@tKh@u124", h)

    def test_hash_is_salted(self):
        """Two hashes of the same password must differ, or the table is a rainbow."""
        assert hash_password("same") != hash_password("same")

    def test_hash_is_not_the_password(self):
        h = hash_password("plaintext")
        assert "plaintext" not in h
        assert h.startswith("$2b$12$")   # bcrypt, cost 12

    def test_vietnamese_password_works(self):
        pw = "MùaVụĐôngXuân2026"
        assert verify_password(pw, hash_password(pw))

    def test_overlong_password_rejected_not_truncated(self):
        """bcrypt silently truncates past 72 bytes.

        Silent truncation means two different long passwords authenticate each
        other, so it is refused rather than absorbed.
        """
        with pytest.raises(ValueError, match="72-byte"):
            hash_password("a" * (BCRYPT_MAX_BYTES + 1))

    def test_diacritics_count_as_multiple_bytes(self):
        """A 40-character Vietnamese password can exceed the 72-BYTE limit."""
        pw = "ố" * 40   # 3 bytes each in UTF-8 = 120 bytes
        with pytest.raises(ValueError):
            hash_password(pw)

    def test_malformed_hash_returns_false_not_exception(self):
        assert verify_password("anything", "not-a-bcrypt-hash") is False


class TestJWT:
    def test_access_token_roundtrip(self):
        uid, hid = uuid.uuid4(), uuid.uuid4()
        payload = decode_token(create_access_token(uid, hid), expected_type="access")
        assert payload["sub"] == str(uid)
        assert payload["hid"] == str(hid)
        assert payload["typ"] == "access"

    def test_household_is_embedded(self):
        """Sync derives the tenant from the token, never from the payload.

        A client therefore cannot write into another household by forging a
        field, because the field is not read from the request at all.
        """
        hid = uuid.uuid4()
        assert decode_token(create_access_token(uuid.uuid4(), hid))["hid"] == str(hid)

    def test_refresh_token_is_stored_only_as_a_hash(self):
        raw, stored_hash, expires_at = create_refresh_token(uuid.uuid4())
        assert stored_hash == hash_token(raw)
        assert raw not in stored_hash
        assert len(stored_hash) == 64          # sha256 hex
        assert expires_at.timestamp() > time.time()

    def test_refresh_token_rejected_where_access_expected(self):
        """Otherwise a 90-day credential silently becomes a 90-day session."""
        raw, _, _ = create_refresh_token(uuid.uuid4())
        with pytest.raises(TokenError, match="Expected a 'access' token"):
            decode_token(raw, expected_type="access")

    def test_tampered_signature_rejected(self):
        token = create_access_token(uuid.uuid4(), uuid.uuid4())
        head, body, sig = token.split(".")
        with pytest.raises(TokenError):
            decode_token(f"{head}.{body}.{sig[:-4]}AAAA")

    def test_expired_token_rejected(self):
        expired = create_access_token(uuid.uuid4(), uuid.uuid4(), expires_minutes=-1)
        with pytest.raises(TokenError):
            decode_token(expired)

    def test_garbage_rejected(self):
        with pytest.raises(TokenError):
            decode_token("not.a.token")

    def test_tokens_are_unique_per_issue(self):
        """The jti claim must make two tokens for one user distinguishable."""
        uid, hid = uuid.uuid4(), uuid.uuid4()
        a = decode_token(create_access_token(uid, hid))
        b = decode_token(create_access_token(uid, hid))
        assert a["jti"] != b["jti"]
