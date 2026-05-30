"""
Unit tests for llm.clients.openai_compatible_client (generic OpenAI-compatible LLM client).

No network: the OpenAI SDK client is constructed (lazy, no call) then replaced with a fake.
We test the call success path, empty-content guard, error→taxonomy mapping, presets, and
build_from_preset env overrides.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from llm.clients.openai_compatible_client import (
    OpenAICompatibleClient,
    PROVIDER_PRESETS,
    build_from_preset,
    preset_api_key,
)
from llm.clients.base import AuthError, RateLimitError, TimeoutError_, ModelUnavailableError


def _resp(content, total_tokens=10):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(total_tokens=total_tokens),
    )


class _FakeOpenAI:
    def __init__(self, content=None, exc=None):
        self._content = content
        self._exc = exc
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        if self._exc:
            raise self._exc
        return _resp(self._content)


def _client(content=None, exc=None):
    c = OpenAICompatibleClient(provider="test", model_name="m", api_key="k", base_url="https://x/v1")
    c._client = _FakeOpenAI(content, exc)
    return c


class TestConstruction:
    def test_no_key_raises_auth_error(self):
        with pytest.raises(AuthError):
            OpenAICompatibleClient(provider="p", model_name="m", api_key="", base_url="https://x/v1")

    def test_attributes_stored(self):
        c = _client("ok")
        assert c.provider == "test" and c.model_name == "m" and c.base_url == "https://x/v1"
        assert c.max_tokens > 0 and c.timeout > 0


class TestCall:
    def test_success_strips_content(self):
        assert _client("  hello  ")("prompt") == "hello"

    def test_empty_content_raises_model_unavailable(self):
        with pytest.raises(ModelUnavailableError):
            _client("")("prompt")

    def test_rate_limit_classified(self):
        with pytest.raises(RateLimitError):
            _client(exc=Exception("Rate limit exceeded (429)"))("p")

    def test_auth_classified(self):
        with pytest.raises(AuthError):
            _client(exc=Exception("401 Unauthorized: invalid api key"))("p")

    def test_timeout_classified(self):
        with pytest.raises(TimeoutError_):
            _client(exc=Exception("Connection timed out"))("p")

    def test_model_not_found_classified(self):
        with pytest.raises(ModelUnavailableError):
            _client(exc=Exception("model not found"))("p")


class TestPresets:
    def test_all_presets_well_formed(self):
        assert "cerebras" in PROVIDER_PRESETS and "sambanova" in PROVIDER_PRESETS
        for name, p in PROVIDER_PRESETS.items():
            assert p["base_url"].startswith("http"), name
            assert p["model"], name
            assert p["key_env"].endswith("_API_KEY"), name

    def test_preset_api_key_reads_env(self, monkeypatch):
        monkeypatch.setenv("CEREBRAS_API_KEY", "abc")
        assert preset_api_key("cerebras") == "abc"
        monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
        assert preset_api_key("cerebras") == ""


class TestBuildFromPreset:
    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError):
            build_from_preset("nope")

    def test_missing_key_raises_auth(self, monkeypatch):
        monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
        with pytest.raises(AuthError):
            build_from_preset("cerebras")

    def test_model_and_base_url_override(self, monkeypatch):
        monkeypatch.setenv("CEREBRAS_API_KEY", "k")
        monkeypatch.setenv("CEREBRAS_MODEL", "custom-model")
        monkeypatch.setenv("CEREBRAS_BASE_URL", "https://custom/v1")
        c = build_from_preset("cerebras")
        assert c.model_name == "custom-model"
        assert c.base_url == "https://custom/v1"
        assert c.provider == "cerebras"

    def test_default_model_used_when_no_override(self, monkeypatch):
        monkeypatch.setenv("SAMBANOVA_API_KEY", "k")
        monkeypatch.delenv("SAMBANOVA_MODEL", raising=False)
        c = build_from_preset("sambanova")
        assert c.model_name == PROVIDER_PRESETS["sambanova"]["model"]
