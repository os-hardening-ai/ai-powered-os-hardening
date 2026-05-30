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
