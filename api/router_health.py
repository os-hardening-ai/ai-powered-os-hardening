from __future__ import annotations
import asyncio
import os
from fastapi import APIRouter
from log_manager import get_logger

router = APIRouter()
_health_logger = get_logger("health")


@router.get("/", tags=["health"])
async def root() -> dict:
    return {"message": "AI-Powered OS Hardening API", "docs": "/docs"}


@router.get("/health", tags=["health"])
async def health_check() -> dict:
    """Gerçek bağımlılık kontrolü: Qdrant, LLM, Redis ping.

    Her zaman 200 döner. Kritik bağımlılık başarısızsa status='degraded'.
    """
    dependencies: dict[str, str] = {}
    rag_available = False

    # Qdrant — cached store üzerinden hafif ping
    try:
        from rag.vector_store import get_vector_store
        vs = get_vector_store()
        # Gerçek ağ çağrısı: mevcut collection'ı sorgula
        await asyncio.wait_for(
            asyncio.to_thread(vs._client.get_collection, vs._collection),
            timeout=5.0,
        )
        dependencies["qdrant"] = "ok"
        rag_available = True
    except Exception:
        dependencies["qdrant"] = "error"

    # LLM — client init (provider API key varlığını doğrular)
    try:
        from llm.clients import get_llm_clients
        get_llm_clients()
        dependencies["llm"] = "ok"
    except Exception:
        dependencies["llm"] = "error"

    # Redis — ping with short timeout
    try:
        redis_url = os.environ.get("REDIS_URL", "")
        if redis_url:
            import redis as _redis
            _r = _redis.from_url(redis_url, socket_connect_timeout=2)
            await asyncio.wait_for(asyncio.to_thread(_r.ping), timeout=3.0)
            dependencies["redis"] = "ok"
        else:
            dependencies["redis"] = "disabled"
    except Exception:
        dependencies["redis"] = "error"

    overall = "ok" if all(v in ("ok", "disabled") for v in dependencies.values()) else "degraded"
    _health_logger.info("status=%s deps=%s", overall, dependencies)
    return {"status": overall, "rag_available": rag_available, "dependencies": dependencies}


@router.get("/ready", tags=["health"])
async def readiness() -> dict:
    """Hafif hazır-olma kontrolü (load balancer / k8s readiness probe için).

    Ağır bağımlılık I/O'su YOK — süreç ayağa kalktıysa hızlıca 200 döner.
    Derin bağımlılık kontrolü için /health veya /health/detailed kullanın."""
    return {"status": "ready"}


@router.get("/health/detailed", tags=["health"])
async def health_detailed() -> dict:
    """Bileşen bazlı sağlık durumu (embedding dahil)."""
    components: dict[str, str] = {}

    try:
        from rag.vector_store import get_vector_store
        get_vector_store()
        components["vector_store"] = "ok"
    except Exception as e:
        components["vector_store"] = f"error: {e}"

    try:
        from rag.embeddings import get_embedding_client
        get_embedding_client()
        components["embedding"] = "ok"
    except Exception as e:
        components["embedding"] = f"error: {e}"

    try:
        from llm.clients import get_llm_clients
        get_llm_clients()
        components["llm"] = "ok"
    except Exception as e:
        components["llm"] = f"error: {e}"

    overall = "ok" if all(v == "ok" for v in components.values()) else "degraded"
    _health_logger.info("status=%s components=%s", overall, components)
    return {"status": overall, "components": components}
