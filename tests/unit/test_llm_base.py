"""Unit tests for llm.clients.base — hata taksonomisi + sınıflandırma."""

from __future__ import annotations

import pytest

from llm.clients.base import (
    LLMProvider,
    LLMProviderError,
    RateLimitError,
    AuthError,
    TimeoutError_,
    ModelUnavailableError,
    classify_error,
)


class TestProtocol:
    def test_callable_satisfies_protocol(self):
        def client(prompt: str) -> str:
            return "ok"
        assert isinstance(client, LLMProvider)

    def test_non_callable_fails_protocol(self):
        assert not isinstance(42, LLMProvider)


class TestClassify:
    @pytest.mark.parametrize("text,kind", [
        ("Error 429 too many requests", RateLimitError),
        ("rate_limit exceeded", RateLimitError),
        ("monthly quota reached", RateLimitError),
        ("401 Unauthorized", AuthError),
        ("invalid api key provided", AuthError),
        ("request timed out", TimeoutError_),
        ("connection refused", TimeoutError_),
        ("model not found", ModelUnavailableError),
        ("model_not_supported on free tier", ModelUnavailableError),
        ("something totally weird", LLMProviderError),
    ])
    def test_classification(self, text, kind):
        err = classify_error(RuntimeError(text), provider="groq")
        assert isinstance(err, kind)
        assert err.provider == "groq"
        assert err.should_fallback is True

    def test_already_classified_passthrough(self):
        original = RateLimitError("x", "novita")
        assert classify_error(original, "groq") is original  # çift sarmalama yok

    def test_cause_preserved(self):
        cause = ValueError("root")
        err = classify_error(cause, "ollama")
        assert err.original_error is cause
