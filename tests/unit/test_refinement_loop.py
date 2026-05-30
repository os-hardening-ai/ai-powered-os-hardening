"""
Tests for the answer-groundedness refinement loop (InfoPipeline._refine_answer).

When the verification confidence of the FIRST answer is below `refine_threshold`,
the pipeline reformulates the query, re-retrieves, regenerates, and re-verifies —
keeping the new answer ONLY if its confidence improved. One attempt (latency bound).

All fakes (no network/LLM): the verifier scores confidence from chunk content,
so we deterministically drive low→high (or low→still-low) transitions.
"""

from __future__ import annotations

import pytest

from llm.core.context import RequestContext
from llm.pipelines.layers import info_pipeline as ip_mod
from llm.pipelines.layers.info_pipeline import InfoPipeline
from rag.verify.claim_verifier import VerificationResult


class FakeLLM:
    """Her çağrıda artan numarayla cevap döner → hangi cevabın tutulduğu izlenebilir."""
    def __init__(self):
        self.calls = 0

    def __call__(self, prompt: str) -> str:
        self.calls += 1
        return f"ANSWER_{self.calls}"


class FakeRag:
    """retrieve_balanced: refined sorgu ('tam yapılandırma' içerir) iyi/zayıf chunk döndürür."""
    def __init__(self, refined_good: bool = True):
        self.refined_good = refined_good
        self.calls: list[str] = []

    def retrieve_balanced(self, query: str, **kw):
        self.calls.append(query)
        refined = "tam yapılandırma" in query
        if refined and self.refined_good:
            chunks = [{"text": "good rule one", "id": "r1", "metadata": {}},
                      {"text": "good rule two", "id": "r2", "metadata": {}}]
            return "CTX_REFINED", chunks
        # initial (veya refined-ama-hala-zayıf)
        chunks = [{"text": "weak ctx a", "id": "w1", "metadata": {}},
                  {"text": "weak ctx b", "id": "w2", "metadata": {}}]
        return "CTX_INITIAL", chunks


class FakeVerifier:
    """Confidence chunk içeriğinden: 'good' → 0.9 (geçerli), aksi 0.3 (düşük)."""
    def verify(self, answer, chunks):
        good = any("good" in c.get("text", "") for c in chunks)
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


def _pipeline(rag, verifier, enable_refinement=True, refine_threshold=0.55):
    return InfoPipeline(
        llm_small=FakeLLM(),
        llm_large=FakeLLM(),
        rag_builder=rag,
        claim_verifier=verifier,
        enable_refinement=enable_refinement,
        refine_threshold=refine_threshold,
    )


_Q = "ubuntu 24.04 ssh sshd_config sıkılaştırma adımları neler"


class TestRefinementTriggers:
    def test_low_confidence_triggers_refine_and_keeps_better(self):
        rag = FakeRag(refined_good=True)
        p = _pipeline(rag, FakeVerifier())
        res = p.handle(RequestContext(user_question=_Q))
        assert res.verification_confidence == 0.9        # düşük 0.3'ten yükseldi
        assert p.stats["refine_count"] == 1
        assert len(rag.calls) == 2                        # initial + refine retrieval
        assert res.answer.startswith("ANSWER_2")          # refined cevap tutuldu

    def test_high_initial_confidence_no_refine(self):
        # initial retrieval'i de 'good' yap → ilk confidence 0.9 → refine yok
        rag = FakeRag(refined_good=True)
        rag.retrieve_balanced = lambda q, **kw: (rag.calls.append(q) or (
            "CTX", [{"text": "good a", "id": "g1", "metadata": {}},
                    {"text": "good b", "id": "g2", "metadata": {}}]))
        p = _pipeline(rag, FakeVerifier())
        res = p.handle(RequestContext(user_question=_Q))
        assert res.verification_confidence == 0.9
        assert p.stats["refine_count"] == 0
        assert len(rag.calls) == 1                         # yalnız initial

    def test_refinement_disabled(self):
        rag = FakeRag(refined_good=True)
        p = _pipeline(rag, FakeVerifier(), enable_refinement=False)
        res = p.handle(RequestContext(user_question=_Q))
        assert res.verification_confidence == 0.3          # düşük kaldı
        assert p.stats["refine_count"] == 0
        assert len(rag.calls) == 1

    def test_keeps_original_when_not_improved(self):
        # refined retrieval da zayıf → yeni confidence iyileşmez → orijinali koru
        rag = FakeRag(refined_good=False)
        p = _pipeline(rag, FakeVerifier())
        res = p.handle(RequestContext(user_question=_Q))
        assert p.stats["refine_count"] == 1
        assert len(rag.calls) == 2
        assert res.answer.startswith("ANSWER_1")           # orijinal cevap korundu
        assert res.verification_confidence == 0.3


class TestReformulate:
    def test_reformulate_includes_question_and_hint(self):
        p = _pipeline(FakeRag(), FakeVerifier())
        out = p._reformulate("ssh nasıl güvenli", ["PermitRootLogin no olmalı"])
        assert "ssh nasıl güvenli" in out
        assert "PermitRootLogin" in out
        assert "tam yapılandırma" in out   # refined retrieval'i tetikleyen işaret

    def test_reformulate_no_unsupported(self):
        p = _pipeline(FakeRag(), FakeVerifier())
        out = p._reformulate("firewall ayarları", [])
        assert out.startswith("firewall ayarları")
        assert "CIS Benchmark" in out
