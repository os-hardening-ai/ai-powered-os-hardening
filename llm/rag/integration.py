# rag_integration.py
"""
RAG Retrieval ile LLM Pipeline entegrasyonu.
CIS benchmark dokümanlarından ilgili bilgileri getirip LLM'e context olarak sunar.
"""

from __future__ import annotations
from typing import List, Dict, Any
import sys
import os

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from core.embeddings import get_embedding_client
    from core.vector_store import get_vector_store
except ImportError as e:
    print(f"[WARNING] Could not import RAG dependencies: {e}")
    print("[WARNING] RAG functionality will be limited")
    get_embedding_client = None  # type: ignore
    get_vector_store = None  # type: ignore


class RAGContextBuilder:
    """
    RAG sistemi ile LLM pipeline arasında köprü.
    Kullanıcı sorusuna göre ilgili doküman chunk'larını getirir.
    """

    def __init__(self, top_k: int = 5, min_score: float = 0.7):
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

    def retrieve_context(self, query: str) -> str:
        """
        Query için RAG retrieval yapar ve LLM'e uygun context string döndürür.

        Args:
            query: Kullanıcı sorusu

        Returns:
            Formatted context string (LLM prompt'una eklenecek)
        """
        try:
            # 1) Query'i embed et
            query_emb = self._embed_client.embed_query(query)

            # 2) Vector store'dan top-k sonuçları çek
            raw_results = self._vector_store.search(query_emb, top_k=self.top_k)

            # 3) Score filtreleme
            filtered_results = [
                r for r in raw_results
                if r.get("score", 0.0) >= self.min_score
            ]

            if not filtered_results:
                return self._get_fallback_message()

            # 4) Context string oluştur
            context_parts = []

            for idx, result in enumerate(filtered_results, start=1):
                text = result.get("text", "").strip()
                score = result.get("score", 0.0)
                metadata = result.get("metadata", {})

                # Metadata'dan useful info çıkar
                source = metadata.get("source", "CIS Benchmark")
                section = metadata.get("section", "N/A")

                context_parts.append(
                    f"[Kaynak {idx}] (Relevance: {score:.2f})\n"
                    f"Doküman: {source}\n"
                    f"Bölüm: {section}\n"
                    f"İçerik:\n{text}\n"
                )

            context = "\n" + "="*60 + "\n" + "\n".join(context_parts) + "="*60 + "\n"

            return context

        except Exception as e:
            print(f"[RAGContextBuilder] Error during retrieval: {e}")
            return self._get_fallback_message()

    def retrieve_raw(self, query: str) -> List[Dict[str, Any]]:
        """
        Raw retrieval results döndürür (API response için).

        Args:
            query: Kullanıcı sorusu

        Returns:
            List of result dicts
        """
        try:
            query_emb = self._embed_client.embed_query(query)
            raw_results = self._vector_store.search(query_emb, top_k=self.top_k)

            # Score filtreleme
            filtered = [
                r for r in raw_results
                if r.get("score", 0.0) >= self.min_score
            ]

            return filtered

        except Exception as e:
            print(f"[RAGContextBuilder] Error during raw retrieval: {e}")
            return []

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


# ─────────────────────────────────────────────
# Test Code
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Test RAG context builder
    builder = get_rag_context_builder(top_k=3, min_score=0.7)

    test_queries = [
        "SSH hardening nasıl yapılır?",
        "Firewall konfigürasyonu nedir?",
        "Password policy önerileri",
    ]

    print("=" * 70)
    print("RAG CONTEXT BUILDER TEST")
    print("=" * 70)

    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 70)

        context = builder.retrieve_context(query)
        print(context)
        print()
