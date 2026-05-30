import asyncio
import threading
import time
from fastapi import APIRouter
from api.schemas import RagSearchRequest, RagSearchResponse
from api.errors import APIError, ErrorCode, raise_internal_error
from rag.retrieval.rag_retriever import RAGRetriever
from log_manager import get_logger

router = APIRouter()
_rag_logger = get_logger("rag_search")

# Retriever artık istek başına yeniden kurulmuyor — thread-safe lazy singleton.
_retriever = None
_retriever_lock = threading.Lock()
_SEARCH_TIMEOUT_S = 30


def get_retriever() -> RAGRetriever:
    global _retriever
    if _retriever is None:
        with _retriever_lock:
            if _retriever is None:  # double-checked locking
                _retriever = RAGRetriever()
    return _retriever


@router.post("/search", response_model=RagSearchResponse)
async def rag_search(payload: RagSearchRequest) -> RagSearchResponse:
    """
    Soru alır → embedding üretir → vector store'dan (Qdrant) top-k sonuçları döndürür.
    Varsayılan olarak late chunking ve min_score filtering kullanıyor.

    Güvenilirlik: arama timeout ile sınırlanır; Qdrant/embedding erişilemezse
    500 değil, anlamlı 503/504 döner.
    """
    lc = payload.late_chunking
    t0 = time.perf_counter()

    try:
        retriever = get_retriever()
        # Bloklayan IO (embedding + Qdrant) — thread + timeout ile sınırla.
        results = await asyncio.wait_for(
            asyncio.to_thread(
                retriever.search,
                query=payload.query,
                top_k=payload.top_k,
                use_late_chunking=lc.enabled,
                coarse_k_factor=lc.coarse_k_factor,
                window_size=lc.window_size,
                stride=lc.stride,
                min_score=payload.min_score,
            ),
            timeout=_SEARCH_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        raise APIError(
            status_code=504, error_code=ErrorCode.TIMEOUT,
            message="RAG search timed out. Try a simpler query or retry later.",
            details={"timeout_s": _SEARCH_TIMEOUT_S},
        )
    except APIError:
        raise
    except Exception as exc:
        # Qdrant/embedding servisi erişilemez → 503 (graceful), 500/crash değil.
        raise_internal_error(
            "rag_search", exc,
            error_code=ErrorCode.SERVICE_UNAVAILABLE, status_code=503,
        )

    elapsed_s = time.perf_counter() - t0
    scores = [round(r.score, 4) for r in results]
    top_score = max(scores) if scores else 0.0

    yaml_count = sum(1 for r in results if r.metadata.get("doc_type") == "yaml_rule")
    pdf_count  = sum(1 for r in results if r.metadata.get("doc_type") == "cis_benchmark")

    _rag_logger.info(
        f"query=\"{payload.query}\" top_k={payload.top_k} min_score={payload.min_score} "
        f"late_chunking={lc.enabled} results={len(results)} "
        f"yaml={yaml_count} pdf={pdf_count} top_score={top_score} elapsed={elapsed_s:.3f}s"
    )

    return RagSearchResponse(
        query=payload.query,
        top_k_per_source=payload.top_k,
        total_returned=len(results),
        yaml_count=yaml_count,
        pdf_count=pdf_count,
        results=results,
    )
