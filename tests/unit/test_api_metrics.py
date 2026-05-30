"""
Unit tests for api.metrics — MetricsCollector aggregation + MetricsMiddleware.

Saf in-memory mantık; network yok. Latency yüzdelikleri, hata oranı, provider
kırılımı, zaman-penceresi filtresi ve middleware'in durum kodu/süre kaydı.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.metrics import (
    MetricsCollector,
    RequestMetrics,
    AggregatedMetrics,
    MetricsMiddleware,
    format_metrics_summary,
)


def _m(status=200, dur=10.0, ts=None, provider=None, model=None, tokens=0, error=None):
    return RequestMetrics(
        timestamp=ts or datetime.now(),
        endpoint="/api/chat", method="POST",
        status_code=status, duration_ms=dur,
        llm_provider=provider, llm_model=model, tokens_used=tokens, error=error,
    )


class TestAggregation:
    def test_empty_returns_zero(self):
        c = MetricsCollector()
        agg = c.get_aggregated_metrics()
        assert isinstance(agg, AggregatedMetrics)
        assert agg.total_requests == 0 and agg.error_rate == 0.0

    def test_success_and_error_rate(self):
        c = MetricsCollector()
        for _ in range(3):
            c.record(_m(status=200))
        c.record(_m(status=500, error="boom"))
        agg = c.get_aggregated_metrics()
        assert agg.total_requests == 4
        assert agg.successful_requests == 3
        assert agg.failed_requests == 1
        assert agg.error_rate == pytest.approx(0.25)

    def test_latency_percentiles(self):
        c = MetricsCollector()
        for d in [10, 20, 30, 40, 100]:
            c.record(_m(dur=float(d)))
        agg = c.get_aggregated_metrics()
        assert agg.min_latency_ms == 10.0
        assert agg.max_latency_ms == 100.0
        assert agg.p50_latency_ms in (30.0, 40.0)  # index-based percentile
        assert agg.p95_latency_ms == 100.0

    def test_provider_and_model_breakdown(self):
        c = MetricsCollector()
        c.record(_m(provider="groq", model="llama-8b", tokens=100))
        c.record(_m(provider="groq", model="llama-70b", tokens=50))
        c.record(_m(provider="novita", model="ds-v3", tokens=20))
        agg = c.get_aggregated_metrics()
        assert agg.provider_stats == {"groq": 2, "novita": 1}
        assert agg.total_tokens == 170
        assert agg.model_stats["llama-8b"] == 1

    def test_time_window_filter(self):
        c = MetricsCollector()
        old = datetime.now() - timedelta(minutes=120)
        c.record(_m(ts=old))          # eski → pencere dışı
        c.record(_m())                # yeni → içeride
        agg = c.get_aggregated_metrics(time_window_minutes=60)
        assert agg.total_requests == 1

    def test_endpoint_filter(self):
        c = MetricsCollector()
        c.record(_m())  # /api/chat
        other = RequestMetrics(timestamp=datetime.now(), endpoint="/rag/search",
                               method="POST", status_code=200, duration_ms=5.0)
        c.record(other)
        assert c.get_aggregated_metrics(endpoint="/rag/search").total_requests == 1
        assert c.get_aggregated_metrics(endpoint="/api/chat").total_requests == 1


class TestRecentAndSlowest:
    def test_recent_errors(self):
        c = MetricsCollector()
        c.record(_m(status=200))
        c.record(_m(status=500, error="e1"))
        c.record(_m(status=503, error="e2"))
        errs = c.get_recent_errors(limit=10)
        assert len(errs) == 2
        assert errs[0].error == "e2"  # en yeni önce

    def test_slowest_requests(self):
        c = MetricsCollector()
        for d in [10, 500, 50]:
            c.record(_m(dur=float(d)))
        slow = c.get_slowest_requests(limit=2)
        assert [s.duration_ms for s in slow] == [500.0, 50.0]


class TestCleanup:
    def test_old_metrics_evicted(self):
        c = MetricsCollector(max_history_hours=1)
        c.record(_m(ts=datetime.now() - timedelta(hours=2)))  # eski → temizlenir
        c.record(_m())                                         # yeni
        assert len(c.metrics) == 1


class TestMiddleware:
    def test_records_status_and_duration(self):
        c = MetricsCollector()
        app = FastAPI()
        app.add_middleware(MetricsMiddleware, collector=c)

        @app.get("/ping")
        def ping():
            return {"ok": True}

        client = TestClient(app)
        assert client.get("/ping").status_code == 200
        assert len(c.metrics) == 1
        rec = c.metrics[0]
        assert rec.endpoint == "/ping" and rec.status_code == 200
        assert rec.duration_ms >= 0


class TestFormatSummary:
    def test_summary_renders(self):
        agg = AggregatedMetrics(total_requests=10, successful_requests=9,
                                failed_requests=1, error_rate=0.1, avg_latency_ms=12.3)
        s = format_metrics_summary(agg)
        assert "Total Requests:" in s and "10" in s
