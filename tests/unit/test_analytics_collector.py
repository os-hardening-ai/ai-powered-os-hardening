"""
Unit tests for llm.utils.analytics_collector.AdvancedAnalyticsCollector.

Pure in-memory aggregation logic — no LLM, no network.
"""

from __future__ import annotations

from llm.utils.analytics_collector import (
    AdvancedAnalyticsCollector,
    QueryAnalytics,
    get_analytics_collector,
)


def _record(c, **kw):
    base = dict(
        query="Ubuntu SSH hardening nasıl yapılır",
        intent_type="info_request",
        safety_category="safe_defensive",
        layer_path="1→2→3B",
        complexity="medium",
        rag_used=True,
        rag_chunks=3,
        model_used="large",
        response_time_s=2.0,
        estimated_cost=0.0005,
        success=True,
    )
    base.update(kw)
    c.record_query(**base)


class TestRecording:
    def test_record_updates_stats(self):
        c = AdvancedAnalyticsCollector()
        _record(c)
        assert c.stats["total_queries"] == 1
        assert c.stats["rag_usage_count"] == 1
        assert c.stats["intent_breakdown"]["info_request"] == 1

    def test_error_increments_error_count(self):
        c = AdvancedAnalyticsCollector()
        _record(c, success=False, error_msg="TimeoutError: too slow")
        assert c.stats["error_count"] == 1

    def test_query_truncated_to_200(self):
        c = AdvancedAnalyticsCollector()
        _record(c, query="x" * 500)
        assert len(c.queries[0].query) == 200


class TestAggregations:
    def setup_method(self):
        self.c = AdvancedAnalyticsCollector()
        _record(self.c, intent_type="info_request", estimated_cost=0.0005, rag_used=True)
        _record(self.c, intent_type="action_request", estimated_cost=0.0025, rag_used=False, rag_chunks=0)
        _record(self.c, intent_type="info_request", success=False, error_msg="ValueError: bad")

    def test_cost_breakdown(self):
        cb = self.c.get_cost_breakdown()
        assert cb["total_cost"] > 0
        assert "info_request" in cb["by_intent"]
        assert cb["avg_cost_per_query"] > 0

    def test_rag_effectiveness(self):
        rag = self.c.get_rag_effectiveness()
        assert 0.0 < rag["rag_usage_rate"] <= 1.0
        assert rag["avg_chunks_per_query"] >= 0

    def test_performance_trends(self):
        t = self.c.get_performance_trends(window_minutes=60)
        assert t["query_count"] == 3
        assert t["avg_latency_ms"] > 0

    def test_error_analysis(self):
        e = self.c.get_error_analysis()
        assert e["total_errors"] == 1
        assert e["error_rate"] > 0
        assert len(e["recent_errors"]) == 1

    def test_query_patterns(self):
        pats = self.c.get_query_patterns(top_n=5)
        assert isinstance(pats, list)
        assert all("pattern" in p and "count" in p for p in pats)

    def test_full_analytics_report(self):
        report = self.c.get_full_analytics()
        assert report["overview"]["total_queries"] == 3
        assert "cost_analysis" in report
        assert "rag_effectiveness" in report
        assert "error_analysis" in report


class TestEmptyState:
    def test_empty_rag_effectiveness(self):
        c = AdvancedAnalyticsCollector()
        assert c.get_rag_effectiveness()["rag_usage_rate"] == 0.0

    def test_empty_trends(self):
        c = AdvancedAnalyticsCollector()
        assert c.get_performance_trends()["query_count"] == 0

    def test_empty_error_analysis(self):
        c = AdvancedAnalyticsCollector()
        assert c.get_error_analysis()["total_errors"] == 0


class TestSingleton:
    def test_global_instance_is_stable(self):
        a = get_analytics_collector()
        b = get_analytics_collector()
        assert a is b
