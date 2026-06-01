"""
Tests for the LIGHTWEIGHT answer-groundedness refinement loop
(InfoPipeline._refine_answer).

When the verification confidence of the FIRST answer is below `refine_threshold`,
the pipeline makes ONE small-model correction call against the ALREADY-retrieved
sources (NO re-retrieval / NO re-planning) and re-verifies — keeping the new
answer ONLY if its confidence improved.

All fakes (no network/LLM): the verifier scores confidence from the ANSWER text
('GROUNDED' → high), so we deterministically drive low→high (or low→still-low)
transitions without any retrieval round.
"""

from __future__ import annotations

import pytest

from llm.core.context import RequestContext
from llm.pipelines.layers import info_pipeline as ip_mod
from llm.pipelines.layers.info_pipeline import InfoPipeline
from rag.verify.claim_verifier import VerificationResult


class FakeLLM:
    """Sabit bir metin döner; çağrı sayısını izler. system= kwargs'ı kabul eder."""
    def __init__(self, text: str):
        self.calls = 0
        self.text = text

    def __call__(self, prompt: str, **kw) -> str:
        self.calls += 1
        return self.text


class FakeRag:
    """retrieve_balanced: tek kaynak seti döner; refinement bunu YENİDEN çağırmamalı."""
    def __init__(self):
        self.calls: list[str] = []

    def retrieve_balanced(self, query: str, **kw):
        self.calls.append(query)
        return "CTX_SOURCES", [
            {"text": "rule a", "id": "r1", "metadata": {}},
            {"text": "rule b", "id": "r2", "metadata": {}},
        ]


class FakeVerifier:
    """Confidence ANSWER içeriğinden: 'GROUNDED' → 0.9 (geçerli), aksi 0.3 (düşük)."""
    def verify(self, answer, chunks):
        good = "GROUNDED" in (answer or "")
        conf = 0.9 if good else 0.3
        return VerificationResult(
            is_valid=conf >= 0.6,
            confidence=conf,
            unsupported=[] if good else ["unsupported claim about ssh config"],
        )


@pytest.fixture(autouse=True)
def force_medium(monkeypatch):
    # Karmaşıklığı 'medium'a sabitle → RAG + llm_large yolu (CoT belirsizliği yok).
    monkeypatch.setattr(ip_mod, "classify_question", lambda q: "medium")


def _pipeline(rag, verifier, *, large_text, small_text,
              enable_refinement=True, refine_threshold=0.40):
    return InfoPipeline(
        llm_small=FakeLLM(small_text),
        llm_large=FakeLLM(large_text),
        rag_builder=rag,
        claim_verifier=verifier,
        enable_refinement=enable_refinement,
        refine_threshold=refine_threshold,
    )


_Q = "ubuntu 24.04 ssh sshd_config sıkılaştırma adımları neler"


class TestLightweightRefinement:
    def test_low_confidence_triggers_correction_and_keeps_better(self):
        # İlk üretim (large) ungrounded → 0.3 → düzeltme (small) GROUNDED → 0.9 → tut.
        rag = FakeRag()
        p = _pipeline(rag, FakeVerifier(),
                      large_text="INITIAL ungrounded answer",
                      small_text="GROUNDED corrected answer")
        res = p.handle(RequestContext(user_question=_Q))
        assert p.stats["refine_count"] == 1
        assert p.llm_small.calls == 1                 # TEK düzeltme çağrısı
        assert len(rag.calls) == 1                    # YENİDEN retrieval YOK
        assert res.verification_confidence == 0.9     # 0.3 → 0.9 iyileşti
        assert "GROUNDED" in res.answer               # düzeltilmiş cevap tutuldu

    def test_high_initial_confidence_no_refine(self):
        # İlk üretim zaten GROUNDED → 0.9 → düzeltme hiç çalışmaz.
        rag = FakeRag()
        p = _pipeline(rag, FakeVerifier(),
                      large_text="GROUNDED initial answer",
                      small_text="should-not-be-called")
        res = p.handle(RequestContext(user_question=_Q))
        assert p.stats["refine_count"] == 0
        assert p.llm_small.calls == 0
        assert res.verification_confidence == 0.9

    def test_refinement_disabled(self):
        rag = FakeRag()
        p = _pipeline(rag, FakeVerifier(),
                      large_text="INITIAL ungrounded answer",
                      small_text="GROUNDED corrected answer",
                      enable_refinement=False)
        res = p.handle(RequestContext(user_question=_Q))
        assert p.stats["refine_count"] == 0
        assert p.llm_small.calls == 0
        assert res.verification_confidence == 0.3     # düşük kaldı

    def test_keeps_original_when_not_improved(self):
        # Düzeltme de GROUNDED değil → iyileşmez → orijinali koru.
        rag = FakeRag()
        p = _pipeline(rag, FakeVerifier(),
                      large_text="INITIAL ungrounded answer",
                      small_text="still ungrounded text")
        res = p.handle(RequestContext(user_question=_Q))
        assert p.stats["refine_count"] == 1
        assert p.llm_small.calls == 1                 # düzeltme denendi
        assert len(rag.calls) == 1                    # ama YENİDEN retrieval YOK
        assert res.verification_confidence == 0.3
        assert "INITIAL" in res.answer                # orijinal cevap korundu


class TestAnswerCache:
    """Aynı soru tekrar → 0 LLM/RAG call (exact-match answer cache)."""

    def test_repeat_question_is_cache_hit(self):
        rag = FakeRag()
        large = FakeLLM("GROUNDED cached answer")
        small = FakeLLM("unused")
        p = InfoPipeline(llm_small=small, llm_large=large, rag_builder=rag,
                         claim_verifier=None, enable_refinement=False)
        q = "ubuntu ssh nasıl sıkılaştırılır (cache testi)"
        r1 = p.handle(RequestContext(user_question=q))
        llm_after_first = large.calls + small.calls
        rag_after_first = len(rag.calls)
        assert llm_after_first >= 1 and rag_after_first >= 1   # ilk: gerçekten üretildi
        r2 = p.handle(RequestContext(user_question=q))         # aynı soru → cache HIT
        assert large.calls + small.calls == llm_after_first    # EK LLM call YOK
        assert len(rag.calls) == rag_after_first               # EK RAG YOK
        assert r2.answer == r1.answer
