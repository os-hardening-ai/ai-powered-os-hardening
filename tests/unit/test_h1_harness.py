"""
Unit tests for evaluation.h1_rag_vs_llm scoring logic (deterministic, no LLM).

The live A/B run needs Groq+Qdrant, but the scoring functions and report
aggregation are pure — they are the part that must be trusted, so they are
unit-tested here.
"""

from __future__ import annotations

import pytest

from evaluation.h1_rag_vs_llm import (
    fact_recall,
    cites_section,
    _normalize,
    ModeSample,
    H1Pair,
    H1Report,
    to_markdown,
)


class TestFactRecall:
    def test_all_facts_present(self):
        ans = "CIS önerisi: PermitRootLogin no ve MaxAuthTries 4 olmalı."
        assert fact_recall(ans, ["permitrootlogin no", "maxauthtries 4"]) == 1.0

    def test_partial_recall(self):
        ans = "Sadece PermitRootLogin no ayarlayın."
        assert fact_recall(ans, ["permitrootlogin no", "maxauthtries 4"]) == 0.5

    def test_zero_recall(self):
        assert fact_recall("alakasız metin", ["permitrootlogin no"]) == 0.0

    def test_alternatives_any_match(self):
        # "a|b" → herhangi biri eşleşirse sayılır
        assert fact_recall("set MaxAuthTries=4 here", ["maxauthtries 4|maxauthtries=4"]) == 1.0

    def test_whitespace_and_case_insensitive(self):
        ans = "PERMITROOTLOGIN    NO"
        assert fact_recall(ans, ["permitrootlogin no"]) == 1.0

    def test_empty_expected_is_full(self):
        assert fact_recall("anything", []) == 1.0


class TestCitation:
    def test_cites_exact_section(self):
        assert cites_section("Bkz. CIS 5.1 bölümü", "5.1") is True

    def test_cites_subsection(self):
        assert cites_section("CIS 5.1.22 kuralı", "5.1") is True

    def test_no_citation(self):
        assert cites_section("genel bir öneri", "5.1") is False

    def test_does_not_match_substring_number(self):
        # "15.1" doğru '5.1' atfı sayılmamalı
        assert cites_section("port 15.1 değil", "5.1") is False


class TestNormalize:
    def test_collapses_whitespace(self):
        assert _normalize("  A\t B\n C ") == "a b c"


class TestReportAggregation:
    def _pair(self, q, pr, rr, pg, rg):
        return H1Pair(
            question=q,
            pure=ModeSample("pure", "x", pr, pg, False, 1.0),
            rag=ModeSample("rag", "y", rr, rg, True, 1.5),
            num_chunks=3,
        )

    def test_summary_counts_wins_ties_losses(self):
        rep = H1Report(pairs=[
            self._pair("q1", 0.0, 1.0, 0.2, 0.9),   # rag win
            self._pair("q2", 0.5, 0.5, 0.5, 0.5),   # tie
            self._pair("q3", 1.0, 0.0, 0.8, 0.1),   # rag loss
        ])
        s = rep.summary()
        assert s["n"] == 3
        assert s["rag_wins"] == 1
        assert s["ties"] == 1
        assert s["rag_losses"] == 1
        assert s["pure_fact_recall"] == pytest.approx(0.5)
        assert s["rag_fact_recall"] == pytest.approx(0.5)
        assert s["rag_citation_rate"] == pytest.approx(1.0)
        assert s["pure_citation_rate"] == pytest.approx(0.0)

    def test_markdown_renders_table(self):
        rep = H1Report(pairs=[self._pair("soru bir", 0.0, 1.0, 0.1, 0.9)])
        md = to_markdown(rep)
        assert "# H1 Kanıtı" in md
        assert "Fact-recall" in md
        assert "soru bir" in md
