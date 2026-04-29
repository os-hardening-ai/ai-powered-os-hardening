from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List

try:
    from rank_bm25 import BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:
    _BM25_AVAILABLE = False


@dataclass
class FusedResult:
    id: str
    text: str
    metadata: dict
    dense_score: float
    sparse_score: float
    fused_score: float


class InContextHybridScorer:
    """
    Re-scores already-retrieved candidates with BM25 and fuses via RRF.

    This is NOT full-corpus BM25 search — it works on the small candidate
    set returned by Qdrant (typically 20-40 chunks).  The benefit is exact
    keyword matching for CIS-specific tokens like /etc/ssh/sshd_config,
    PermitRootLogin, auditd, etc., which dense search can miss.

    Requires: pip install rank-bm25
    """

    def __init__(
        self,
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
        rrf_k: int = 60,
    ) -> None:
        if not _BM25_AVAILABLE:
            raise ImportError(
                "rank_bm25 not installed — run: pip install rank-bm25>=0.3.1"
            )
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.rrf_k = rrf_k

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        # Keep file paths, config keys, shell commands intact as single tokens
        return re.findall(r"[A-Za-z0-9_./\-]+", text.lower())

    def score(
        self,
        query: str,
        candidates: List[dict],
        top_n: int | None = None,
    ) -> List[FusedResult]:
        """
        Args:
            query: Original user query string.
            candidates: [{"id", "text", "metadata", "score"}] from Qdrant.
            top_n: Return only top_n results (None = return all, sorted).

        Returns:
            List of FusedResult ordered by fused_score descending.
        """
        if not candidates:
            return []

        corpus = [self._tokenize(c.get("text", "")) for c in candidates]
        bm25 = BM25Okapi(corpus)
        query_tokens = self._tokenize(query)
        bm25_scores = bm25.get_scores(query_tokens)

        # Compute RRF ranks
        dense_ranked = sorted(
            range(len(candidates)),
            key=lambda i: candidates[i].get("score", 0.0),
            reverse=True,
        )
        dense_rank = {idx: rank + 1 for rank, idx in enumerate(dense_ranked)}

        sparse_ranked = sorted(
            range(len(candidates)),
            key=lambda i: bm25_scores[i],
            reverse=True,
        )
        sparse_rank = {idx: rank + 1 for rank, idx in enumerate(sparse_ranked)}

        n = len(candidates) + 1
        results: List[FusedResult] = []
        for i, cand in enumerate(candidates):
            dr = dense_rank.get(i, n)
            sr = sparse_rank.get(i, n)
            fused = (
                self.dense_weight / (self.rrf_k + dr)
                + self.sparse_weight / (self.rrf_k + sr)
            )
            results.append(
                FusedResult(
                    id=str(cand.get("id", i)),
                    text=cand.get("text", ""),
                    metadata=cand.get("metadata", {}),
                    dense_score=float(cand.get("score", 0.0)),
                    sparse_score=float(bm25_scores[i]),
                    fused_score=fused,
                )
            )

        results.sort(key=lambda r: r.fused_score, reverse=True)
        if top_n is not None:
            results = results[:top_n]
        return results


def is_hybrid_available() -> bool:
    return _BM25_AVAILABLE
