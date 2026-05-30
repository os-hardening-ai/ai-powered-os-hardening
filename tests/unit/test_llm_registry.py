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
        assert {"groq", "huggingface", "ollama", "novita", "openai"} <= names

    def test_groq_is_free_tier(self):
        assert get_spec("groq").cost is Cost.FREE_TIER

    def test_ollama_is_free(self):
        assert get_spec("ollama").cost is Cost.FREE

    def test_novita_openai_are_paid(self):
        assert get_spec("novita").cost is Cost.PAID
        assert get_spec("openai").cost is Cost.PAID

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Bilinmeyen"):
            get_spec("gemini")

    def test_case_insensitive(self):
        assert get_spec("GROQ").name == "groq"


class TestFreeFirstOrder:
    def test_excludes_paid_by_default(self):
        order = free_first_order()
        assert "novita" not in order and "openai" not in order
        assert "groq" in order and "ollama" in order and "huggingface" in order

    def test_groq_before_ollama(self):
        order = free_first_order()
        assert order.index("groq") < order.index("ollama")  # hız önceliği

    def test_include_paid_appends_at_end(self):
        order = free_first_order(include_paid=True)
        assert "novita" in order
        # paid en sonda (free_priority 900+)
        assert order.index("groq") < order.index("novita")


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

    def test_paid_primary_allowed_explicitly(self):
        # kullanıcı açıkça novita derse, paid olsa da başa gelir
        order = build_order(primary="novita", include_paid=True)
        assert order[0] == "novita"
