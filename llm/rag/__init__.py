"""
RAG (Retrieval Augmented Generation) Module
============================================

CIS Benchmark document retrieval for context-aware responses.

## Features:

- Semantic search over CIS Benchmark PDFs
- Vector database integration (Qdrant/FAISS)
- Cohere embeddings
- Context relevance scoring
"""

try:
    from .integration import get_rag_context_builder, RAGContextBuilder
    RAG_AVAILABLE = True
except ImportError as e:
    RAG_AVAILABLE = False
    print(f"[WARNING] RAG not available: {e}")

    # Provide dummy implementations
    def get_rag_context_builder(*args, **kwargs):
        raise ImportError("RAG dependencies not installed")

    RAGContextBuilder = None

__all__ = [
    "get_rag_context_builder",
    "RAGContextBuilder",
    "RAG_AVAILABLE",
]
