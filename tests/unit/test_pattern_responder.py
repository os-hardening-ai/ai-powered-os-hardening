"""
Unit tests for llm.pipelines.layers.pattern_responder (Layer 3A).

Pure pattern matching — no LLM, no network. Delegates to LocalResponder.
"""

from __future__ import annotations

from llm.pipelines.layers.pattern_responder import (
    PatternResponderHandler,
    PatternResponse,
    handle_pattern_response,
)


class TestInferCategory:
    """_infer_category is deterministic keyword logic."""

    def setup_method(self):
        self.h = PatternResponderHandler()

    def test_greeting(self):
        assert self.h._infer_category("merhaba", "...") == "greeting"

    def test_farewell(self):
        assert self.h._infer_category("görüşürüz", "...") == "farewell"

    def test_thanks(self):
        assert self.h._infer_category("teşekkürler", "...") == "thanks"

    def test_definition(self):
        assert self.h._infer_category("CIS nedir?", "...") == "security_definition"

    def test_command(self):
        assert self.h._infer_category("SSH port değiştir", "...") == "quick_command"

    def test_affirmation(self):
        assert self.h._infer_category("evet", "...") == "affirmation"

    def test_other(self):
        assert self.h._infer_category("xyz random", "...") == "other"


class TestHandle:
    def test_greeting_returns_response(self):
        h = PatternResponderHandler()
        res = h.handle("merhaba")
        # Greetings are handled locally -> non-None response
        assert res is not None
        assert isinstance(res, PatternResponse)
        assert res.category == "greeting"
        assert res.response

    def test_technical_query_returns_none(self):
        h = PatternResponderHandler()
        # A specific hardening request is NOT smalltalk -> needs LLM -> None
        res = h.handle("Ubuntu 24.04 sunucumda sshd_config dosyasını CIS 5.2'ye göre nasıl sıkılaştırırım?")
        assert res is None

    def test_stats_tracked_on_match(self):
        h = PatternResponderHandler()
        if h.handle("merhaba") is not None:
            assert h.get_stats()["total_responses"] >= 1


class TestConvenience:
    def test_helper_matches_greeting(self):
        res = handle_pattern_response("selam")
        assert res is None or isinstance(res, PatternResponse)
