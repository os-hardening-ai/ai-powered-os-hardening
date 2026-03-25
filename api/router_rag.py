import time
from fastapi import APIRouter, Depends
from api.schemas import RagSearchRequest, RagSearchResponse
from rag.retrieval.rag_retriever import RAGRetriever
from log_manager import get_logger

router = APIRouter()
_rag_logger = get_logger("rag_search")

def get_retriever() -> RAGRetriever:
    return RAGRetriever()


@router.post("/search", response_model=RagSearchResponse)
async def rag_search(
    payload: RagSearchRequest,
    retriever: RAGRetriever = Depends(get_retriever),
) -> RagSearchResponse:
    """
    Soru alır → embedding üretir → vector store'dan (Qdrant) top-k sonuçları döndürür.
    Varsayılan olarak late chunking ve min_score filtering kullanıyor.
    """
    
    lc = payload.late_chunking
    t0 = time.perf_counter()

    results = retriever.search(
        query=payload.query,
        top_k=payload.top_k,
        use_late_chunking=lc.enabled,
        coarse_k_factor=lc.coarse_k_factor,
        window_size=lc.window_size,
        stride=lc.stride,
        min_score=payload.min_score,
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
