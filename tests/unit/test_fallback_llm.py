"""
Unit tests for the provider fallback chain (FallbackLLM + get_llm_clients).

The proposal promised a Groq->OpenAI->Ollama failover that did not exist:
get_llm_clients() picked exactly one provider and raised on failure. These
tests cover the new lazy, fail-through wrapper. Provider builders are faked —
no network, no real keys.
"""

from __future__ import annotations

import pytest

import llm.clients as clients
from llm.clients import FallbackLLM, get_llm_clients


def _provider(name, *, small_ret=None, large_ret=None, build_error=None, call_error=None):
    """Return a builder() that yields (small, large) callables, or raises on build."""
    def builder():
        if build_error:
            raise build_error
        def small(_p):
            if call_error:
                raise call_error
            return small_ret if small_ret is not None else f"{name}-small"
        def large(_p):
            if call_error:
                raise call_error
            return large_ret if large_ret is not None else f"{name}-large"
        return small, large
    return builder


class TestFallbackLLM:
    def test_uses_primary_when_healthy(self):
        cache = {}
        fb = FallbackLLM("small", ["groq", "openai"], cache)
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(clients, "_PROVIDER_BUILDERS", {
                "groq": _provider("groq"),
                "openai": _provider("openai"),
            })
            assert fb("hi") == "groq-small"

    def test_falls_through_on_call_error(self):
        cache = {}
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(clients, "_PROVIDER_BUILDERS", {
                "groq": _provider("groq", call_error=RuntimeError("429")),
                "openai": _provider("openai"),
            })
            fb = FallbackLLM("large", ["groq", "openai"], cache)
            assert fb("hi") == "openai-large"  # groq 429 -> openai

    def test_small_large_roles_preserved_across_fallback(self):
        """KRİTİK: birincil 429'da bile small küçük modele, large büyük modele gider.

        Karmaşıklık-yönlendirmesi (complex→large) fallback sonrası da geçerli kalmalı:
        yedek sağlayıcıya düşünce zor görev yanlışlıkla küçük modele DÜŞMEZ.
        """
        cache = {}
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(clients, "_PROVIDER_BUILDERS", {
                "groq": _provider("groq", call_error=RuntimeError("rate limit 429")),
                "ollama": _provider("ollama"),
            })
            # small ve large aynı paylaşımlı cache'i kullanır (get_llm_clients gibi)
            small = FallbackLLM("small", ["groq", "ollama"], cache)
            large = FallbackLLM("large", ["groq", "ollama"], cache)
            assert small("hi") == "ollama-small"   # küçük rol korundu
            assert large("hi") == "ollama-large"   # büyük rol korundu (complex görev güvende)

    def test_skips_provider_that_fails_to_build(self):
        """Missing API key (builder raises) -> provider skipped, not fatal."""
        cache = {}
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(clients, "_PROVIDER_BUILDERS", {
                "openai": _provider("openai", build_error=RuntimeError("no key")),
                "groq": _provider("groq"),
            })
            fb = FallbackLLM("small", ["openai", "groq"], cache)
            assert fb("hi") == "groq-small"
            assert cache["openai"] is None  # cached as unavailable

    def test_raises_when_all_providers_fail(self):
        cache = {}
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(clients, "_PROVIDER_BUILDERS", {
                "groq": _provider("groq", call_error=RuntimeError("429")),
                "openai": _provider("openai", call_error=RuntimeError("500")),
            })
            fb = FallbackLLM("small", ["groq", "openai"], cache)
            with pytest.raises(RuntimeError, match="Tüm LLM sağlayıcıları başarısız"):
                fb("hi")

    def test_shared_cache_builds_provider_once(self):
        cache = {}
        calls = {"n": 0}

        def counting_builder():
            calls["n"] += 1
            return (lambda _p: "s", lambda _p: "l")

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(clients, "_PROVIDER_BUILDERS", {"groq": counting_builder})
            small = FallbackLLM("small", ["groq"], cache)
            large = FallbackLLM("large", ["groq"], cache)
            small("x"); large("x"); small("y")
            assert calls["n"] == 1  # built once, shared


class TestGetLLMClients:
    def test_fallback_disabled_returns_primary_only(self, monkeypatch):
        monkeypatch.setattr(clients, "LLM_PROVIDER", "groq")
        monkeypatch.setattr(clients, "_PROVIDER_BUILDERS", {"groq": _provider("groq")})
        small, large = get_llm_clients(enable_fallback=False)
        assert small("x") == "groq-small"
        assert not isinstance(small, FallbackLLM)

    def test_fallback_enabled_returns_wrapper(self, monkeypatch):
        monkeypatch.setattr(clients, "LLM_PROVIDER", "groq")
        monkeypatch.setattr(clients, "_PROVIDER_BUILDERS", {
            "groq": _provider("groq"), "novita": _provider("novita"),
        })
        small, large = get_llm_clients()
        assert isinstance(small, FallbackLLM)
        assert small.providers[0] == "groq"  # primary first

    def test_invalid_provider_raises(self, monkeypatch):
        monkeypatch.setattr(clients, "LLM_PROVIDER", "not_a_provider")
        with pytest.raises(ValueError, match="Desteklenmeyen LLM_PROVIDER"):
            get_llm_clients()


class _Streamable:
    """stream()+__call__ olan sahte istemci (gerçek OpenAICompatibleClient gibi)."""

    def __init__(self, label, tokens=None, stream_error=None):
        self.label = label
        self._tokens = tokens
        self._err = stream_error

    def __call__(self, _p):
        return f"{self.label}-full"

    def stream(self, _p):
        if self._err:
            raise self._err
        for t in (self._tokens if self._tokens is not None else [self.label]):
            yield t


def _streamable_builder(name, tokens=None, stream_error=None):
    def builder():
        return (_Streamable(f"{name}-s", tokens, stream_error),
                _Streamable(f"{name}-l", tokens, stream_error))
    return builder


class TestFallbackStream:
    def test_streams_real_tokens_from_primary(self):
        cache = {}
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(clients, "_PROVIDER_BUILDERS",
                       {"cerebras": _streamable_builder("cb", tokens=["He", "llo"])})
            fb = FallbackLLM("large", ["cerebras"], cache)
            assert list(fb.stream("p")) == ["He", "llo"]

    def test_falls_through_when_primary_stream_errors_upfront(self):
        cache = {}
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(clients, "_PROVIDER_BUILDERS", {
                "cerebras": _streamable_builder("cb", stream_error=RuntimeError("429 rate limit")),
                "sambanova": _streamable_builder("sn", tokens=["ok", "!"]),
            })
            fb = FallbackLLM("large", ["cerebras", "sambanova"], cache)
            assert list(fb.stream("p")) == ["ok", "!"]   # cerebras 429 -> sambanova

    def test_degrades_for_non_streaming_provider(self):
        # Plain callable (no .stream) → tam cevabı tek parça akıt
        cache = {}
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(clients, "_PROVIDER_BUILDERS", {"novita": _provider("novita")})
            fb = FallbackLLM("small", ["novita"], cache)
            assert list(fb.stream("p")) == ["novita-small"]

    def test_raises_when_all_stream_providers_fail(self):
        cache = {}
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(clients, "_PROVIDER_BUILDERS", {
                "cerebras": _streamable_builder("cb", stream_error=RuntimeError("429")),
                "sambanova": _streamable_builder("sn", stream_error=RuntimeError("500")),
            })
            fb = FallbackLLM("large", ["cerebras", "sambanova"], cache)
            with pytest.raises(RuntimeError, match="stream"):
                list(fb.stream("p"))


class TestRoundRobinLoadBalancing:
    """FallbackLLM (provider) + LaneLoadBalancer (provider:model) round-robin dağılımı."""

    def test_fallback_round_robin_distributes_primary(self):
        cache = {}
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(clients, "_PROVIDER_BUILDERS",
                       {"a": _provider("a"), "b": _provider("b"), "c": _provider("c")})
            fb = FallbackLLM("small", ["a", "b", "c"], cache)
            outs = [fb("x") for _ in range(6)]
            # her çağrı farklı birincil ile başlar → yük 3'e bölünür (~2'şer)
            assert fb.stats["by_provider"] == {"a": 2, "b": 2, "c": 2}
            assert outs == ["a-small", "b-small", "c-small", "a-small", "b-small", "c-small"]

    def test_lane_balancer_round_robin(self):
        from llm.clients import LaneLoadBalancer

        def lane(name):
            return lambda p, system=None: f"{name}-out"

        lb = LaneLoadBalancer("small", [("p1:m1", lane("m1")), ("p2:m2", lane("m2")), ("p3:m3", lane("m3"))])
        outs = [lb("x") for _ in range(6)]
        assert lb.stats["by_provider"] == {"p1:m1": 2, "p2:m2": 2, "p3:m3": 2}
        assert outs[0] == "m1-out" and outs[1] == "m2-out" and outs[2] == "m3-out"

    def test_lane_balancer_falls_through_on_error(self):
        from llm.clients import LaneLoadBalancer

        def bad(p, system=None):
            raise RuntimeError("429 rate limit")

        def good(p, system=None):
            return "good-out"

        lb = LaneLoadBalancer("large", [("bad:x", bad), ("good:y", good)])
        # call1 start0 → bad 429 → good; call2 start1 → good direkt → her hâlükârda good
        assert lb("p") == "good-out"
        assert lb("p") == "good-out"
        assert lb.stats["by_provider"].get("good:y") == 2

    def test_lane_balancer_raises_when_all_fail(self):
        from llm.clients import LaneLoadBalancer

        def bad(p, system=None):
            raise RuntimeError("429")

        lb = LaneLoadBalancer("small", [("p1:m", bad), ("p2:m", bad)])
        with pytest.raises(RuntimeError, match="Tüm LLM lane"):
            lb("p")

    def test_lane_stats_track_latency_and_failures(self):
        from llm.clients import LaneLoadBalancer

        def good(p, system=None):
            return "ok"

        def bad(p, system=None):
            raise RuntimeError("429 rate limit")

        lb = LaneLoadBalancer("small", [("ok:m", good), ("bad:m", bad)])
        lb("x"); lb("y")   # call2 start1 → bad fail (fallback) → good
        s = lb.get_stats()
        assert "ok:m" in s["avg_latency_ms_by_provider"]        # ort. gecikme kaydedildi
        assert s["failures_by_provider"].get("bad:m", 0) >= 1   # ölü lane fail sayısı kaydedildi
