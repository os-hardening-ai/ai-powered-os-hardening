"""
Unit tests for llm.pipelines.layers.safety_classifier (Layer 1).

The LLM is replaced with a deterministic fake callable, so these tests are
fast, offline and reproducible. They exercise our parsing / fallback / stats
logic — NOT the real model's judgement (that belongs to the e2e tier).
"""

from __future__ import annotations

import pytest

from llm.pipelines.layers.safety_classifier import (
    SafetyClassifier,
    SafetyResult,
    classify_safety,
)


def fake_llm(response: str):
    """Return a callable that always yields `response` (ignores the prompt)."""
    return lambda _prompt: response


class TestSafetyResult:
    def test_is_safe_flag_for_safe_categories(self):
        for cat in ("safe_defensive", "safe_educational", "ambiguous"):
            assert SafetyResult(category=cat, confidence=0.9, reason="x").is_safe

    def test_is_safe_flag_for_unsafe_categories(self):
        for cat in ("unsafe_offensive", "unsafe_spam"):
            assert not SafetyResult(category=cat, confidence=0.9, reason="x").is_safe


class TestClassify:
    def test_empty_question_is_spam(self):
        clf = SafetyClassifier(fake_llm("{}"))
        res = clf.classify("   ")
        assert res.category == "unsafe_spam"
        assert res.is_safe is False

    def test_clean_json_defensive(self):
        clf = SafetyClassifier(
            fake_llm('{"category": "safe_defensive", "confidence": 0.95, "reason": "ssh hardening"}')
        )
        res = clf.classify("How to harden SSH?")
        assert res.category == "safe_defensive"
        assert res.confidence == pytest.approx(0.95)
        assert res.is_safe

    def test_offensive_is_blocked(self):
        clf = SafetyClassifier(
            fake_llm('{"category": "unsafe_offensive", "confidence": 0.9, "reason": "exploit"}')
        )
        res = clf.classify("How to exploit SSH?")
        assert res.category == "unsafe_offensive"
        assert res.is_safe is False

    def test_markdown_wrapped_json(self):
        raw = '```json\n{"category": "safe_educational", "confidence": 0.8, "reason": "learning"}\n```'
        clf = SafetyClassifier(fake_llm(raw))
        res = clf.classify("What is a buffer overflow?")
        assert res.category == "safe_educational"

    def test_regex_fallback_on_malformed_json(self):
        raw = 'garbage "category": "unsafe_spam" , "confidence": 0.7 trailing'
        clf = SafetyClassifier(fake_llm(raw))
        res = clf.classify("buy cheap meds")
        assert res.category == "unsafe_spam"
        assert res.confidence == pytest.approx(0.7)

    def test_llm_exception_falls_back_to_ambiguous(self):
        def boom(_):
            raise RuntimeError("provider down")

        clf = SafetyClassifier(boom)
        res = clf.classify("anything")
        assert res.category == "ambiguous"
        assert res.confidence == 0.5

    def test_stats_accumulate(self):
        clf = SafetyClassifier(
            fake_llm('{"category": "safe_defensive", "confidence": 0.9, "reason": "ok"}')
        )
        clf.classify("q1")
        clf.classify("q2")
        stats = clf.get_stats()
        assert stats["total_classifications"] == 2
        assert stats["safe_count"] == 2
        assert stats["safe_rate"] == pytest.approx(1.0)

    def test_get_stats_empty(self):
        clf = SafetyClassifier(fake_llm("{}"))
        assert clf.get_stats()["total_classifications"] == 0


class TestConvenience:
    def test_classify_safety_helper(self):
        res = classify_safety(
            "harden ufw",
            fake_llm('{"category": "safe_defensive", "confidence": 0.9, "reason": "fw"}'),
        )
        assert isinstance(res, SafetyResult)
        assert res.is_safe
