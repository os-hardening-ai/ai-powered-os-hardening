"""Unit tests for llm.clients.registry — FREE/PAID etiketi + ücretsiz-first sıra."""

from __future__ import annotations

import pytest

from llm.clients.registry import (
    Cost,
    ProviderSpec,
    get_spec,
    all_specs,
    free_first_order,
    build_order,
)


class TestSpecs:
    def test_known_providers_registered(self):
        names = set(all_specs())
        assert {"cerebras", "sambanova", "groq", "ollama", "novita", "openai"} <= names

    def test_cerebras_sambanova_free_tier(self):
        assert get_spec("cerebras").cost is Cost.FREE_TIER
        assert get_spec("sambanova").cost is Cost.FREE_TIER

    def test_hf_is_deprecated(self):
        # HF bozuk → registered ama deprecated (otomatik zincire alınmaz)
        assert get_spec("huggingface").deprecated is True

    def test_groq_is_free_tier(self):
        assert get_spec("groq").cost is Cost.FREE_TIER

    def test_ollama_is_free(self):
        assert get_spec("ollama").cost is Cost.FREE

    def test_novita_is_cheap_paid(self):
        assert get_spec("novita").cost is Cost.CHEAP_PAID

    def test_openai_is_paid(self):
        assert get_spec("openai").cost is Cost.PAID

    def test_gemini_registered_cheap_paid(self):
        assert get_spec("gemini").cost is Cost.CHEAP_PAID

    def test_groq_ollama_deprecated(self):
        # Kullanıcı kararı: groq (flaky) + ollama (GPU yok) → otomatik zincirden çıkarıldı
        assert get_spec("groq").deprecated is True
        assert get_spec("ollama").deprecated is True

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Bilinmeyen"):
            get_spec("nonexistent_provider_xyz")

    def test_case_insensitive(self):
        assert get_spec("GROQ").name == "groq"


class TestFreeFirstOrder:
    def test_only_active_free_in_default(self):
        order = free_first_order()
        # Varsayılan zincir: yalnızca cerebras (sambanova 2026-06 rate-limit → deprecated;
        # groq/ollama/hf deprecated; paid hariç). Tek aktif ücretsiz sağlayıcı.
        assert "cerebras" in order
        assert "sambanova" not in order                             # rate-limit → deprecated
        assert "novita" not in order and "openai" not in order      # paid/deprecated (cheap flag yok)
        for dep in ("groq", "ollama", "huggingface"):
            assert dep not in order, f"{dep} deprecated → zincirde olmamalı"

    def test_cerebras_first(self):
        order = free_first_order()
        assert order[0] == "cerebras"                                # en hızlı + ücretsiz 1M/gün (tek aktif free)

    def test_include_cheap_adds_gemini_not_novita_not_openai(self):
        order = free_first_order(include_cheap=True)
        assert "gemini" in order                                     # Gemini Flash Lite (OpenRouter) cheap fallback
        assert "novita" not in order                                 # Novita LLM DEPRECATED (embedding-only) → zincirde yok
        assert "openai" not in order                                 # pahalı hariç
        assert order.index("cerebras") < order.index("gemini")       # cerebras primary, gemini fallback

    def test_include_paid_adds_openai_last(self):
        order = free_first_order(include_paid=True)
        assert "openai" in order
        assert order.index("gemini") < order.index("openai")         # ucuz gemini, pahalı openai'den önce


class TestBuildOrder:
    def test_primary_goes_first(self):
        order = build_order(primary="cerebras", include_cheap=True)
        assert order[0] == "cerebras"
        assert "gemini" in order  # OpenRouter cheap fallback (sambanova/novita deprecated)

    def test_no_duplicate_primary(self):
        order = build_order(primary="groq")
        assert order.count("groq") == 1

    def test_default_is_free_first(self):
        assert build_order() == free_first_order()

    def test_cheap_primary_allowed_explicitly(self):
        # kullanıcı açıkça novita derse, flag kapalı olsa da başa gelir
        order = build_order(primary="novita")
        assert order[0] == "novita"

    def test_include_cheap_chain_gemini_safety_net_no_novita(self):
        order = build_order(include_cheap=True)
        assert order[0] == "cerebras"   # ücretsiz-first primary (en hızlı)
        assert "gemini" in order        # OpenRouter cheap fallback (güvenlik ağı)
        assert "novita" not in order    # Novita LLM DEPRECATED (embedding-only) → otomatik zincirde yok
        assert "huggingface" not in order   # deprecated hariç

    def test_deprecated_hf_still_explicitly_selectable(self):
        # HF varsayılan zincirde yok ama açıkça primary seçilirse yine başa gelir
        order = build_order(primary="huggingface")
        assert order[0] == "huggingface"
