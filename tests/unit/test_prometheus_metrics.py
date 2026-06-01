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


# ── Registry'den GERÇEK DEĞER okuyarak toplama doğrulaması ──────────────────────
from prometheus_client import REGISTRY


def _sample(name: str, labels: dict | None = None) -> float:
    """Registry'den bir metrik örneğinin güncel değerini al (yoksa 0.0)."""
    val = REGISTRY.get_sample_value(name, labels or {})
    return float(val) if val is not None else 0.0


class TestQueryOutcomeCollected:
    """record_query_outcome histogram/counter'ları GERÇEKTEN artırıyor mu?"""

    def test_latency_observed(self):
        before = _sample("hardening_query_duration_seconds_count", {"intent": "info_request"})
        pm.record_query_outcome(intent="info_request", total_time_s=1.5)
        assert _sample("hardening_query_duration_seconds_count", {"intent": "info_request"}) == before + 1

    def test_cost_accumulates(self):
        before = _sample("hardening_query_estimated_cost_usd_total", {"intent": "action_request"})
        pm.record_query_outcome(intent="action_request", estimated_cost=0.0025)
        after = _sample("hardening_query_estimated_cost_usd_total", {"intent": "action_request"})
        assert after == __import__("pytest").approx(before + 0.0025)

    def test_zero_cost_not_recorded(self):
        before = _sample("hardening_query_estimated_cost_usd_total", {"intent": "smalltalk"})
        pm.record_query_outcome(intent="smalltalk", estimated_cost=0.0)
        assert _sample("hardening_query_estimated_cost_usd_total", {"intent": "smalltalk"}) == before

    def test_verification_confidence_observed(self):
        before = _sample("hardening_rag_verification_confidence_count")
        pm.record_query_outcome(intent="info_request", verification_confidence=0.82)
        assert _sample("hardening_rag_verification_confidence_count") == before + 1

    def test_none_confidence_not_observed(self):
        before = _sample("hardening_rag_verification_confidence_count")
        pm.record_query_outcome(intent="info_request", verification_confidence=None)
        assert _sample("hardening_rag_verification_confidence_count") == before


class TestLLMProviderMetricsCollected:
    def test_primary_call_no_fallback(self):
        before = _sample("hardening_llm_provider_calls_total", {"role": "small", "provider": "cerebras"})
        fb_before = _sample("hardening_llm_fallback_total", {"role": "small"})
        pm.record_llm_provider_call("small", "cerebras", was_fallback=False)
        assert _sample("hardening_llm_provider_calls_total", {"role": "small", "provider": "cerebras"}) == before + 1
        assert _sample("hardening_llm_fallback_total", {"role": "small"}) == fb_before

    def test_fallback_increments_both(self):
        c_before = _sample("hardening_llm_provider_calls_total", {"role": "large", "provider": "gemini"})
        fb_before = _sample("hardening_llm_fallback_total", {"role": "large"})
        pm.record_llm_provider_call("large", "gemini", was_fallback=True)
        assert _sample("hardening_llm_provider_calls_total", {"role": "large", "provider": "gemini"}) == c_before + 1
        assert _sample("hardening_llm_fallback_total", {"role": "large"}) == fb_before + 1

    def test_chain_failure(self):
        before = _sample("hardening_llm_chain_failure_total", {"role": "small"})
        pm.record_llm_chain_failure("small")
        assert _sample("hardening_llm_chain_failure_total", {"role": "small"}) == before + 1


class TestFallbackLLMFeedsMetrics:
    """FallbackLLM gerçek akışı metrik besliyor mu? Sahte sağlayıcılarla, ağsız."""

    def _make(self, role, providers, builders):
        import llm.clients as mod
        mod._PROVIDER_BUILDERS = builders  # type: ignore[attr-defined]
        return mod.FallbackLLM(role=role, providers=providers, cache={})

    def test_primary_served_records_metric(self):
        ok = lambda _p, **_k: "cevap"
        llm = self._make("small", ["p1"], {"p1": lambda: (ok, ok)})
        before = _sample("hardening_llm_provider_calls_total", {"role": "small", "provider": "p1"})
        assert llm("soru") == "cevap"
        assert _sample("hardening_llm_provider_calls_total", {"role": "small", "provider": "p1"}) == before + 1

    def test_fallback_path_records_fallback(self):
        def boom(_p, **_k): raise RuntimeError("down")
        ok = lambda _p, **_k: "kurtarıldı"
        llm = self._make("small", ["pf1", "pf2"], {"pf1": lambda: (boom, boom), "pf2": lambda: (ok, ok)})
        c_before = _sample("hardening_llm_provider_calls_total", {"role": "small", "provider": "pf2"})
        fb_before = _sample("hardening_llm_fallback_total", {"role": "small"})
        assert llm("soru") == "kurtarıldı"
        assert _sample("hardening_llm_provider_calls_total", {"role": "small", "provider": "pf2"}) == c_before + 1
        assert _sample("hardening_llm_fallback_total", {"role": "small"}) == fb_before + 1

    def test_total_chain_failure_records_metric(self):
        import pytest as _pt
        def boom(_p, **_k): raise RuntimeError("down")
        llm = self._make("large", ["px1", "px2"], {"px1": lambda: (boom, boom), "px2": lambda: (boom, boom)})
        before = _sample("hardening_llm_chain_failure_total", {"role": "large"})
        with _pt.raises(RuntimeError):
            llm("soru")
        assert _sample("hardening_llm_chain_failure_total", {"role": "large"}) == before + 1


class TestMetricsExportable:
    def test_new_metrics_in_exposition(self):
        from prometheus_client import generate_latest
        pm.record_query_outcome(intent="info_request", total_time_s=0.5,
                                estimated_cost=0.001, verification_confidence=0.7)
        pm.record_llm_provider_call("small", "cerebras", was_fallback=False)
        text = generate_latest().decode("utf-8")
        for name in [
            "hardening_query_duration_seconds",
            "hardening_query_estimated_cost_usd_total",
            "hardening_rag_verification_confidence",
            "hardening_llm_provider_calls_total",
            "hardening_llm_fallback_total",
            "hardening_llm_chain_failure_total",
        ]:
            assert name in text, f"{name} /metrics çıktısında yok"
