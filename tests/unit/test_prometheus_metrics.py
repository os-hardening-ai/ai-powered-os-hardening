"""
Unit tests for prometheus_metrics: optional-dependency graceful degradation + record helpers.

`prometheus_fastapi_instrumentator` is OPTIONAL (auto HTTP instrumentation). When it is
absent the app must STILL import and the custom metrics must STILL work — importing it at
module top previously hard-crashed the whole app (and the eval harness), so the
graceful-skip behaviour is locked down here.
"""

from __future__ import annotations

import sys

import prometheus_metrics as pm


class TestSetupMetricsGraceful:
    def test_no_raise_when_instrumentator_missing(self, monkeypatch):
        # Force the optional import to fail (sys.modules[...] = None ⇒ ImportError on import)
        monkeypatch.setitem(sys.modules, "prometheus_fastapi_instrumentator", None)
        from fastapi import FastAPI
        assert pm.setup_metrics(FastAPI()) is None   # graceful skip, no exception

    def test_no_raise_in_current_env(self):
        # In this env the package is genuinely absent → exercises the real degradation path.
        from fastapi import FastAPI
        assert pm.setup_metrics(FastAPI()) is None


class TestSetupTracingDisabled:
    def test_returns_early_when_disabled(self, monkeypatch):
        monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
        from fastapi import FastAPI
        # Must return before importing/contacting any OTLP collector.
        assert pm.setup_tracing(FastAPI()) is None

    def test_disabled_accepts_truthy_variants(self, monkeypatch):
        from fastapi import FastAPI
        for val in ("1", "TRUE", "yes"):
            monkeypatch.setenv("OTEL_SDK_DISABLED", val)
            assert pm.setup_tracing(FastAPI()) is None


class TestRecordHelpers:
    """Custom metrics use prometheus_client (installed) — must work regardless of instrumentator."""

    def test_record_query_with_tokens(self):
        pm.record_query(status="answered", intent="os_hardening", complexity="simple",
                        model="m", rag_used=True, input_tokens=10, output_tokens=20)

    def test_record_query_no_tokens(self):
        pm.record_query(status="rejected")          # zero tokens ⇒ token counter untouched

    def test_record_safety_check(self):
        pm.record_safety_check(category="injection", outcome="blocked")

    def test_record_rejection(self):
        pm.record_rejection(layer="1")

    def test_record_rag_retrieval(self):
        pm.record_rag_retrieval(duration_s=0.4, results_count=5, top_score=0.87)

    def test_record_rag_retrieval_zero_score_skips_similarity(self):
        pm.record_rag_retrieval(duration_s=0.1, results_count=0, top_score=0.0)

    def test_layer_timer_context_manager(self):
        with pm.layer_timer("1"):
            pass   # observes a duration sample without error
