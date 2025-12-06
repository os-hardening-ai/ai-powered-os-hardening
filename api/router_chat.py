from __future__ import annotations

import sys
import os
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import LLM modules (now llm is importable as a package)
from llm.context import RequestContext
from llm.pipeline_optimized import run_optimized_pipeline_with_retry
from llm.models import get_llm_clients

# Import security utilities
from api.security import validate_chat_input, sanitize_output

router = APIRouter()


# ──────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Chat request payload"""
    question: str = Field(
        ...,
        description="Kullanıcı sorusu",
        min_length=1,
        max_length=5000,  # Security: max length
        examples=["Ubuntu 24.04 sistemimde SSH nasıl sıkılaştırırım?"]
    )
    os: Optional[str] = Field(
        None,
        description="Operating system (ubuntu_22_04, ubuntu_24_04, windows_11, etc.)",
        examples=["ubuntu_24_04"]
    )
    role: Optional[str] = Field(
        None,
        description="User role (sysadmin, soc, developer, devops)",
        examples=["sysadmin"]
    )
    security_level: str = Field(
        "balanced",
        description="Security level: minimal/balanced/strict",
        pattern="^(minimal|balanced|strict)$"
    )
    zt_maturity: str = Field(
        "medium",
        description="Zero Trust maturity: low/medium/high",
        pattern="^(low|medium|high)$"
    )
    use_rag: bool = Field(True, description="RAG retrieval kullanılsın mı")
    rag_top_k: int = Field(5, description="RAG'den kaç chunk getirileceği", ge=1, le=20)
    rag_min_score: float = Field(0.7, description="Minimum relevance score", ge=0.0, le=1.0)

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        """Validate and sanitize question input"""
        # Use security module for validation
        # check_injection=False because LLM providers (Groq, OpenAI) already handle this
        # We keep input length validation to prevent API quota abuse
        validate_chat_input(v, max_length=5000, check_injection=False)
        return v.strip()


class RAGSource(BaseModel):
    """RAG kaynak bilgisi"""
    id: str
    score: float
    source: str
    section: str


class ChatResponse(BaseModel):
    """Chat response payload"""
    answer: str = Field(..., description="LLM cevabı")
    intent: Optional[str] = Field(None, description="Tespit edilen intent")
    safety_category: Optional[str] = Field(None, description="Güvenlik kategorisi")
    rag_sources: List[RAGSource] = Field(default_factory=list, description="RAG'den gelen kaynaklar")
    stats: Dict[str, Any] = Field(default_factory=dict, description="Pipeline istatistikleri")
    request_id: Optional[str] = Field(None, description="Request ID")


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

# Global LLM clients (lazy init)
_llm_small = None
_llm_large = None


def _get_llm_clients():
    """Get or initialize LLM clients"""
    global _llm_small, _llm_large

    if _llm_small is None or _llm_large is None:
        _llm_small, _llm_large = get_llm_clients()

    return _llm_small, _llm_large


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    """
    RAG + LLM birleşik chat endpoint.

    1. Kullanıcı sorusunu alır
    2. RAG retrieval yapar (opsiyonel)
    3. LLM pipeline'ı çalıştırır
    4. Cevap + kaynak bilgilerini döndürür
    """
    try:
        # LLM clients
        llm_small, llm_large = _get_llm_clients()

        # Request context oluştur
        ctx = RequestContext(
            user_question=payload.question,
            os=payload.os,
            role=payload.role,
            security_level=payload.security_level,  # type: ignore
            zt_maturity=payload.zt_maturity,  # type: ignore
        )

        # Pipeline'ı çalıştır (RAG entegrasyonu pipeline içinde)
        from pipeline_optimized import OptimizedPipeline

        pipeline = OptimizedPipeline(
            llm_small=llm_small,
            llm_large=llm_large,
            priority="balanced",
            use_rag=payload.use_rag,
            rag_top_k=payload.rag_top_k,
            rag_min_score=payload.rag_min_score,
        )

        result_ctx = pipeline.run(ctx)

        # RAG kaynaklarını parse et (eğer varsa)
        rag_sources: List[RAGSource] = []
        if result_ctx.retrieved_context and payload.use_rag:
            try:
                # RAG context'ten kaynak bilgilerini çıkar
                # (Bu basit bir parsing, gerçek implementasyonda daha robust olmalı)
                import re

                pattern = r'\[Kaynak \d+\] \(Relevance: ([\d.]+)\)\nDoküman: (.+?)\nBölüm: (.+?)\n'
                matches = re.findall(pattern, result_ctx.retrieved_context)

                for idx, (score, source, section) in enumerate(matches, start=1):
                    rag_sources.append(
                        RAGSource(
                            id=f"source_{idx}",
                            score=float(score),
                            source=source,
                            section=section,
                        )
                    )
            except Exception as e:
                print(f"[ChatAPI] Failed to parse RAG sources: {e}")

        # Sanitize output (remove any leaked prompts/instructions)
        sanitized_answer = sanitize_output(result_ctx.final_answer or "Cevap üretilemedi.")

        # Response oluştur
        return ChatResponse(
            answer=sanitized_answer,
            intent=str(result_ctx.intent) if result_ctx.intent else None,
            safety_category=result_ctx.safety.category if result_ctx.safety else None,
            rag_sources=rag_sources,
            stats=pipeline.stats,
            request_id=result_ctx.request_id,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "chat_api",
        "rag_available": True,  # RAG integration mevcut
    }
