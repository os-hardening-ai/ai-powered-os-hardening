"""
Tests for sanitized internal-error handling (no leakage of exception text).

Routers previously returned `message=f"...: {str(e)}"`, exposing internal
implementation details (and potentially secrets) to clients. raise_internal_error
must keep the real cause server-side only and return a generic client message.
"""

from __future__ import annotations

import textwrap

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.errors import APIError, ErrorCode, api_error_handler, raise_internal_error


class TestRaiseInternalError:
    def test_raises_apierror_without_leaking_exception_text(self):
        secret = "DB password=hunter2 at /etc/secret"
        with pytest.raises(APIError) as ei:
            raise_internal_error("some_stage", RuntimeError(secret))
        err = ei.value
        assert err.status_code == 500
        # client-facing message must be generic — NOT the exception text
        assert secret not in err.error_detail.message
        assert "internal error" in err.error_detail.message.lower()
        assert err.error_detail.request_id  # correlation id present
        assert err.error_detail.details == {"stage": "some_stage"}

    def test_custom_code_and_status(self):
        with pytest.raises(APIError) as ei:
            raise_internal_error(
                "rag", ValueError("qdrant down"),
                error_code=ErrorCode.SERVICE_UNAVAILABLE, status_code=503,
            )
        assert ei.value.status_code == 503
        assert "qdrant down" not in ei.value.error_detail.message


class TestEndpointDoesNotLeak:
    """End-to-end: a route that explodes must return a sanitized 500 body."""

    def _client(self):
        app = FastAPI()
        app.add_exception_handler(APIError, api_error_handler)

        @app.get("/boom")
        def boom():
            try:
                raise RuntimeError("super secret internal trace: token=abc123")
            except Exception as e:
                raise_internal_error("boom_stage", e)

        return TestClient(app, raise_server_exceptions=False)

    def test_response_body_is_sanitized(self):
        r = self._client().get("/boom")
        assert r.status_code == 500
        body = r.text
        assert "super secret" not in body
        assert "token=abc123" not in body
        payload = r.json()["error"]
        assert payload["code"] == ErrorCode.INTERNAL_ERROR.value
        assert payload["request_id"]
