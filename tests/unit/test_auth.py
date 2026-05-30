"""
Tests for JWT authentication + RBAC (api.auth).

A minimal app mounts the real auth router (/auth/login, /logout, /me) plus two
role-protected routes. Users live in a temporary SQLite DB (isolated per test),
auth runs in dev mode (no JWT_SECRET → fixed dev secret). Covers: login success/
failure, missing/garbage/expired token (401), logout→blacklist (401), RBAC (403),
and the SSE query-token fallback.
"""

from __future__ import annotations

import time
import uuid

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api import auth as auth_mod
from api import auth_blacklist, db
from api.auth import create_access_token, get_current_user, require_role
from api.auth_models import AuthenticatedUser, Role
from api.auth_store import user_store
from api.errors import APIError, api_error_handler
from api.router_auth import router as auth_router


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    # Dev mode (sabit dev-secret) — JWT_SECRET kapalı.
    monkeypatch.delenv("JWT_SECRET", raising=False)
    db.reset_for_tests(str(tmp_path / "auth.db"))
    auth_blacklist.reset_for_tests()
    user_store.create("admin", "adminpass", Role.SYSADMIN)
    user_store.create("ender", "userpass", Role.END_USER)

    app = FastAPI()
    app.add_exception_handler(APIError, api_error_handler)
    app.include_router(auth_router)

    @app.get("/sysadmin-only", dependencies=[Depends(require_role(Role.SYSADMIN))])
    def sysadmin_only():
        return {"ok": True}

    @app.get("/any-auth")
    def any_auth(user: AuthenticatedUser = Depends(get_current_user)):
        return {"user": user.username, "role": user.role.value}

    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        # Global bağlantıyı varsayılana geri al (diğer testleri etkilemesin).
        db.reset_for_tests("data/auth.db")
        auth_blacklist.reset_for_tests()


def _login(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password})


class TestLogin:
    def test_login_success_returns_token(self, app_client):
        r = _login(app_client, "admin", "adminpass")
        assert r.status_code == 200
        body = r.json()
        assert body["token_type"] == "bearer"
        assert body["role"] == "sysadmin"
        assert body["access_token"] and body["expires_in"] > 0

    def test_login_wrong_password_401(self, app_client):
        r = _login(app_client, "admin", "WRONG")
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "UNAUTHORIZED"

    def test_login_unknown_user_401(self, app_client):
        assert _login(app_client, "ghost", "x").status_code == 401


class TestProtectedRoutes:
    def test_no_token_401(self, app_client):
        assert app_client.get("/any-auth").status_code == 401

    def test_garbage_token_401(self, app_client):
        r = app_client.get("/any-auth", headers={"Authorization": "Bearer not.a.jwt"})
        assert r.status_code == 401

    def test_valid_token_200(self, app_client):
        tok = _login(app_client, "ender", "userpass").json()["access_token"]
        r = app_client.get("/any-auth", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        assert r.json() == {"user": "ender", "role": "end_user"}

    def test_query_param_token_fallback(self, app_client):
        # EventSource/SSE: Authorization header gönderemez → ?access_token=
        tok = _login(app_client, "ender", "userpass").json()["access_token"]
        r = app_client.get(f"/any-auth?access_token={tok}")
        assert r.status_code == 200
        assert r.json()["user"] == "ender"

    def test_expired_token_401(self, app_client):
        # Geçmiş exp ile manuel token üret (dev secret ile imzalı).
        payload = {
            "sub": "admin", "role": "sysadmin", "jti": uuid.uuid4().hex,
            "iat": int(time.time()) - 200, "exp": int(time.time()) - 100,
        }
        tok = jwt.encode(payload, auth_mod._secret(), algorithm=auth_mod._algorithm())
        r = app_client.get("/any-auth", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401


class TestLogoutBlacklist:
    def test_logout_blacklists_token(self, app_client):
        tok = _login(app_client, "admin", "adminpass").json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        assert app_client.get("/auth/me", headers=h).status_code == 200
        assert app_client.post("/auth/logout", headers=h).status_code == 200
        # Aynı token artık reddedilmeli
        assert app_client.get("/auth/me", headers=h).status_code == 401


class TestRBAC:
    def test_end_user_forbidden_on_sysadmin_route(self, app_client):
        tok = _login(app_client, "ender", "userpass").json()["access_token"]
        r = app_client.get("/sysadmin-only", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "FORBIDDEN"

    def test_sysadmin_allowed_on_sysadmin_route(self, app_client):
        tok = _login(app_client, "admin", "adminpass").json()["access_token"]
        r = app_client.get("/sysadmin-only", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200


class TestTokenRoundtrip:
    def test_create_then_decode(self, app_client):
        tok, expires_in = create_access_token(AuthenticatedUser("admin", Role.SYSADMIN))
        payload = auth_mod.decode_token(tok)
        assert payload["sub"] == "admin" and payload["role"] == "sysadmin"
        assert "jti" in payload and expires_in > 0


class TestTokenSecurity:
    def test_foreign_secret_token_rejected(self, app_client):
        # Baska bir secret ile imzalanmis token → imza dogrulanmaz → 401
        bad = jwt.encode(
            {"sub": "admin", "role": "sysadmin", "jti": uuid.uuid4().hex,
             "iat": int(time.time()), "exp": int(time.time()) + 600},
            "totally-different-secret-not-ours-xxxxxxxx", algorithm="HS256",
        )
        r = app_client.get("/any-auth", headers={"Authorization": f"Bearer {bad}"})
        assert r.status_code == 401

    def test_tampered_token_rejected(self, app_client):
        tok = _login(app_client, "admin", "adminpass").json()["access_token"]
        tampered = tok[:-3] + ("aaa" if not tok.endswith("aaa") else "bbb")
        r = app_client.get("/any-auth", headers={"Authorization": f"Bearer {tampered}"})
        assert r.status_code == 401

    def test_missing_role_claim_rejected(self, app_client):
        tok = jwt.encode(
            {"sub": "admin", "jti": uuid.uuid4().hex,
             "iat": int(time.time()), "exp": int(time.time()) + 600},
            auth_mod._secret(), algorithm=auth_mod._algorithm(),
        )
        r = app_client.get("/any-auth", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401

    def test_invalid_role_value_rejected(self, app_client):
        tok = jwt.encode(
            {"sub": "admin", "role": "superduper", "jti": uuid.uuid4().hex,
             "iat": int(time.time()), "exp": int(time.time()) + 600},
            auth_mod._secret(), algorithm=auth_mod._algorithm(),
        )
        r = app_client.get("/any-auth", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401


class TestAuthConfigValidation:
    def test_short_secret_rejected(self):
        from config.schemas import AuthConfig
        with pytest.raises(ValueError):
            AuthConfig(jwt_secret="too-short")

    def test_valid_long_secret_ok(self):
        from config.schemas import AuthConfig
        cfg = AuthConfig(jwt_secret="x" * 32)
        assert cfg.jwt_secret == "x" * 32

    def test_bad_algorithm_rejected(self):
        from config.schemas import AuthConfig
        with pytest.raises(ValueError):
            AuthConfig(algorithm="RS256-bogus")

    def test_too_short_expiry_rejected(self):
        from config.schemas import AuthConfig
        with pytest.raises(ValueError):
            AuthConfig(access_token_expiry_minutes=1)
