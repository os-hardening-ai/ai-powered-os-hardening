"""
Unit tests for LLM client reliability config — timeout + retry wiring.

429/5xx best-practice: the Groq/OpenAI SDKs perform exponential backoff and
honor the `Retry-After` header when `max_retries` is set, and `timeout` bounds
a hung socket. These tests assert our clients actually pass those values to the
SDK constructors (previously they did not, so requests could hang and a single
429 burst failed hard). The SDK objects are faked — no network.
"""

from __future__ import annotations

import pytest

import llm.clients.groq_client as gc
import llm.clients.openai_client as oc


class _FakeSDK:
    """Captures constructor kwargs so we can assert timeout/max_retries wiring."""
    last_kwargs: dict = {}

    def __init__(self, **kwargs):
        type(self).last_kwargs = kwargs


class TestGroqReliability:
    def test_timeout_and_retries_passed_to_sdk(self, monkeypatch):
        monkeypatch.setattr(gc, "Groq", _FakeSDK)
        client = gc.GroqClient(
            model_name="llama-x", api_key="key", timeout=42.0, max_retries=7
        )
        assert client.timeout == 42.0
        assert client.max_retries == 7
        assert _FakeSDK.last_kwargs["timeout"] == 42.0
        assert _FakeSDK.last_kwargs["max_retries"] == 7

    def test_defaults_come_from_config(self, monkeypatch):
        monkeypatch.setattr(gc, "Groq", _FakeSDK)
        client = gc.GroqClient(model_name="llama-x", api_key="key")
        # config-driven defaults (REQUEST_TIMEOUT / MAX_RETRIES) — not hard 0/None
        assert client.timeout >= 10  # config validates request_timeout >= 10
        assert client.max_retries >= 1
        assert _FakeSDK.last_kwargs["timeout"] == client.timeout
        assert _FakeSDK.last_kwargs["max_retries"] == client.max_retries

    def test_missing_api_key_raises(self):
        with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
            gc.GroqClient(model_name="x", api_key="")


class TestOpenAIReliability:
    def test_timeout_and_retries_passed_to_sdk(self, monkeypatch):
        monkeypatch.setattr(oc, "OPENAI_API_KEY", "key")
        monkeypatch.setattr(oc, "NEW_API_AVAILABLE", True)
        monkeypatch.setattr(oc, "OpenAI", _FakeSDK)
        client = oc.OpenAIClient(model_name="gpt-x", timeout=33.0, max_retries=5)
        assert client.timeout == 33.0
        assert client.max_retries == 5
        assert _FakeSDK.last_kwargs["timeout"] == 33.0
        assert _FakeSDK.last_kwargs["max_retries"] == 5

    def test_defaults_come_from_config(self, monkeypatch):
        monkeypatch.setattr(oc, "OPENAI_API_KEY", "key")
        monkeypatch.setattr(oc, "NEW_API_AVAILABLE", True)
        monkeypatch.setattr(oc, "OpenAI", _FakeSDK)
        client = oc.OpenAIClient(model_name="gpt-x")
        assert client.timeout >= 10
        assert client.max_retries >= 1
