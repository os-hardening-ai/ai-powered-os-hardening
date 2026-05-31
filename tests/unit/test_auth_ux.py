"""
Tests for the auth-UX endpoints: /auth/register, /auth/forgot-password, /auth/reset-password.

Mirrors the test_auth.py setup: a minimal app mounts the real auth router, users live
in an isolated temp SQLite DB, dev mode (no JWT_SECRET → fixed dev secret, so reset
tokens are returned in the response body for testability). Covers: register success +
auto-login, duplicate username (409), short username/password validation (422),
forgot→token issued (existing) vs generic-message-only (unknown user), reset success +
new password works + old fails, one-time token consumption, invalid/garbage token (400).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import auth_blacklist, auth_reset, db
from api import router_auth
from api.auth_models import Role
from api.auth_store import user_store
from api.errors import APIError, api_error_handler
from api.router_auth import router as auth_router


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    # Dev mode'u kesinleştir → forgot-password yanıtında reset_token döner.
    # (is_dev_mode global config'i okur; tam suite çalışırken başka test JWT_SECRET
    #  yüklemiş olabilir → burada doğrudan dev-mode'a sabitliyoruz.)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setattr(router_auth, "is_dev_mode", lambda: True)
    db.reset_for_tests(str(tmp_path / "auth.db"))
    auth_blacklist.reset_for_tests()
    auth_reset.reset_for_tests()
    user_store.create("admin", "adminpass", Role.SYSADMIN)

    app = FastAPI()
    app.add_exception_handler(APIError, api_error_handler)
    app.include_router(auth_router)
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        db.reset_for_tests("data/auth.db")
        auth_blacklist.reset_for_tests()
        auth_reset.reset_for_tests()


def _register(client, username, password):
    return client.post("/auth/register", json={"username": username, "password": password})


def _forgot(client, username):
    return client.post("/auth/forgot-password", json={"username": username})


def _reset(client, token, new_password):
    return client.post("/auth/reset-password", json={"token": token, "new_password": new_password})


def _login(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password})


class TestRegister:
    def test_register_returns_token_with_end_user_role(self, app_client):
        r = _register(app_client, "yeni_kisi", "parola123")
        assert r.status_code == 200
        body = r.json()
        assert body["role"] == "end_user"
        assert body["token_type"] == "bearer"
        assert body["access_token"] and body["expires_in"] > 0

    def test_registered_user_can_login(self, app_client):
        _register(app_client, "loginme", "parola123")
        assert _login(app_client, "loginme", "parola123").status_code == 200

    def test_duplicate_username_409(self, app_client):
        _register(app_client, "ikikere", "parola123")
        r = _register(app_client, "ikikere", "baskaparola")
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_existing_seed_user_conflict_409(self, app_client):
        # 'admin' fixture'da var → register reddedilmeli
        assert _register(app_client, "admin", "parola123").status_code == 409

    def test_short_username_422(self, app_client):
        assert _register(app_client, "ab", "parola123").status_code == 422

    def test_short_password_422(self, app_client):
        assert _register(app_client, "gecerli_ad", "123").status_code == 422


class TestForgotPassword:
    def test_existing_user_gets_reset_token_in_dev(self, app_client):
        r = _forgot(app_client, "admin")
        assert r.status_code == 200
        body = r.json()
        assert body["message"]  # genel mesaj
        assert body["reset_token"]  # dev-mode → token döner

    def test_unknown_user_same_message_no_token(self, app_client):
        r = _forgot(app_client, "hayalet_kullanici")
        assert r.status_code == 200
        body = r.json()
        assert body["message"]  # aynı genel mesaj (enumeration yok)
        assert body["reset_token"] is None


class TestResetPassword:
    def test_reset_changes_password(self, app_client):
        token = _forgot(app_client, "admin").json()["reset_token"]
        assert _reset(app_client, token, "yeniParola1").status_code == 200
        # Yeni parola çalışır, eski çalışmaz
        assert _login(app_client, "admin", "yeniParola1").status_code == 200
        assert _login(app_client, "admin", "adminpass").status_code == 401

    def test_token_is_one_time(self, app_client):
        token = _forgot(app_client, "admin").json()["reset_token"]
        assert _reset(app_client, token, "yeniParola1").status_code == 200
        # İkinci kullanım reddedilmeli
        assert _reset(app_client, token, "tekrarParola2").status_code == 400

    def test_invalid_token_400(self, app_client):
        r = _reset(app_client, "kesinlikle-gecersiz-token-xyz", "yeniParola1")
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_short_new_password_422(self, app_client):
        token = _forgot(app_client, "admin").json()["reset_token"]
        assert _reset(app_client, token, "12").status_code == 422
