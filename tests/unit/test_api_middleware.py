"""
Unit tests for api.middleware — RequestID, ResponseMetadata, ProviderHeaders, RequestLog.

Mini FastAPI app + TestClient; her middleware'in başlık/davranış sözleşmesi.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.middleware import (
    RequestIDMiddleware,
    ResponseMetadataMiddleware,
    ProviderHeadersMiddleware,
    RequestLogMiddleware,
)


class TestRequestID:
    def _client(self):
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/x")
        def x(request: Request):
            return {"rid": request.state.request_id}

        return TestClient(app)

    def test_generates_request_id(self):
        r = self._client().get("/x")
        assert r.headers.get("X-Request-ID", "").startswith("req_")
        assert r.json()["rid"].startswith("req_")

    def test_honors_client_request_id(self):
        r = self._client().get("/x", headers={"X-Client-Request-ID": "my-id-123"})
        assert r.headers["X-Request-ID"] == "my-id-123"
        assert r.headers["X-Client-Request-ID"] == "my-id-123"  # acknowledged


class TestResponseMetadata:
    def test_adds_version_and_process_time(self):
        app = FastAPI()
        app.add_middleware(ResponseMetadataMiddleware, version="9.9.9")

        @app.get("/x")
        def x():
            return {"ok": True}

        r = TestClient(app).get("/x")
        assert r.headers["X-API-Version"] == "9.9.9"
        assert float(r.headers["X-Process-Time-Ms"]) >= 0


class TestProviderHeaders:
    def test_adds_provider_headers_when_in_state(self):
        app = FastAPI()
        app.add_middleware(ProviderHeadersMiddleware)

        @app.get("/x")
        def x(request: Request):
            request.state.llm_provider = "groq"
            request.state.llm_model = "llama-8b"
            request.state.rag_used = True
            return {"ok": True}

        r = TestClient(app).get("/x")
        assert r.headers["X-LLM-Provider"] == "groq"
        assert r.headers["X-LLM-Model"] == "llama-8b"
        assert r.headers["X-RAG-Used"] == "True"

    def test_no_headers_when_state_absent(self):
        app = FastAPI()
        app.add_middleware(ProviderHeadersMiddleware)

        @app.get("/x")
        def x():
            return {"ok": True}

        r = TestClient(app).get("/x")
        assert "X-LLM-Provider" not in r.headers


class TestRequestLog:
    def test_logs_without_breaking_response(self):
        # RequestID önce çalışmalı (request_id state'i için); sonra log
        app = FastAPI()
        app.add_middleware(RequestLogMiddleware)
        app.add_middleware(RequestIDMiddleware)

        @app.get("/x")
        def x():
            return {"ok": True}

        r = TestClient(app).get("/x")
        assert r.status_code == 200  # log middleware yanıtı bozmaz
