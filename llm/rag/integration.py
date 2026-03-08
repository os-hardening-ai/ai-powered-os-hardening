# rag_integration.py
"""
RAG Retrieval ile LLM Pipeline entegrasyonu.
CIS benchmark dokümanlarından ilgili bilgileri getirip LLM'e context olarak sunar.
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple

try:
    from rag.embeddings import get_embedding_client
    from rag.vector_store import get_vector_store
    RAG_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] Could not import RAG dependencies: {e}")
    print("[WARNING] RAG functionality will be limited")
    get_embedding_client = None  # type: ignore
    get_vector_store = None  # type: ignore
    RAG_AVAILABLE = False


class RAGContextBuilder:
    """
    RAG sistemi ile LLM pipeline arasında köprü.
    Kullanıcı sorusuna göre ilgili doküman chunk'larını getirir.
    """

    def __init__(self, top_k: int = 5, min_score: float = 0.5):
        """
        Args:
            top_k: Kaç tane chunk getirileceği
            min_score: Minimum relevance score (altındakiler filtrelenir)
        """
        self.top_k = top_k
        self.min_score = min_score

        if get_embedding_client is None or get_vector_store is None:
            raise RuntimeError("RAG dependencies not available. Check core.embeddings and core.vector_store imports")

        self._embed_client = get_embedding_client()
        self._vector_store = get_vector_store()

    def _search(self, query: str) -> List[Dict[str, Any]]:
        """Embed query once and return score-filtered results."""
        print(f"[RAG._search] Embedding query: '{query[:60]}'")
        query_emb = self._embed_client.embed_query(query)
        print(f"[RAG._search] Searching vector store (top_k={self.top_k})...")
        raw_results = self._vector_store.search(query_emb, top_k=self.top_k)
        scores = [round(r.get("score", 0), 3) for r in raw_results]
        print(f"[RAG._search] Raw scores: {scores}")
        filtered = [r for r in raw_results if r.get("score", 0.0) >= self.min_score]
        print(f"[RAG._search] {len(raw_results)} results, {len(filtered)} pass min_score={self.min_score}")
        for r in filtered:
            print(f"  score={r.get('score', 0):.3f} | {str(r.get('metadata', {}))[:80]}")
        return filtered

    def _format_context(self, filtered_results: List[Dict[str, Any]]) -> str:
        """Format filtered results into LLM-ready context string."""
        context_parts = []
        for idx, result in enumerate(filtered_results, start=1):
            text = result.get("text", "").strip()
            score = result.get("score", 0.0)
            metadata = result.get("metadata", {})

            source = metadata.get("benchmark_product") or metadata.get("source_id") or "CIS Benchmark"
            section_id = metadata.get("section_id") or ""
            section_title = metadata.get("section_title") or ""
            if section_id and section_title:
                section = f"{section_id} - {section_title}"
            elif section_id:
                section = section_id
            elif section_title:
                section = section_title
            else:
                section = "N/A"

            context_parts.append(
                f"[Kaynak {idx}] (Relevance: {score:.2f})\n"
                f"Doküman: {source}\n"
                f"Bölüm: {section}\n"
                f"İçerik:\n{text}\n"
            )

        return "\n" + "="*60 + "\n" + "\n".join(context_parts) + "="*60 + "\n"

    def retrieve_all(self, query: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Tek embed çağrısıyla hem context string hem raw results döndürür.

        Args:
            query: Kullanıcı sorusu

        Returns:
            (context_str, raw_results) tuple
        """
        try:
            print(f"[RAG.retrieve_all] START — query='{query[:60]}'")
            filtered = self._search(query)
            if not filtered:
                print("[RAG.retrieve_all] No results passed score threshold → fallback")
                return self._get_fallback_message(), []
            context = self._format_context(filtered)
            print(f"[RAG.retrieve_all] OK — {len(filtered)} sources, context_len={len(context)}")
            return context, filtered
        except Exception as e:
            print(f"[RAG.retrieve_all] ERROR: {e}")
            return self._get_fallback_message(), []

    def retrieve_context(self, query: str) -> str:
        """Formatted context string döndürür (LLM prompt'una eklenecek)."""
        context, _ = self.retrieve_all(query)
        return context

    def retrieve_raw(self, query: str) -> List[Dict[str, Any]]:
        """Raw retrieval results döndürür (API response için)."""
        _, raw = self.retrieve_all(query)
        return raw

    def _get_fallback_message(self) -> str:
        """
        RAG retrieval başarısız olduğunda fallback message.
        """
        return (
            "\n[NOT: İlgili CIS benchmark dokümanı bulunamadı. "
            "Genel bilgilerle cevap verilecek.]\n"
        )


# Singleton instance (optional)
_rag_builder: RAGContextBuilder | None = None


def get_rag_context_builder(
    top_k: int = 5,
    min_score: float = 0.7
) -> RAGContextBuilder:
    """
    Global RAGContextBuilder instance döndürür (singleton pattern).

    Args:
        top_k: Kaç chunk getirileceği
        min_score: Minimum score threshold

    Returns:
        RAGContextBuilder instance
    """
    global _rag_builder

    if _rag_builder is None:
        _rag_builder = RAGContextBuilder(top_k=top_k, min_score=min_score)

    return _rag_builder
