"""Unit tests for HuggingFaceClient — ücretsiz tier, taksonomi entegrasyonu (mock'lu)."""

from __future__ import annotations

import sys
import types

import pytest

import llm.clients.huggingface_client as hf
from llm.clients.base import AuthError, RateLimitError, ModelUnavailableError


def _install_fake_hub(monkeypatch, *, chat_ret=None, chat_exc=None, text_ret=None, captured=None):
    """huggingface_hub.InferenceClient'i sahteleyen modül kur.

    captured (dict verilirse) InferenceClient kurucu kwargs'larını yakalar →
    provider/token wiring'i doğrulanabilir.
    """
    class _Msg:
        def __init__(self, c): self.message = types.SimpleNamespace(content=c)
    class _FakeClient:
        def __init__(self, *a, **k):
            if captured is not None:
                captured.update(k)
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


class TestProviderRouting:
    """provider parametresi — HF'nin partner-provider yönlendirmesi (regresyon koruması).

    Eski kod provider='hf-inference' sabitliyordu; HF modelleri partner provider'lara
    taşıyınca bu 500 veriyordu. Artık varsayılan auto-route (None).
    """

    def test_default_provider_is_auto_route_none(self, monkeypatch):
        monkeypatch.setattr(hf, "HF_API_KEY", "tok")
        monkeypatch.delenv("HF_PROVIDER", raising=False)
        cap = {}
        _install_fake_hub(monkeypatch, chat_ret="OK", captured=cap)
        hf.HuggingFaceClient(model_name="m")
        assert cap.get("provider") is None          # auto-route (NOT 'hf-inference')
        assert cap.get("token") == "tok"

    def test_explicit_provider_passed_through(self, monkeypatch):
        monkeypatch.setattr(hf, "HF_API_KEY", "tok")
        cap = {}
        _install_fake_hub(monkeypatch, chat_ret="OK", captured=cap)
        hf.HuggingFaceClient(model_name="m", provider="together")
        assert cap.get("provider") == "together"

    def test_hf_provider_env_override(self, monkeypatch):
        monkeypatch.setattr(hf, "HF_API_KEY", "tok")
        monkeypatch.setenv("HF_PROVIDER", "fireworks-ai")
        cap = {}
        _install_fake_hub(monkeypatch, chat_ret="OK", captured=cap)
        hf.HuggingFaceClient(model_name="m")
        assert cap.get("provider") == "fireworks-ai"

    def test_explicit_provider_beats_env(self, monkeypatch):
        monkeypatch.setattr(hf, "HF_API_KEY", "tok")
        monkeypatch.setenv("HF_PROVIDER", "fromenv")
        cap = {}
        _install_fake_hub(monkeypatch, chat_ret="OK", captured=cap)
        hf.HuggingFaceClient(model_name="m", provider="explicit")
        assert cap.get("provider") == "explicit"


class TestFactories:
    """get_small/large_hf_llm config'teki HF modellerini kullanmalı."""

    def test_factories_use_config_models(self, monkeypatch):
        monkeypatch.setattr(hf, "HF_API_KEY", "tok")
        _install_fake_hub(monkeypatch, chat_ret="OK")
        small = hf.get_small_hf_llm()
        large = hf.get_large_hf_llm()
        assert small.model_name == hf.SMALL_MODEL_NAME
        assert large.model_name == hf.LARGE_MODEL_NAME
        # düzeltme sonrası: doğrulanmış ücretsiz Llama modelleri (gated Mistral/Mixtral değil)
        assert "Llama-3.2-3B" in small.model_name
        assert "Llama-3.1-8B" in large.model_name
