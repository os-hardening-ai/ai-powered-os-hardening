from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List


@dataclass
class RerankedResult:
    id: str
    text: str
    metadata: dict
    original_score: float
    mmr_score: float
    rank: int


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9_./\-]+", text.lower()))


def _jaccard(tokens_a: set[str], tokens_b: set[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


class MMRReranker:
    """
    Maximal Marginal Relevance reranker.

    Uses Qdrant cosine similarity scores for relevance and Jaccard token
    similarity for diversity — no extra embedding API calls needed.

    Prevents the LLM context window from being filled with near-duplicate
    chunks (common when the same CIS section appears in both PDF + YAML).
    """

    def __init__(
        self,
        lambda_param: float = 0.7,
        max_per_source: int = 3,
    ) -> None:
        self.lam = lambda_param
        self.max_per_source = max_per_source

    def rerank(
        self,
        candidates: List[dict],
        top_n: int = 5,
    ) -> List[RerankedResult]:
        """
        Args:
            candidates: [{"id", "text", "metadata", "score"}] — score is
                        the Qdrant cosine similarity (higher = more relevant).
            top_n: Number of results to return.

        Returns:
            List of RerankedResult ordered by MMR score.
        """
        if not candidates:
            return []

        n = len(candidates)
        relevance = [float(c.get("score", 0.0)) for c in candidates]
        token_sets = [_tokenize(c.get("text", "")) for c in candidates]

        selected_idx: list[int] = []
        remaining = list(range(n))
        source_counts: dict[str, int] = {}

        while remaining and len(selected_idx) < top_n:
            best_score = -1.0
            best_i: int | None = None

            for i in remaining:
                src = str(candidates[i].get("metadata", {}).get("source_id", "unknown"))
                if source_counts.get(src, 0) >= self.max_per_source:
                    continue

                if not selected_idx:
                    mmr = relevance[i]
                else:
                    max_sim = max(
                        _jaccard(token_sets[i], token_sets[j]) for j in selected_idx
                    )
                    mmr = self.lam * relevance[i] - (1 - self.lam) * max_sim

                if mmr > best_score:
                    best_score = mmr
                    best_i = i

            if best_i is None:
                # All sources capped — pick highest relevance from remaining
                best_i = max(remaining, key=lambda i: relevance[i])

            selected_idx.append(best_i)
            remaining.remove(best_i)
            src = str(candidates[best_i].get("metadata", {}).get("source_id", "unknown"))
            source_counts[src] = source_counts.get(src, 0) + 1

        return [
            RerankedResult(
                id=str(candidates[i].get("id", i)),
                text=candidates[i].get("text", ""),
                metadata=candidates[i].get("metadata", {}),
                original_score=float(candidates[i].get("score", 0.0)),
                mmr_score=relevance[i],
                rank=rank,
            )
            for rank, i in enumerate(selected_idx)
        ]


class CrossEncoderReranker:
    """Cross-encoder reranker — (query, chunk) çiftini BİRLİKTE skorlar.

    Bi-encoder (embedding) araması anlamı yakalar ama query-chunk etkileşimini göremez;
    cross-encoder ikisini birlikte değerlendirir → daha isabetli relevance sıralaması.
    En iyi desen: GENİŞ aday çek (top-20) → cross-encoder ile rerank → top-k LLM'e.
    Araştırma (Databricks): reranking halüsinasyonu ~%35 azaltır → İP-5 groundedness'e doğrudan katkı.

    Model LAZY yüklenir (ilk rerank'ta) → import/CI maliyeti yok; test için `model` inject edilir
    (indirme olmaz). Çok dilli varsayılan (TR sorgu + EN CIS): mmarco-mMiniLMv2.

    DURUM: DEFAULT KAPALI. RAG retrieval (Engin) `use_cross_encoder` toggle'ı + model deploy ile
    etkinleştirilir (ops adımı — model ağırlığı ~100-500MB, ilk çağrıda indirilir/cache'lenir).
    """

    def __init__(self, model_name: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", model=None) -> None:
        self._model_name = model_name
        self._model = model  # test/inject için; None ise lazy yüklenir

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder  # lazy import (ağır)
            self._model = CrossEncoder(self._model_name)
        return self._model

    def rerank(self, query: str, candidates: List[dict], top_n: int = 5) -> List[RerankedResult]:
        """(query, chunk) çiftlerini skorla → en yüksek top_n'i sıralı döndür."""
        if not candidates:
            return []
        model = self._ensure_model()
        pairs = [(query, c.get("text", "")) for c in candidates]
        scores = [float(s) for s in model.predict(pairs)]
        order = sorted(range(len(candidates)), key=lambda i: -scores[i])[:top_n]
        return [
            RerankedResult(
                id=str(candidates[i].get("id", i)),
                text=candidates[i].get("text", ""),
                metadata=candidates[i].get("metadata", {}),
                original_score=float(candidates[i].get("score", 0.0)),
                mmr_score=scores[i],   # cross-encoder relevance skoru
                rank=rank,
            )
            for rank, i in enumerate(order)
        ]
