"""Unit tests for HuggingFaceClient — ücretsiz tier, taksonomi entegrasyonu (mock'lu)."""

from __future__ import annotations

import sys
import types

import pytest

import llm.clients.huggingface_client as hf
from llm.clients.base import AuthError, RateLimitError, ModelUnavailableError


def _install_fake_hub(monkeypatch, *, chat_ret=None, chat_exc=None, text_ret=None):
    """huggingface_hub.InferenceClient'i sahteleyen modül kur."""
    class _Msg:
        def __init__(self, c): self.message = types.SimpleNamespace(content=c)
    class _FakeClient:
        def __init__(self, *a, **k): pass
        def chat_completion(self, **k):
            if chat_exc:
                raise chat_exc
            return types.SimpleNamespace(choices=[_Msg(chat_ret)])
        def text_generation(self, **k):
            return text_ret
    fake = types.ModuleType("huggingface_hub")
    fake.InferenceClient = _FakeClient
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake)


class TestNoKey:
    def test_missing_key_raises_autherror(self, monkeypatch):
        monkeypatch.setattr(hf, "HF_API_KEY", "")
        with pytest.raises(AuthError):
            hf.HuggingFaceClient(model_name="x")


class TestCall:
    def test_chat_success(self, monkeypatch):
        monkeypatch.setattr(hf, "HF_API_KEY", "tok")
        _install_fake_hub(monkeypatch, chat_ret="  hello  ")
        c = hf.HuggingFaceClient(model_name="m")
        assert c("hi") == "hello"

    def test_empty_content_is_unavailable(self, monkeypatch):
        monkeypatch.setattr(hf, "HF_API_KEY", "tok")
        _install_fake_hub(monkeypatch, chat_ret="")
        c = hf.HuggingFaceClient(model_name="m")
        with pytest.raises(ModelUnavailableError):
            c("hi")

    def test_rate_limit_classified(self, monkeypatch):
        monkeypatch.setattr(hf, "HF_API_KEY", "tok")
        _install_fake_hub(monkeypatch, chat_exc=RuntimeError("429 too many requests"))
        c = hf.HuggingFaceClient(model_name="m")
        with pytest.raises(RateLimitError):
            c("hi")

    def test_chat_unsupported_falls_back_to_text(self, monkeypatch):
        monkeypatch.setattr(hf, "HF_API_KEY", "tok")
        # chat_completion AttributeError → text_generation devreye girer
        _install_fake_hub(monkeypatch, chat_exc=AttributeError("no chat"), text_ret="  via-text  ")
        c = hf.HuggingFaceClient(model_name="m")
        assert c("hi") == "via-text"
