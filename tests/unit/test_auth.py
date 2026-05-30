"""
Tests for API-key authentication (api.auth.require_api_key).

A minimal app mounts a protected route + a public route; the API_KEY env var
is toggled via monkeypatch. Covers: enforced when configured, open in dev mode,
wrong/missing key rejected, public routes always reachable.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

import api.auth as auth
from api.auth import require_api_key, auth_enabled, API_KEY_ENV
from api.errors import APIError, api_error_handler


@pytest.fixture
def client():
    app = FastAPI()
    app.add_exception_handler(APIError, api_error_handler)

    @app.get("/protected", dependencies=[Depends(require_api_key)])
    def protected():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return TestClient(app, raise_server_exceptions=False)


class TestAuthConfigured:
    def test_missing_key_rejected(self, client, monkeypatch):
        monkeypatch.setenv(API_KEY_ENV, "secret-key")
        r = client.get("/protected")
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "UNAUTHORIZED"

    def test_wrong_key_rejected(self, client, monkeypatch):
        monkeypatch.setenv(API_KEY_ENV, "secret-key")
        r = client.get("/protected", headers={"X-API-Key": "nope"})
        assert r.status_code == 401

    def test_correct_key_allowed(self, client, monkeypatch):
        monkeypatch.setenv(API_KEY_ENV, "secret-key")
        r = client.get("/protected", headers={"X-API-Key": "secret-key"})
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_health_is_public_even_with_auth(self, client, monkeypatch):
        monkeypatch.setenv(API_KEY_ENV, "secret-key")
        assert client.get("/health").status_code == 200


class TestAuthDisabled:
    def test_dev_mode_allows_without_key(self, client, monkeypatch):
        monkeypatch.delenv(API_KEY_ENV, raising=False)
        auth._warned = False  # reset one-time warning
        r = client.get("/protected")
        assert r.status_code == 200

    def test_auth_enabled_flag(self, monkeypatch):
        monkeypatch.delenv(API_KEY_ENV, raising=False)
        assert auth_enabled() is False
        monkeypatch.setenv(API_KEY_ENV, "x")
        assert auth_enabled() is True
        monkeypatch.setenv(API_KEY_ENV, "   ")  # whitespace = not configured
        assert auth_enabled() is False
