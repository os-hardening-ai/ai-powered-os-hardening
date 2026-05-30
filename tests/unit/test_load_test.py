"""
Unit tests for evaluation.load_test pure/deterministic parts (no LLM, no real HTTP).

The live H3 measurement needs a running app + real LLM, but the request-aggregation,
percentile delegation, global rate limiter, provider-info capture and report rendering
are pure logic — that is the trusted part, so it is unit-tested here (mirrors
test_ip_metrics / test_h1_harness). Fake clients stand in for the FastAPI TestClient.
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest

import evaluation.load_test as lt


# ── Test doubles ─────────────────────────────────────────────────────────────────

class _FakeClient:
    """Stands in for fastapi.testclient.TestClient — returns a fixed status fast."""

    def __init__(self, status: int = 200, delay: float = 0.0) -> None:
        self.status = status
        self.delay = delay
        self.calls = 0

    def request(self, method, path, json=None):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        return SimpleNamespace(status_code=self.status)


class _BoomClient:
    def request(self, *a, **k):
        raise RuntimeError("connection refused")


def _spec() -> "lt.EndpointSpec":
    return lt.EndpointSpec("agent_plan", "POST", "/api/agent/plan", {"goal": "x"})


def _fresh_state() -> dict:
    return {"lock": threading.Lock(), "last": 0.0}


# ── _percentile (delegates to api.metrics, single source of truth) ────────────────

class TestPercentile:
    def test_delegates_to_metrics_collector(self):
        from api.metrics import MetricsCollector
        data = [0.1, 0.2, 0.3, 0.4, 0.5]
        for q in (0.5, 0.95, 0.99):
            assert lt._percentile(data, q) == round(
                MetricsCollector._percentile(sorted(data), q), 3)

    def test_sorts_input(self):
        assert lt._percentile([0.5, 0.1, 0.3], 0.5) == lt._percentile([0.1, 0.3, 0.5], 0.5)

    def test_rounds_to_three_dp(self):
        val = lt._percentile([0.123456, 0.2, 0.3], 0.5)
        assert val == round(val, 3)


# ── _rate_limit (global request-rate cap; prevents 429 backoff storms) ────────────

class TestRateLimit:
    def test_noop_when_zero(self):
        st = _fresh_state()
        t0 = time.monotonic()
        lt._rate_limit(0.0, st)
        assert time.monotonic() - t0 < 0.05

    def test_negative_is_noop(self):
        st = _fresh_state()
        t0 = time.monotonic()
        lt._rate_limit(-1.0, st)
        assert time.monotonic() - t0 < 0.05

    def test_spaces_consecutive_starts(self):
        st = _fresh_state()
        lt._rate_limit(0.1, st)          # first call sets `last` ~ now
        t0 = time.monotonic()
        lt._rate_limit(0.1, st)          # immediate second → must wait ~0.1s
        assert time.monotonic() - t0 >= 0.08

    def test_no_wait_when_interval_already_elapsed(self):
        st = {"lock": threading.Lock(), "last": time.monotonic() - 10.0}
        t0 = time.monotonic()
        lt._rate_limit(0.1, st)          # last was 10s ago → no wait
        assert time.monotonic() - t0 < 0.05

    def test_updates_last_timestamp(self):
        st = _fresh_state()
        lt._rate_limit(0.01, st)
        assert st["last"] > 0.0


# ── _model_name_of (defensive model-name extraction for self-documenting report) ──

class TestModelNameOf:
    def test_direct_attribute(self):
        assert lt._model_name_of(SimpleNamespace(model_name="llama-3.1-8b")) == "llama-3.1-8b"

    def test_wrapped_in_primary(self):
        inner = SimpleNamespace(model_name="deepseek-v3")
        assert lt._model_name_of(SimpleNamespace(_primary=inner)) == "deepseek-v3"

    def test_wrapped_in_client(self):
        inner = SimpleNamespace(model_name="gpt-x")
        assert lt._model_name_of(SimpleNamespace(client=inner)) == "gpt-x"

    def test_unknown_returns_questionmark(self):
        assert lt._model_name_of(object()) == "?"

    def test_callable_without_model_name(self):
        assert lt._model_name_of(lambda p: p) == "?"


# ── _provider_info (records provider/models actually used — the missing piece) ────

class TestProviderInfo:
    def test_provider_and_fallback_from_env(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "novita")
        monkeypatch.setenv("LLM_INCLUDE_CHEAP", "1")
        import llm.clients as _c
        monkeypatch.setattr(
            _c, "get_llm_clients",
            lambda **k: (SimpleNamespace(model_name="s"), SimpleNamespace(model_name="l")))
        info = lt._provider_info()
        assert info["provider"] == "novita"
        assert info["fallback_cheap"] == "on"
        assert info["small_model"] == "s"
        assert info["large_model"] == "l"

    def test_default_provider_is_groq(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("LLM_INCLUDE_CHEAP", raising=False)
        import llm.clients as _c
        monkeypatch.setattr(_c, "get_llm_clients",
                            lambda **k: (SimpleNamespace(model_name="a"), SimpleNamespace(model_name="b")))
        info = lt._provider_info()
        assert info["provider"] == "groq"
        assert info["fallback_cheap"] == "off"

    def test_defensive_on_client_build_failure(self, monkeypatch):
        """Sağlayıcı bilgisi alınamasa bile ölçüm engellenmemeli — model '?' kalır."""
        monkeypatch.setenv("LLM_PROVIDER", "groq")

        def _raise(**k):
            raise RuntimeError("no api key")

        import llm.clients as _c
        monkeypatch.setattr(_c, "get_llm_clients", _raise)
        info = lt._provider_info()
        assert info["provider"] == "groq"
        assert info["small_model"] == "?"
        assert info["large_model"] == "?"


# ── run_endpoint (request fan-out + aggregation) ──────────────────────────────────

class TestRunEndpoint:
    def test_all_ok_passes_h3(self):
        res = lt.run_endpoint(_FakeClient(200), _spec(), n=6, concurrency=2)
        assert res.n == 6 and res.ok == 6 and res.errors == 0
        assert res.passed_h3 is True            # fast + ok
        assert len(res.durations_s) == 6

    def test_http_errors_fail_h3(self):
        res = lt.run_endpoint(_FakeClient(500), _spec(), n=4, concurrency=2)
        assert res.ok == 0 and res.errors == 4
        assert res.passed_h3 is False           # ok == 0 ⇒ fail regardless of latency

    def test_exception_counts_as_error(self):
        res = lt.run_endpoint(_BoomClient(), _spec(), n=3, concurrency=1)
        assert res.ok == 0 and res.errors == 3
        assert res.passed_h3 is False

    def test_p95_over_target_fails_even_if_ok(self, monkeypatch):
        # Negatif hedef ⇒ herhangi bir gerçek p95 (≥0) eşiği aşar ⇒ deterministik fail
        # (Windows sleep granülaritesine bağlı kalmadan threshold mantığını test eder).
        monkeypatch.setattr(lt, "_P95_TARGET_S", -1.0)
        res = lt.run_endpoint(_FakeClient(200), _spec(), n=4, concurrency=1)
        assert res.ok == 4
        assert res.passed_h3 is False

    def test_percentiles_are_ordered(self):
        res = lt.run_endpoint(_FakeClient(200), _spec(), n=8, concurrency=2)
        assert res.p50_s <= res.p95_s <= res.p99_s <= res.max_s + 1e-9

    def test_throttle_accepted_and_spaces_requests(self):
        # n=3, concurrency=1, throttle 0.05s ⇒ ≥2 gaps ⇒ ≥~0.1s wall time
        t0 = time.monotonic()
        lt._rate_state["last"] = 0.0   # reset global state used by default
        res = lt.run_endpoint(_FakeClient(200), _spec(), n=3, concurrency=1, throttle_s=0.05)
        assert res.ok == 3
        assert time.monotonic() - t0 >= 0.08


# ── Report rendering / summary ────────────────────────────────────────────────────

def _sample_result(passed=True) -> "lt.EndpointResult":
    return lt.EndpointResult(
        name="agent_plan", n=5, ok=5, errors=0,
        p50_s=0.5, p95_s=1.2, p99_s=1.5, avg_s=0.6, max_s=1.5,
        passed_h3=passed, durations_s=[0.5, 0.6, 0.5, 0.7, 1.2])


class TestSummary:
    def test_includes_provider_block(self):
        rep = lt.LoadReport(concurrency=3, provider_info={"provider": "novita"})
        s = rep.summary()
        assert s["provider"]["provider"] == "novita"
        assert s["concurrency"] == 3
        assert s["p95_target_s"] == 5.0
        assert "endpoints" in s

    def test_endpoints_serialized(self):
        rep = lt.LoadReport(concurrency=2, provider_info={"provider": "groq"},
                            results=[_sample_result()])
        s = rep.summary()
        assert "agent_plan" in s["endpoints"]
        assert s["endpoints"]["agent_plan"]["passed_h3"] is True


class TestToMarkdown:
    def test_includes_provider_line(self):
        rep = lt.LoadReport(
            concurrency=2,
            provider_info={"provider": "groq", "small_model": "llama-8b",
                           "large_model": "llama-70b", "fallback_cheap": "off"},
            results=[_sample_result()])
        md = lt.to_markdown(rep)
        assert "groq" in md
        assert "llama-8b" in md and "llama-70b" in md

    def test_includes_endpoint_row_and_verdict(self):
        rep = lt.LoadReport(concurrency=2, provider_info={"provider": "groq"},
                            results=[_sample_result(passed=True)])
        md = lt.to_markdown(rep)
        assert "agent_plan" in md
        assert "✅" in md
        assert "H3" in md

    def test_fail_verdict_renders(self):
        rep = lt.LoadReport(concurrency=2, provider_info={"provider": "novita"},
                            results=[_sample_result(passed=False)])
        md = lt.to_markdown(rep)
        assert "❌" in md

    def test_missing_provider_info_does_not_crash(self):
        rep = lt.LoadReport(concurrency=1, results=[_sample_result()])
        md = lt.to_markdown(rep)   # provider_info defaults to {}
        assert "?" in md           # falls back to '?' placeholders
