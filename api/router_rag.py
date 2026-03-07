from fastapi import APIRouter, Depends
from api.schemas import RagSearchRequest, RagSearchResponse
from core.retrieval.rag_retriever import RAGRetriever

router = APIRouter()

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

    results = retriever.search(
        query=payload.query,
        top_k=payload.top_k,
        use_late_chunking=lc.enabled,
        coarse_k_factor=lc.coarse_k_factor,
        window_size=lc.window_size,
        stride=lc.stride,
        min_score=payload.min_score,
    )

    return RagSearchResponse(
        query=payload.query,
        top_k=payload.top_k,
        results=results,
    )
