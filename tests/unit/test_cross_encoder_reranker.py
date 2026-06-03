"""
CrossEncoderReranker birim testleri — AĞSIZ (sahte model inject, gerçek model İNDİRİLMEZ).

#1 (reranker): cross-encoder (query,chunk) çiftini birlikte skorlayıp daha isabetli sıralar.
Burada model mock'lanır → CI'da indirme/ağ yok; rerank MANTIĞI (yeniden sıralama, top_n, boş) test edilir.
"""
from __future__ import annotations

from rag.retrieval.reranker import CrossEncoderReranker, RerankedResult


class _FakeCE:
    """Sahte cross-encoder: query+chunk'ta 'ssh' eşleşiyorsa yüksek skor (deterministik)."""
    def predict(self, pairs):
        return [0.95 if "ssh" in text.lower() else 0.10 for (_q, text) in pairs]


def test_reorders_by_relevance_not_original_score():
    # UFW orijinal skoru YÜKSEK (0.9) ama SSH chunk soruyla daha alakalı → cross-encoder öne almalı
    cands = [
        {"id": "ufw", "text": "UFW firewall varsayılan deny", "score": 0.90, "metadata": {}},
        {"id": "ssh", "text": "SSH PermitRootLogin no ayarı", "score": 0.50, "metadata": {}},
    ]
    out = CrossEncoderReranker(model=_FakeCE()).rerank("ssh hardening", cands, top_n=2)
    assert isinstance(out[0], RerankedResult)
    assert out[0].id == "ssh"          # alakalı chunk öne geçti (orijinal skoru düşük olsa da)
    assert out[0].rank == 0 and out[0].mmr_score == 0.95
    assert out[1].id == "ufw"


def test_top_n_limit():
    cands = [{"id": str(i), "text": f"ssh kural {i}", "score": 0.5, "metadata": {}} for i in range(10)]
    out = CrossEncoderReranker(model=_FakeCE()).rerank("ssh", cands, top_n=3)
    assert len(out) == 3
    assert [r.rank for r in out] == [0, 1, 2]


def test_empty_candidates():
    assert CrossEncoderReranker(model=_FakeCE()).rerank("q", [], top_n=5) == []


def test_lazy_model_not_loaded_until_rerank():
    # model inject edilmezse İMPORT/INIT'te yüklenmez (lazy) — sadece rerank çağrısında
    r = CrossEncoderReranker()  # model=None
    assert r._model is None     # init'te yüklenmedi (indirme yok)
