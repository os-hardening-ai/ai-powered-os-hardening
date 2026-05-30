"""
Reliability tests for /rag/search — graceful degradation when the retriever
(Qdrant/embedding) is unavailable or slow.

Previously the endpoint built a new RAGRetriever per request with no timeout,
so a Qdrant outage surfaced as an opaque 500. Now: thread-safe singleton +
timeout, returning 503 (unavailable) / 504 (timeout). The retriever is faked.
"""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.router_rag as rag_mod
from api.router_rag import router as rag_router
from api.errors import APIError, api_error_handler


@pytest.fixture
def client():
    app = FastAPI()
    app.add_exception_handler(APIError, api_error_handler)
    app.include_router(rag_router, prefix="/rag")
    return TestClient(app, raise_server_exceptions=False)


class _FakeRetriever:
    def __init__(self, *, error=None, delay=0.0):
        self._error = error
        self._delay = delay

    def search(self, **kwargs):
        if self._delay:
            time.sleep(self._delay)
        if self._error:
            raise self._error
        return []


class TestRagReliability:
    def test_retriever_failure_returns_503_not_500(self, client, monkeypatch):
        monkeypatch.setattr(
            rag_mod, "get_retriever",
            lambda: _FakeRetriever(error=RuntimeError("qdrant connection refused")),
        )
        r = client.post("/rag/search", json={"query": "ssh hardening"})
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
        # must not leak the raw exception text
        assert "connection refused" not in r.text

    def test_construction_failure_returns_503(self, client, monkeypatch):
        def boom():
            raise RuntimeError("cannot reach Qdrant at startup")
        monkeypatch.setattr(rag_mod, "get_retriever", boom)
        r = client.post("/rag/search", json={"query": "ssh"})
        assert r.status_code == 503

    def test_timeout_returns_504(self, client, monkeypatch):
        monkeypatch.setattr(rag_mod, "_SEARCH_TIMEOUT_S", 0.05)
        monkeypatch.setattr(rag_mod, "get_retriever", lambda: _FakeRetriever(delay=0.5))
        r = client.post("/rag/search", json={"query": "ssh"})
        assert r.status_code == 504
        assert r.json()["error"]["code"] == "TIMEOUT"

    def test_empty_query_rejected_by_schema(self, client):
        r = client.post("/rag/search", json={"query": ""})
        assert r.status_code == 422  # min_length=1
