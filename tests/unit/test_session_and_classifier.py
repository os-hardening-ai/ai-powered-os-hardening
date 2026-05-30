"""
Unit tests for llm.core.session_store.SessionStore and
llm.utils.question_classifier (both pure, in-memory).
"""

from __future__ import annotations

from llm.core.session_store import SessionStore, Turn, global_session_store
from llm.utils.question_classifier import classify_question, QuestionClassifier


class TestSessionStore:
    def test_add_and_get_history(self):
        s = SessionStore(max_history=5)
        s.add_turn("s1", "user", "soru", intent="os_hardening")
        s.add_turn("s1", "assistant", "cevap", intent="os_hardening")
        hist = s.get_history("s1")
        assert len(hist) == 2
        assert isinstance(hist[0], Turn)
        assert hist[0].role == "user"

    def test_history_capped_to_max(self):
        s = SessionStore(max_history=3)
        for i in range(10):
            s.add_turn("s1", "user", f"m{i}")
        hist = s.get_history("s1")
        assert len(hist) == 3
        # most recent kept
        assert hist[-1].content == "m9"

    def test_memory_leak_trim(self):
        s = SessionStore(max_history=2)
        # exceed max_history*4 -> internal list trimmed
        for i in range(20):
            s.add_turn("s1", "user", f"m{i}")
        assert len(s._sessions["s1"]) <= s.max_history * 4

    def test_unknown_session_returns_empty(self):
        s = SessionStore()
        assert s.get_history("nope") == []

    def test_reset_session(self):
        s = SessionStore()
        s.add_turn("s1", "user", "x")
        s.reset_session("s1")
        assert s.get_history("s1") == []
        # resetting unknown session is a no-op
        s.reset_session("ghost")

    def test_global_instance_exists(self):
        assert isinstance(global_session_store, SessionStore)


class TestQuestionClassifier:
    def test_short_question_is_simple(self):
        assert classify_question("ssh nedir") == "simple"

    def test_greeting_is_simple(self):
        assert classify_question("merhaba nasılsın bugün") == "simple"

    def test_script_request_is_complex(self):
        assert classify_question("bana tam bir hardening script yaz lütfen") == "complex"

    def test_zero_trust_is_complex(self):
        assert classify_question("zero trust architecture maturity değerlendirmesi gerekli") == "complex"

    def test_service_config_is_medium(self):
        assert classify_question("ssh config dosyasını nasıl güvenli yapılandırırım") == "medium"

    def test_long_generic_is_complex(self):
        q = " ".join(["kelime"] * 25)
        assert classify_question(q) == "complex"

    def test_classifier_class_direct(self):
        c = QuestionClassifier()
        assert c.classify("firewall ufw kuralları nasıl") in {"simple", "medium", "complex"}
