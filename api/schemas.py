from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RagSearchRequest(BaseModel):
    query: str = Field(..., description="Kullanıcının sorusu / arama cümlesi")
    top_k: int = Field(5, ge=1, le=20, description="Döndürülecek sonuç sayısı")
    source_id: str | None = Field(None, description="Opsiyonel source id filtresi")

class RagSearchResult(BaseModel):
    id: str
    score: float
    text: str
    metadata: Dict[str, Any]


class RagSearchResponse(BaseModel):
    query: str
    top_k: int
    results: List[RagSearchResult]
