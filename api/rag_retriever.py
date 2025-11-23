from __future__ import annotations

from typing import List

from core.embeddings import get_embedding_client
from core.vector_store import get_vector_store
from api.schemas import RagSearchResult


class RAGRetriever:
    """
    Sadece retrieval (top-k chunk getirme) yapan servis.
    Embedding provider + vector store, config.json üzerinden geliyor.
    """

    def __init__(self) -> None:
        self._embed_client = get_embedding_client()
        self._vector_store = get_vector_store()

    def search(self, query: str, top_k: int = 5) -> List[RagSearchResult]:
        # 1) Query'i embed et
        query_emb = self._embed_client.embed_query(query)

        # 2) Vector store'dan top-k sonuçları çek
        raw_results = self._vector_store.search(query_emb, top_k=top_k)

        # Beklenen şekil: {"score": float, "id": ..., "text": ..., "metadata": {...}}
        results: List[RagSearchResult] = []
        for r in raw_results:
            results.append(
                RagSearchResult(
                    id=str(r.get("id")),
                    score=float(r.get("score", 0.0)),
                    text=r.get("text", ""),
                    metadata=r.get("metadata", {}),
                )
            )
        return results
