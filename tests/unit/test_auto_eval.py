"""
auto_eval (LLM-judge otomatik değerlendirme) birim testleri — TAMAMEN AĞSIZ.

answer_fn + judge_fn enjekte edilir (sahte). Gerçek LLM/RAG çağrılmaz. Test edilen:
saf yardımcılar (verdict/score/likert parse, actionability→süre türetme), harness'in
survey_eval şemasına doğru dönüştürmesi, RAG-vs-no_rag kıyası, conservative fallback.
"""
from __future__ import annotations

import json

import pytest

from evaluation.auto_eval import (
    AutoEvalHarness,
    EvalScenario,
    actionability_to_decision_time,
    normalize_verdict,
    parse_score,
    parse_likert,
    to_markdown,
    _DT_BASE_S,
)
from evaluation.survey_eval import summarize as survey_summarize


# ── saf yardımcılar ──
class TestPureHelpers:
    def test_actionability_monotonic(self):
        # yüksek actionability → düşük karar süresi (monotonik azalan)
        assert actionability_to_decision_time(1.0) < actionability_to_decision_time(0.5)
        assert actionability_to_decision_time(0.5) < actionability_to_decision_time(0.0)
        assert actionability_to_decision_time(1.0) == 0.0
        assert actionability_to_decision_time(0.0) == pytest.approx(_DT_BASE_S)

    def test_actionability_clamps(self):
        assert actionability_to_decision_time(2.0) == 0.0      # >1 kırpılır
        assert actionability_to_decision_time(-1.0) == pytest.approx(_DT_BASE_S)

    @pytest.mark.parametrize("raw,exp", [
        ("accept", "accept"), ("ACCEPT", "accept"), ("modify it", "modify"),
        ("reject", "reject"), ("kabul ederim", "accept"), ("reddederim", "reject"),
        ("belirsiz şey", "modify"),  # bilinmeyen → conservative modify
    ])
    def test_normalize_verdict(self, raw, exp):
        assert normalize_verdict(raw) == exp

    @pytest.mark.parametrize("raw,exp", [
        ("0.8", 0.8), ("1.0", 1.0), ("0", 0.0), ("yes fully", 1.0), ("no", 0.0),
    ])
    def test_parse_score(self, raw, exp):
        assert parse_score(raw) == pytest.approx(exp)

    def test_parse_score_fallback(self):
        assert parse_score("anlamsız metin") == 0.5

    @pytest.mark.parametrize("raw,exp", [(5, 5), (1, 1), (7, 5), (0, 1), ("4", 4), ("x", 3)])
    def test_parse_likert(self, raw, exp):
        assert parse_likert(raw) == exp


# ── sahte LLM'ler ──
def _fake_answer(rag_text="RAG cevabı: PermitRootLogin no ayarla, sshd restart.",
                 norag_text="Genel öneri: ssh'i güvenli yapın."):
    def fn(goal, use_rag):
        return (rag_text, 5) if use_rag else (norag_text, 0)
    return fn


def _fake_judge(rag_json: dict, norag_json: dict):
    """RAG cevabına yüksek, no-RAG'e düşük puan veren sahte judge (prompt'a göre ayırır)."""
    def fn(prompt):
        # RAG cevabı prompt'ta 'RAG cevabı' geçer → yüksek; değilse düşük
        return json.dumps(rag_json if "RAG cevabı" in prompt else norag_json)
    return fn


_HIGH = {"verdict": "accept", "actionability": 0.9, "usefulness": 5, "trust": 5,
         "clarity": 4, "would_use_again": 5, "overall_satisfaction": 5, "reason": "net"}
_LOW = {"verdict": "modify", "actionability": 0.3, "usefulness": 3, "trust": 2,
        "clarity": 3, "would_use_again": 2, "overall_satisfaction": 2, "reason": "belirsiz"}


class TestHarness:
    def _run(self, judge):
        h = AutoEvalHarness(answer_fn=_fake_answer(), judge_fn=judge)
        return h.run([EvalScenario("SSH sıkılaştır"), EvalScenario("UFW yapılandır")])

    def test_run_produces_results(self):
        rep = self._run(_fake_judge(_HIGH, _LOW))
        assert len(rep.results) == 2
        assert rep.results[0].rag.verdict == "accept"
        assert rep.results[0].no_rag.verdict == "modify"
        assert rep.results[0].n_chunks == 5

    def test_survey_data_shape_valid(self):
        # to_survey_data() çıktısı survey_eval.summarize() ile sorunsuz işlenmeli
        rep = self._run(_fake_judge(_HIGH, _LOW))
        data = rep.to_survey_data()
        s = survey_summarize(data)
        assert s["n_participants"] == 2
        assert "ip12_satisfaction" in s and "h4_acceptance" in s and "h2_decision_time" in s

    def test_high_rag_satisfaction_passes_ip12(self):
        # RAG Likert hep ≥4 → memnuniyet %100 → İP-12 eşiği (%70) geçer
        rep = self._run(_fake_judge(_HIGH, _LOW))
        s = survey_summarize(rep.to_survey_data())
        assert s["ip12_satisfaction"]["passed"] is True

    def test_h4_rag_beats_norag(self):
        # RAG accept(1.0) > no-RAG modify(0.5) → H4 RAG kazanır
        rep = self._run(_fake_judge(_HIGH, _LOW))
        cmp = rep.rag_vs_norag()
        assert cmp["rag_accept_credit"] > cmp["norag_accept_credit"]

    def test_h2_decision_time_reduction(self):
        # RAG actionability 0.9 > no-RAG 0.3 → araçla süre < araçsız → azalma >0
        rep = self._run(_fake_judge(_HIGH, _LOW))
        s = survey_summarize(rep.to_survey_data())
        assert s["h2_decision_time"]["reduction_pct"] > 0
        assert s["h2_supported"] is True

    def test_markdown_renders(self):
        rep = self._run(_fake_judge(_HIGH, _LOW))
        md = to_markdown(rep)
        assert "Otomatik LLM-Judge" in md
        assert "İP-12" in md and "H4" in md and "H2" in md
        assert "Dürüstlük notu" in md   # proxy olduğu açıkça yazılı

    def test_judge_parse_failure_is_conservative(self):
        # judge bozuk metin döndürürse → verdict=modify, likert=3, actionability=0.5 (crash yok)
        rep = self._run(lambda prompt: "tamamen bozuk yanıt, json yok")
        r = rep.results[0]
        assert r.rag.verdict == "modify"
        assert r.rag.actionability == 0.5
        assert all(v == 3 for v in r.rag.likert.values())

    def test_judge_exception_is_caught(self):
        def boom(_prompt):
            raise RuntimeError("judge down")
        h = AutoEvalHarness(answer_fn=_fake_answer(), judge_fn=boom)
        rep = h.run([EvalScenario("SSH sıkılaştır")])
        # senaryo atlanmaz; conservative değerlerle sonuç üretilir
        assert len(rep.results) == 1
        assert rep.results[0].rag.verdict == "modify"
