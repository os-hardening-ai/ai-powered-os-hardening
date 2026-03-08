from __future__ import annotations

import asyncio
from typing import Optional, List, Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from llm.core.context import RequestContext
from llm.pipelines.secure_v2 import SecurePipelineV2
from llm.clients import get_llm_clients
from llm.rag.integration import RAGContextBuilder

# Import security utilities
from api.security import validate_chat_input, sanitize_output

# Import error handling
from api.errors import APIError, ErrorCode

# Import streaming support
from api.streaming import stream_chat_response

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
        pattern="^(minimal|balanced|strict)$",
        examples=["balanced"]
    )
    zt_maturity: str = Field(
        "medium",
        description="Zero Trust maturity: low/medium/high",
        pattern="^(low|medium|high)$",
        examples=["medium"]
    )
    use_rag: bool = Field(True, description="RAG retrieval kullanılsın mı", examples=[True])
    rag_top_k: int = Field(5, description="RAG'den kaç chunk getirileceği", ge=1, le=20, examples=[5])
    rag_min_score: float = Field(0.7, description="Minimum relevance score", ge=0.0, le=1.0, examples=[0.7])
    stream: bool = Field(False, description="Enable streaming response (SSE)", examples=[False])
    timeout: Optional[int] = Field(60, description="Request timeout in seconds (default: 60s, max: 300s)", ge=1, le=300, examples=[60])

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        """Validate and sanitize question input"""
        # Use security module for validation
        # check_injection=False because LLM providers (Groq, OpenAI) already handle this
        # We keep input length validation to prevent API quota abuse
        is_valid, error_message = validate_chat_input(v, max_length=5000, check_injection=False)
        if not is_valid:
            raise ValueError(error_message)
        return v.strip()


class RAGSource(BaseModel):
    """RAG kaynak bilgisi"""
    id: str
    score: float
    source: str
    section: str


class ChatResponse(BaseModel):
    """Chat response payload"""
    answer: str = Field(..., description="LLM cevabi")
    intent: Optional[str] = Field(None, description="Tespit edilen intent")
    safety_category: Optional[str] = Field(None, description="Guvenlik kategorisi")
    layer_path: Optional[str] = Field(None, description="Pipeline katman yolu (1->2->3A gibi)")
    rag_sources: List[RAGSource] = Field(default_factory=list, description="RAG'den gelen kaynaklar")
    stats: Dict[str, Any] = Field(default_factory=dict, description="Pipeline istatistikleri")
    request_id: Optional[str] = Field(None, description="Request ID")
    estimated_cost: Optional[float] = Field(None, description="Tahmini maliyet ($)")


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
    RAG + LLM birlesik chat endpoint (4-Layer Security Pipeline).

    Layer 1: Safety Classification
    Layer 2: Intent Detection
    Layer 3: Routing (Pattern/Info/Action/Out-of-Scope)
    Layer 4: Generation

    1. Kullanici sorusunu alir
    2. Guvenlik kontrolu yapar
    3. Intent tespit eder
    4. Uygun pipeline'a yonlendirir
    5. Cevap + kaynak bilgilerini dondurur
    """
    # Set timeout (default: 60s for complex RAG queries)
    timeout_seconds = payload.timeout or 60

    try:
        # LLM clients
        llm_small, llm_large = _get_llm_clients()

        # Request context olustur
        ctx = RequestContext(
            user_question=payload.question,
            os=payload.os,
            role=payload.role,
            security_level=payload.security_level,  # type: ignore
            zt_maturity=payload.zt_maturity,  # type: ignore
        )

        # RAG builder — sadece use_rag=True ise baslat
        rag_builder = None
        if payload.use_rag:
            try:
                rag_builder = RAGContextBuilder(
                    top_k=payload.rag_top_k,
                    min_score=payload.rag_min_score,
                )
            except Exception as e:
                print(f"[ChatAPI] RAG init failed, devam ediliyor: {e}")

        # Pipeline'i calistir (4-layer security pipeline)
        pipeline = SecurePipelineV2(
            llm_ultra_fast=llm_small,
            llm_small=llm_small,
            llm_large=llm_large,
            rag_builder=rag_builder,
            debug=False,
        )

        # Run with timeout
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(pipeline.run, ctx),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            raise APIError(
                status_code=504,
                error_code=ErrorCode.TIMEOUT,
                message=f"Request timeout after {timeout_seconds} seconds. Try a simpler query or increase timeout.",
                details={"timeout": timeout_seconds, "suggestion": "increase_timeout_or_simplify_query"}
            )

        # RAG kaynaklarini parse et (eger varsa - metadata'dan)
        rag_sources: List[RAGSource] = []
        if result.metadata and "rag_sources" in result.metadata:
            try:
                for idx, source_data in enumerate(result.metadata["rag_sources"], start=1):
                    rag_sources.append(
                        RAGSource(
                            id=f"source_{idx}",
                            score=source_data.get("score", 0.0),
                            source=source_data.get("source", "Unknown"),
                            section=source_data.get("section", "Unknown"),
                        )
                    )
            except Exception as e:
                print(f"[ChatAPI] Failed to parse RAG sources: {e}")

        # Sanitize output (remove any leaked prompts/instructions)
        sanitized_answer = sanitize_output(result.answer or "Cevap uretilemedi.")

        # Response olustur
        return ChatResponse(
            answer=sanitized_answer,
            intent=result.intent.type if result.intent else None,
            safety_category=result.safety.category if result.safety else None,
            layer_path=result.layer_path,
            rag_sources=rag_sources,
            stats={
                "total_time_s": result.total_time_s,
                "layer_path": result.layer_path,
            },
            request_id=ctx.request_id,
            estimated_cost=result.estimated_cost,
        )

    except Exception as e:
        # Use standardized error handling
        raise APIError(
            status_code=500,
            error_code=ErrorCode.PIPELINE_ERROR,
            message=f"Pipeline execution failed: {str(e)}",
            details={"stage": "pipeline_execution"}
        )


@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest):
    """
    Streaming version of /chat endpoint using Server-Sent Events (SSE).

    Returns token-by-token streaming response for better user experience.

    Response format (SSE):
        event: metadata
        data: {"intent": "info_request", "rag_used": true}

        event: message
        data: {"token": "SSH "}

        event: message
        data: {"token": "güvenliği "}

        event: done
        data: {"total_tokens": 150}
    """
    # Set timeout (default: 60s for streaming)
    timeout_seconds = payload.timeout or 60

    try:
        # LLM clients
        llm_small, llm_large = _get_llm_clients()

        # Request context
        ctx = RequestContext(
            user_question=payload.question,
            os=payload.os,
            role=payload.role,
            security_level=payload.security_level,  # type: ignore
            zt_maturity=payload.zt_maturity,  # type: ignore
        )

        # RAG builder
        rag_builder = None
        if payload.use_rag:
            try:
                rag_builder = RAGContextBuilder(
                    top_k=payload.rag_top_k,
                    min_score=payload.rag_min_score,
                )
            except Exception as e:
                print(f"[ChatAPI] RAG init failed, devam ediliyor: {e}")

        # Pipeline
        pipeline = SecurePipelineV2(
            llm_ultra_fast=llm_small,
            llm_small=llm_small,
            llm_large=llm_large,
            rag_builder=rag_builder,
            debug=False,
        )

        # Run with timeout
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(pipeline.run, ctx),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            raise APIError(
                status_code=504,
                error_code=ErrorCode.TIMEOUT,
                message=f"Streaming request timeout after {timeout_seconds} seconds",
                details={"timeout": timeout_seconds}
            )

        # Stream the answer token by token
        async def token_generator():
            # Split answer into words and stream
            words = (result.answer or "No response").split()
            for word in words:
                yield word + " "

        # Prepare metadata
        metadata = {
            "intent": result.intent.type if result.intent else None,
            "safety": result.safety.category if result.safety else None,
            "rag_used": payload.use_rag,
            "layer_path": result.layer_path,
        }

        return await stream_chat_response(token_generator(), metadata=metadata)

    except Exception as e:
        raise APIError(
            status_code=500,
            error_code=ErrorCode.PIPELINE_ERROR,
            message=f"Streaming pipeline failed: {str(e)}",
            details={"stage": "streaming"}
        )


