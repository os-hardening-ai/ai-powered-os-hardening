from __future__ import annotations
from fastapi import APIRouter
from log_manager import get_logger

router = APIRouter()
_health_logger = get_logger("health")


@router.get("/", tags=["health"])
async def root() -> dict:
    return {"message": "AI-Powered OS Hardening API", "docs": "/docs"}


@router.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok"}


@router.get("/health/detailed", tags=["health"])
async def health_detailed() -> dict:
    """Bileşen bazlı sağlık durumu."""
    components: dict[str, str] = {}

    # RAG bağlantısı
    try:
        from rag.vector_store import get_vector_store
        get_vector_store()
        components["vector_store"] = "ok"
    except Exception as e:
        components["vector_store"] = f"error: {e}"

    # Embedding client
    try:
        from rag.embeddings import get_embedding_client
        get_embedding_client()
        components["embedding"] = "ok"
    except Exception as e:
        components["embedding"] = f"error: {e}"

    # LLM client (Groq)
    try:
        from llm.clients import get_llm_clients
        get_llm_clients()
        components["llm"] = "ok"
    except Exception as e:
        components["llm"] = f"error: {e}"

    overall = "ok" if all(v == "ok" for v in components.values()) else "degraded"
    _health_logger.info(f"status={overall} components={components}")
    return {"status": overall, "components": components}
