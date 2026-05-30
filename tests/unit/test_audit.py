"""
Tests for api.audit (SQLite audit log + middleware).

Isolated temp DB per test. Covers record/query, filtering, the auto-recording
middleware, and the /api/audit query endpoint guarded by RBAC.
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api import db
from api.audit import AuditMiddleware, AuditStore, audit_router
from api.auth import get_current_user
from api.auth_models import AuthenticatedUser, Role
from api.errors import APIError, api_error_handler


@pytest.fixture
def audit_db(tmp_path):
    db.reset_for_tests(str(tmp_path / "auth.db"))
    try:
        yield AuditStore()
    finally:
        db.reset_for_tests("data/auth.db")


class TestAuditStore:
    def test_record_then_query(self, audit_db):
        audit_db.record("login_success", username="alice", role="security", status=200)
        rows = audit_db.query(limit=10)
        assert len(rows) == 1
        assert rows[0]["action"] == "login_success" and rows[0]["username"] == "alice"

    def test_query_filter_by_user(self, audit_db):
        audit_db.record("request", username="alice")
        audit_db.record("request", username="bob")
        rows = audit_db.query(username="bob")
        assert len(rows) == 1 and rows[0]["username"] == "bob"

    def test_query_filter_by_action(self, audit_db):
        audit_db.record("login_success", username="a")
        audit_db.record("login_failure", username="a")
        assert len(audit_db.query(action="login_failure")) == 1

    def test_newest_first(self, audit_db):
        audit_db.record("request", detail="first")
        audit_db.record("request", detail="second")
        rows = audit_db.query()
        assert rows[0]["detail"] == "second"  # en yeni önce


class TestAuditMiddleware:
    def test_middleware_records_request(self, tmp_path):
        db.reset_for_tests(str(tmp_path / "auth.db"))
        try:
            app = FastAPI()
            app.add_middleware(AuditMiddleware, enabled=True)

            @app.get("/ping")
            def ping():
                return {"pong": True}

            client = TestClient(app)
            assert client.get("/ping").status_code == 200
            rows = AuditStore().query()
            assert any(r["endpoint"] == "/ping" and r["status"] == 200 for r in rows)
        finally:
            db.reset_for_tests("data/auth.db")

    def test_health_is_skipped(self, tmp_path):
        db.reset_for_tests(str(tmp_path / "auth.db"))
        try:
            app = FastAPI()
            app.add_middleware(AuditMiddleware, enabled=True)

            @app.get("/health")
            def health():
                return {"status": "ok"}

            TestClient(app).get("/health")
            assert AuditStore().query() == []  # /health muaf
        finally:
            db.reset_for_tests("data/auth.db")


class TestAuditEndpointRBAC:
    def _app(self, role: Role):
        app = FastAPI()
        app.add_exception_handler(APIError, api_error_handler)
        app.include_router(audit_router, prefix="/api")
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser("t", role)
        return TestClient(app, raise_server_exceptions=False)

    def test_security_can_view(self, tmp_path):
        db.reset_for_tests(str(tmp_path / "auth.db"))
        try:
            assert self._app(Role.SECURITY).get("/api/audit").status_code == 200
        finally:
            db.reset_for_tests("data/auth.db")

    def test_end_user_forbidden(self, tmp_path):
        db.reset_for_tests(str(tmp_path / "auth.db"))
        try:
            r = self._app(Role.END_USER).get("/api/audit")
            assert r.status_code == 403
        finally:
            db.reset_for_tests("data/auth.db")
