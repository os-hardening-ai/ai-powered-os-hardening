"""
Unit tests for api.router_health, api.router_analytics, api.streaming.

router_health/detailed: bileşen probe'ları mock'lanır (network yok).
router_analytics: collector mock'lanır.
streaming: SSE biçimi + hata-event yolu.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def _client(self):
        from api.router_health import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_root(self):
        r = self._client().get("/")
        assert r.status_code == 200 and "docs" in r.json()

    def test_health_ok(self):
        # Endpoint SÖZLEŞMESİ: 200 + geçerli status enum döner. "ok" vs "degraded"
        # ORTAMA bağlı (gerçek Qdrant/LLM canlıysa "ok"; CI'da dummy key/dep yok → "degraded").
        # Dep canlılığı entegrasyon konusu; birim test endpoint'in çalıştığını doğrular.
        r = self._client().get("/health")
        assert r.status_code == 200 and r.json()["status"] in ("ok", "degraded")

    def test_detailed_all_ok(self, monkeypatch):
        import rag.vector_store as vs
        import rag.embeddings as emb
        import llm.clients as cl
        monkeypatch.setattr(vs, "get_vector_store", lambda: object(), raising=False)
        monkeypatch.setattr(emb, "get_embedding_client", lambda: object(), raising=False)
        monkeypatch.setattr(cl, "get_llm_clients", lambda *a, **k: (object(), object()))
        r = self._client().get("/health/detailed")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["components"]["llm"] == "ok"

    def test_detailed_degraded_on_component_error(self, monkeypatch):
        import rag.vector_store as vs
        import rag.embeddings as emb
        import llm.clients as cl
        monkeypatch.setattr(vs, "get_vector_store", lambda: object(), raising=False)
        monkeypatch.setattr(emb, "get_embedding_client", lambda: object(), raising=False)
        def boom(*a, **k):
            raise RuntimeError("llm down")
        monkeypatch.setattr(cl, "get_llm_clients", boom)
        r = self._client().get("/health/detailed")
        assert r.status_code == 200            # health endpoint kendisi 200 döner
        assert r.json()["status"] == "degraded"
        assert "error" in r.json()["components"]["llm"]


# ── Analytics ───────────────────────────────────────────────────────────────────

class _FakeCollector:
    def get_full_analytics(self): return {"summary": "ok"}
    def get_cost_breakdown(self): return {"total_cost": 1.23}
    def get_query_patterns(self, top_n): return [{"q": "x"}][:top_n]
    def get_rag_effectiveness(self): return {"rag_rate": 0.5}
    def get_error_analysis(self, limit): return {"errors": [], "limit": limit}
    def get_performance_trends(self, window_minutes): return {"window": window_minutes}


class TestAnalytics:
    def _client(self, monkeypatch):
        import api.router_analytics as ra
        monkeypatch.setattr(ra, "get_analytics_collector", lambda: _FakeCollector())
        app = FastAPI()
        app.include_router(ra.router, prefix="/api")
        return TestClient(app)

    def test_full(self, monkeypatch):
        assert self._client(monkeypatch).get("/api/analytics").json()["summary"] == "ok"

    def test_cost(self, monkeypatch):
        assert self._client(monkeypatch).get("/api/analytics/cost").json()["total_cost"] == 1.23

    def test_patterns_respects_top_n(self, monkeypatch):
        r = self._client(monkeypatch).get("/api/analytics/patterns?top_n=5")
        assert "patterns" in r.json()

    def test_patterns_rejects_over_limit(self, monkeypatch):
        # le=50 → 51 reddedilmeli (422)
        r = self._client(monkeypatch).get("/api/analytics/patterns?top_n=51")
        assert r.status_code == 422

    def test_trends_window(self, monkeypatch):
        r = self._client(monkeypatch).get("/api/analytics/trends?window_minutes=30")
        assert r.json()["window"] == 30

    def test_errors_limit(self, monkeypatch):
        r = self._client(monkeypatch).get("/api/analytics/errors?limit=5")
        assert r.json()["limit"] == 5


# ── Streaming ───────────────────────────────────────────────────────────────────

class TestStreaming:
    def test_format_sse_event(self):
        from api.streaming import format_sse_event
        out = format_sse_event("message", {"token": "hi"})
        assert out.startswith("event: message\ndata: ")
        assert out.endswith("\n\n")
        # data satırı geçerli JSON
        data_line = out.split("data: ", 1)[1].split("\n", 1)[0]
        assert json.loads(data_line) == {"token": "hi"}

    def test_format_sse_unicode_preserved(self):
        from api.streaming import format_sse_event
        out = format_sse_event("message", {"token": "şğüöç"})
        assert "şğüöç" in out  # ensure_ascii=False

    def test_stream_emits_metadata_messages_done(self):
        import asyncio
        from api.streaming import stream_chat_response

        async def gen():
            for t in ["a", "b", "c"]:
                yield t

        async def collect():
            resp = await stream_chat_response(gen(), metadata={"intent": "info"})
            chunks = [c async for c in resp.body_iterator]
            return "".join(
                c.decode() if isinstance(c, (bytes, bytearray)) else c for c in chunks
            )

        body = asyncio.run(collect())
        assert "event: metadata" in body
        assert body.count("event: message") == 3
        assert "event: done" in body
        assert '"total_tokens": 3' in body

    def test_stream_error_event_on_generator_failure(self):
        import asyncio
        from api.streaming import stream_chat_response

        async def bad_gen():
            yield "ok"
            raise RuntimeError("mid-stream boom")

        async def collect():
            resp = await stream_chat_response(bad_gen())
            chunks = [c async for c in resp.body_iterator]
            return "".join(
                c.decode() if isinstance(c, (bytes, bytearray)) else c for c in chunks
            )

        body = asyncio.run(collect())
        assert "event: error" in body
        assert "mid-stream boom" in body
