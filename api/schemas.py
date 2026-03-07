from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from config.config_loader import get_config


class LateChunkingOptions(BaseModel):
    """
    Late chunking davranışını kontrol eden opsiyonlar.
    API katmanında tanımlı, core'a direkt bağımlı değil.
    """
    enabled: bool = Field(
        True,
        description="Late chunking aktif mi?"
    )
    coarse_k_factor: int = Field(
        3, ge=1, le=10,
        description="Top_k * factor kadar coarse sonuç çekilir (örn: top_k=5 → 15)."
    )
    window_size: int = Field(
        3, ge=1, le=10,
        description="Cümle penceresi boyutu (kaç cümle bir arada)."
    )
    stride: int = Field(
        1, ge=1, le=10,
        description="Kayma adımı (stride)."
    )

def late_chunking_default() -> LateChunkingOptions:
    cfg = get_config()
    lc = getattr(cfg.rag, "late_chunking", None)

    if lc is None:
        return LateChunkingOptions()

    if hasattr(lc, "model_dump"):
        data = lc.model_dump()
    elif isinstance(lc, dict):
        data = lc
    else:
        data = {}

    return LateChunkingOptions.model_validate(data)


class RagSearchRequest(BaseModel):
    query: str = Field(..., description="Kullanıcının sorusu / arama cümlesi")
    top_k: int = Field(5, ge=1, le=20, description="Döndürülecek sonuç sayısı")
    source_id: str | None = Field(None, description="Opsiyonel source id filtresi")
    min_score: float = Field(0.3, ge=0.0, le=1.0, description="Minimum relevance score threshold (default: 0.3)")
    late_chunking: LateChunkingOptions = Field(
        default_factory=late_chunking_default,  
        description="Late chunking yapılandırması"
    )

class RagSearchResult(BaseModel):
    id: str
    score: float
    text: str
    metadata: Dict[str, Any]


class RagSearchResponse(BaseModel):
    query: str
    top_k: int
    results: List[RagSearchResult]
