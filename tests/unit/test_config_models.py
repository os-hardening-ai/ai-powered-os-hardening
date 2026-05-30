"""
config.json LLM sağlayıcı modellerinin tutarlılık testleri.

Bu testler, sağlayıcı modellerinin ÇALIŞAN ücretsiz adlara işaret ettiğini garanti
eder ve geçmişte yaşanan iki regresyonu önler:
  1. Ollama large = llama3.1:70b → ARM/dizüstüde imkânsız (40GB+).
  2. HF default = gated Mistral/Mixtral → ücretsiz tier'da 401/dağınık yanıt.
Network YOK — yalnızca config + config.py çözümleme doğrulanır.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.json"


@pytest.fixture(scope="module")
def providers():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return cfg["llm"]["providers"]


class TestProviderBlocks:
    def test_free_providers_present_and_enabled(self, providers):
        # Ücretsiz/ücretsiz-tier sağlayıcıların hepsi config'te tanımlı olmalı
        for name in ("groq", "ollama", "huggingface", "novita"):
            assert name in providers, f"{name} config'te yok"
        assert providers["groq"]["enabled"] is True
        assert providers["ollama"]["enabled"] is True
        assert providers["huggingface"]["enabled"] is True

    def test_each_provider_has_small_and_large(self, providers):
        for name, blk in providers.items():
            assert "small" in blk["models"] and "large" in blk["models"], name
            assert blk["models"]["small"]["name"], name
            assert blk["models"]["large"]["name"], name


class TestNoUnrealisticModels:
    def test_ollama_not_70b(self, providers):
        """Ollama 70b regresyonu — dizüstü/ARM'de çalışamaz."""
        for role in ("small", "large"):
            name = providers["ollama"]["models"][role]["name"]
            assert "70b" not in name.lower(), f"Ollama {role} = {name} (70b imkânsız)"

    def test_ollama_uses_pulled_models(self, providers):
        # Bu makinede gerçekten çekilip test edilen modeller
        names = {providers["ollama"]["models"]["small"]["name"],
                 providers["ollama"]["models"]["large"]["name"]}
        assert names <= {"llama3.2:1b", "llama3.2:3b"}, names

    def test_hf_not_gated_mistral(self, providers):
        """HF gated Mistral/Mixtral regresyonu — ücretsiz tier'da çalışmıyordu."""
        for role in ("small", "large"):
            name = providers["huggingface"]["models"][role]["name"].lower()
            assert "mixtral" not in name, f"HF {role}: Mixtral gated"


class TestConfigPyResolution:
    def test_hf_defaults_resolve_to_working_models(self):
        from llm.core.config import SMALL_MODEL_NAME, LARGE_MODEL_NAME
        assert "Llama-3.2-3B" in SMALL_MODEL_NAME
        assert "Llama-3.1-8B" in LARGE_MODEL_NAME

    def test_ollama_defaults_resolve(self):
        from llm.core.config import CONFIG
        assert CONFIG.ollama_small_model == "llama3.2:1b"
        assert CONFIG.ollama_large_model == "llama3.2:3b"
