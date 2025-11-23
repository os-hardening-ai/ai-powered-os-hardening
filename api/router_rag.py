from __future__ import annotations

from fastapi import APIRouter, Depends
from api.schemas import RagSearchRequest, RagSearchResponse
from api.rag_retriever import RAGRetriever

router = APIRouter()

def get_retriever() -> RAGRetriever:
    # Şimdilik basit; istersek ileride dependency injection / caching ekleyebiliriz.
    # Eğer tek instance kullanmak istersen, main.py’de global bir retriever yaratıp
    # buraya oradan da referans geçebiliriz.
    return RAGRetriever()

@router.post("/search", response_model=RagSearchResponse)
async def rag_search(
    payload: RagSearchRequest,
    retriever: RAGRetriever = Depends(get_retriever),
) -> RagSearchResponse:
    """
    Soru alır → embedding üretir → vector store'dan (Qdrant) top-k sonuçları döndürür.
    Şimdilik LLM yok, sadece retrieval testi için.
    """
    results = retriever.search(query=payload.query, top_k=payload.top_k)
    return RagSearchResponse(
        query=payload.query,
        top_k=payload.top_k,
        results=results,
    )
