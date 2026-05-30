"""
Tests for user-based rate-limit keying (api.security + api.auth.peek_username).

The rate-limit key is `user:{username}` when a valid JWT is present (header or
query), else `ip:{ip}`. This makes quotas fair behind NAT/shared IPs.
"""

from __future__ import annotations

import pytest
from starlette.requests import Request

from api import auth_blacklist, db
from api.auth import create_access_token, peek_username
from api.auth_models import AuthenticatedUser, Role
from api.security import RateLimitConfig, RateLimitMiddleware


def _request(headers=None, query_string=b"", client=("9.9.9.9", 1111)) -> Request:
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/api/chat",
        "headers": raw_headers,
        "query_string": query_string,
        "client": client,
    })


@pytest.fixture
def auth_env(tmp_path, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    db.reset_for_tests(str(tmp_path / "auth.db"))
    auth_blacklist.reset_for_tests()
    try:
        yield
    finally:
        db.reset_for_tests("data/auth.db")
        auth_blacklist.reset_for_tests()


def _mw():
    # BaseHTTPMiddleware app arg is unused by _get_rate_limit_key; pass a dummy.
    return RateLimitMiddleware(app=lambda *a, **k: None, config=RateLimitConfig())


class TestPeekUsername:
    def test_valid_header_token(self, auth_env):
        tok, _ = create_access_token(AuthenticatedUser("alice", Role.DEVELOPER))
        assert peek_username(_request({"Authorization": f"Bearer {tok}"})) == "alice"

    def test_valid_query_token(self, auth_env):
        tok, _ = create_access_token(AuthenticatedUser("bob", Role.END_USER))
        assert peek_username(_request(query_string=f"access_token={tok}".encode())) == "bob"

    def test_no_token_returns_none(self, auth_env):
        assert peek_username(_request()) is None

    def test_garbage_token_returns_none(self, auth_env):
        assert peek_username(_request({"Authorization": "Bearer garbage"})) is None

    def test_blacklisted_token_returns_none(self, auth_env):
        tok, _ = create_access_token(AuthenticatedUser("carol", Role.SYSADMIN))
        # jti'yi çöz + blacklist'e al
        import jwt
        from api import auth as auth_mod
        payload = jwt.decode(tok, auth_mod._secret(), algorithms=[auth_mod._algorithm()])
        auth_blacklist.block_token(payload["jti"], payload["exp"])
        assert peek_username(_request({"Authorization": f"Bearer {tok}"})) is None


class TestRateLimitKey:
    def test_user_key_when_token_present(self, auth_env):
        tok, _ = create_access_token(AuthenticatedUser("alice", Role.DEVELOPER))
        key = _mw()._get_rate_limit_key(_request({"Authorization": f"Bearer {tok}"}))
        assert key == "user:alice"

    def test_ip_key_when_no_token(self, auth_env):
        key = _mw()._get_rate_limit_key(_request(client=("1.2.3.4", 5555)))
        assert key == "ip:1.2.3.4"
