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

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Bilinmeyen"):
            get_spec("gemini")

    def test_case_insensitive(self):
        assert get_spec("GROQ").name == "groq"


class TestFreeFirstOrder:
    def test_excludes_paid_and_deprecated_by_default(self):
        order = free_first_order()
        assert "novita" not in order and "openai" not in order
        assert "huggingface" not in order            # DEPRECATED → varsayılan zincirden çıkarıldı
        assert "cerebras" in order and "sambanova" in order
        assert "groq" in order and "ollama" in order

    def test_cerebras_first_then_sambanova_then_groq(self):
        order = free_first_order()
        assert order[0] == "cerebras"                # en hızlı + ücretsiz 1M/gün
        assert order.index("cerebras") < order.index("sambanova") < order.index("groq")

    def test_groq_before_ollama(self):
        order = free_first_order()
        assert order.index("groq") < order.index("ollama")  # hız önceliği (ollama offline son-çare)

    def test_include_cheap_adds_novita_not_openai(self):
        order = free_first_order(include_cheap=True)
        assert "novita" in order        # ucuz paid güvenlik ağı
        assert "openai" not in order    # pahalı hariç
        assert order.index("groq") < order.index("novita")  # ücretsizler önce

    def test_include_paid_adds_everything(self):
        order = free_first_order(include_paid=True)
        assert "novita" in order and "openai" in order
        assert order.index("novita") < order.index("openai")  # ucuz, pahalıdan önce


class TestBuildOrder:
    def test_primary_goes_first(self):
        order = build_order(primary="ollama")
        assert order[0] == "ollama"
        assert "groq" in order  # diğer ücretsizler kalır

    def test_no_duplicate_primary(self):
        order = build_order(primary="groq")
        assert order.count("groq") == 1

    def test_default_is_free_first(self):
        assert build_order() == free_first_order()

    def test_cheap_primary_allowed_explicitly(self):
        # kullanıcı açıkça novita derse, flag kapalı olsa da başa gelir
        order = build_order(primary="novita")
        assert order[0] == "novita"

    def test_include_cheap_appends_novita_as_safety_net(self):
        order = build_order(include_cheap=True)
        assert order[0] == "cerebras"   # ücretsiz-first primary (en hızlı)
        assert "novita" in order        # 429 güvenlik ağı sonda
        assert order.index("cerebras") < order.index("novita")
        assert "huggingface" not in order   # deprecated hariç

    def test_deprecated_hf_still_explicitly_selectable(self):
        # HF varsayılan zincirde yok ama açıkça primary seçilirse yine başa gelir
        order = build_order(primary="huggingface")
        assert order[0] == "huggingface"
