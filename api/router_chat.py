from __future__ import annotations

import asyncio
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

from llm.core.context import RequestContext
from llm.core.session_store import SessionStore
from llm.core.redis_session_store import RedisSessionStore
from llm.pipelines.secure_v2 import SecurePipelineV2
from llm.clients import get_llm_clients
from llm.rag.integration import RAGContextBuilder

# Import security utilities
from api.security import validate_chat_input, sanitize_output

# Import error handling
from api.errors import APIError, ErrorCode, raise_internal_error

# Import streaming support
from api.streaming import stream_chat_response

from log_manager import get_logger

_conv_logger = get_logger("conversations")

router = APIRouter()

def _init_session_store():
    """Use Redis session store when available; fall back to in-memory."""
    try:
        import os
        from config.config_loader import get_config
        cfg = get_config()
        # REDIS_URL env var overrides config.json (set by docker-compose)
        redis_url = os.environ.get("REDIS_URL") or cfg.redis.url
        store = RedisSessionStore(
            url=redis_url,
            ttl_seconds=cfg.redis.session_ttl_seconds,
            max_history=10,
        )
        if store.available:
            return store
    except Exception:
        pass
    return SessionStore(max_history=10)


_session_store = _init_session_store()


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
    rag_top_k: int = Field(3, description="RAG'den kaç chunk getirileceği (her kaynak için)", ge=1, le=20, examples=[3])
    rag_min_score: float = Field(0.5, description="Minimum relevance score", ge=0.0, le=1.0, examples=[0.5])
    stream: bool = Field(False, description="Enable streaming response (SSE)", examples=[False])
    timeout: Optional[int] = Field(60, description="Request timeout in seconds (default: 60s, max: 300s)", ge=1, le=300, examples=[60])
    session_id: Optional[str] = Field(None, description="Oturum ID'si — multi-turn konuşma geçmişi için", examples=["user-abc-123"])

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
    section: str = "N/A"
    text: Optional[str] = Field(None, description="Chunk metni (ilk 500 karakter)")


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
    verification_confidence: Optional[float] = Field(None, description="Claim verification güven skoru (0-1). Enhanced RAG etkinse dolar.")
    unsupported_claims: List[str] = Field(default_factory=list, description="Bağlamca DESTEKLENMEYEN iddialar (ClaimVerifier) — boşsa hepsi grounded veya doğrulama yapılmadı.")


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
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
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

        # Session history yükle
        session_id = payload.session_id or ""
        history: List[Dict[str, str]] = []
        if session_id:
            turns = _session_store.get_history(session_id)
            history = [{"role": t.role, "content": t.content} for t in turns]

        # Context-aware query rewriting (follow-up → standalone)
        effective_question = payload.question
        if history:
            try:
                from rag.query.query_rewriter import QueryRewriter
                _rewriter = QueryRewriter(llm_fn=llm_small)
                rewritten = _rewriter.rewrite(payload.question, history)
                if rewritten != payload.question:
                    _conv_logger.info(
                        "[QueryRewriter] '%s' → '%s'",
                        payload.question[:60],
                        rewritten[:60],
                    )
                    effective_question = rewritten
            except Exception as _re:
                _conv_logger.warning("[QueryRewriter] failed (non-fatal): %s", _re)

        # Request context olustur
        ctx = RequestContext(
            user_question=effective_question,
            os=payload.os,
            role=payload.role,
            security_level=payload.security_level,  # type: ignore
            zt_maturity=payload.zt_maturity,  # type: ignore
            conversation_history=history,
        )

        # Filter agent: os/role verilmemişse sorgudan çıkar
        _inferred_os: str | None = None
        if ctx.os is None or ctx.role is None:
            try:
                from rag.query.filter_agent import FilterAgent
                _fa = FilterAgent(llm_fn=llm_small)
                _filters = _fa.infer(payload.question)
                if _filters.os_type and ctx.os is None:
                    ctx.os = _filters.os_type
                    _inferred_os = _filters.os_type
                if _filters.role and ctx.role is None:
                    ctx.role = _filters.role
                _conv_logger.debug(
                    "[FilterAgent] os=%s role=%s confidence=%.2f source=%s",
                    _filters.os_type, _filters.role, _filters.confidence, _filters.source,
                )
            except Exception as _fe:
                _conv_logger.warning("[FilterAgent] failed (non-fatal): %s", _fe)

        # RAG builder — sadece use_rag=True ise baslat
        rag_builder = None
        if payload.use_rag:
            try:
                # OS version: explicit > inferred > None
                _os_for_rag = payload.os or _inferred_os or None
                rag_builder = RAGContextBuilder(
                    top_k=payload.rag_top_k,
                    min_score=payload.rag_min_score,
                    os_version=_os_for_rag,
                )
                _conv_logger.debug(
                    "[RAG] Builder OK top_k=%d min_score=%.2f os_version=%s",
                    payload.rag_top_k,
                    payload.rag_min_score,
                    _os_for_rag,
                )
            except Exception as e:
                _conv_logger.warning(f"[RAG] Builder FAILED: {e}")
        else:
            _conv_logger.debug("[RAG] use_rag=False skipped")

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
                            source=source_data.get("source") or "Unknown",
                            section=source_data.get("section") or "N/A",
                            text=source_data.get("text"),
                        )
                    )
            except Exception as e:
                _conv_logger.warning(f"[ChatAPI] Failed to parse RAG sources: {e}")

        # Sanitize output (remove any leaked prompts/instructions)
        sanitized_answer = sanitize_output(result.answer or "Cevap uretilemedi.")

        # Session history'ye kaydet
        if session_id:
            _session_store.add_turn(session_id, "user", effective_question)
            _session_store.add_turn(session_id, "assistant", sanitized_answer[:500])

        # Log conversation (question + answer)
        _conv_logger.info(
            f"--- [{ctx.request_id}] intent={result.intent.type if result.intent else 'unknown'} "
            f"path={result.layer_path} total={result.total_time_s:.3f}s ---"
        )
        _conv_logger.info(f"Q: {payload.question}")
        _conv_logger.info(f"A: {sanitized_answer}")

        # Pipeline LLM bilgisini middleware için request.state'e yaz
        _meta = result.metadata or {}
        from config.config_loader import get_config as _gcfg
        _cfg = _gcfg()
        _provider = _cfg.llm.default_provider
        _model_tier = _meta.get("model", "unknown")  # "small", "large", "large+CoT" etc.
        _provider_models = _cfg.llm.providers.get(_provider, {}).get("models", {})
        _base_tier = _model_tier.split("+")[0]  # "large+CoT" → "large"
        _model_name = _provider_models.get(_base_tier, {}).get("name") or _model_tier
        request.state.llm_provider = _provider
        request.state.llm_model = _model_name
        request.state.llm_tokens = _meta.get("tokens_used", 0)

        return ChatResponse(
            answer=sanitized_answer,
            intent=result.intent.type if result.intent else None,
            safety_category=result.safety.category if result.safety else None,
            layer_path=result.layer_path,
            rag_sources=rag_sources,
            stats={
                "total_time_s": result.total_time_s,
                "layer_path": result.layer_path,
                "rag_used": _meta.get("rag_used", False),
                "rag_chunks": _meta.get("rag_chunks", 0),
                "model": _meta.get("model"),
                "complexity": _meta.get("complexity"),
                "inferred_os": _inferred_os,
                "session_id": session_id or None,
                "history_turns": len(history) // 2,
                "query_rewritten": effective_question != payload.question,
            },
            request_id=ctx.request_id,
            estimated_cost=result.estimated_cost,
            verification_confidence=_meta.get("verification_confidence"),
            unsupported_claims=_meta.get("unsupported_claims", []) or [],
        )

    except APIError:
        raise
    except Exception as e:
        raise_internal_error("pipeline_execution", e, error_code=ErrorCode.PIPELINE_ERROR)


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

        # Filter agent: os/role verilmemişse sorgudan çıkar
        if ctx.os is None or ctx.role is None:
            try:
                from rag.query.filter_agent import FilterAgent
                _fa = FilterAgent(llm_fn=llm_small)
                _filters = _fa.infer(payload.question)
                if _filters.os_type and ctx.os is None:
                    ctx.os = _filters.os_type
                if _filters.role and ctx.role is None:
                    ctx.role = _filters.role
            except Exception as _fe:
                _conv_logger.warning("[FilterAgent] stream failed (non-fatal): %s", _fe)

        # RAG builder (stream)
        rag_builder = None
        if payload.use_rag:
            try:
                _os_for_rag_stream = payload.os or None
                rag_builder = RAGContextBuilder(
                    top_k=payload.rag_top_k,
                    min_score=payload.rag_min_score,
                    os_version=_os_for_rag_stream,
                )
            except Exception as e:
                _conv_logger.warning(f"[ChatAPI] RAG init failed, devam ediliyor: {e}")

        # ── Güvenlik (fail-closed) — tam pipeline'ı koşmadan hızlı sınıflandırma ──
        # GERÇEK streaming için cevabı ÖNCE üretip bölmek yerine üretimi token-token akıtırız;
        # ama güvenlik korunmalı → önce safety, sonra RAG + grounded prompt + stream.
        from llm.pipelines.layers.safety_classifier import SafetyClassifier
        from llm.prompts.simple_prompts import get_prompt_for_complexity

        safety = await asyncio.to_thread(
            SafetyClassifier(llm_ultra_fast=llm_small).classify, payload.question
        )
        if not safety.is_safe:
            async def _refusal():
                yield ("Bu istek savunma-amaçlı güvenlik kapsamı dışında görünüyor; "
                       "bu konuda yardımcı olamıyorum.")
            return await stream_chat_response(
                _refusal(),
                metadata={"safety": safety.category, "rag_used": False, "blocked": True},
            )

        # ── RAG bağlamı (varsa) → prompt'a enjekte (grounded üretim) ──
        if rag_builder is not None:
            try:
                _ctx_txt, _chunks = await asyncio.to_thread(
                    rag_builder.retrieve_balanced, payload.question
                )
                if _ctx_txt:
                    ctx.retrieved_context = _ctx_txt
            except Exception as _re:
                _conv_logger.warning("[ChatAPI.stream] RAG retrieve başarısız (non-fatal): %s", _re)

        prompt = get_prompt_for_complexity(ctx, "medium")

        # ── GERÇEK token streaming: llm_large.stream() (senkron üretici) → asyncio kuyruğu ──
        # (sync ağ akışını event loop'u bloklamadan async SSE'ye köprüler)
        async def token_generator():
            queue: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_running_loop()
            sentinel = object()

            def _produce():
                try:
                    streamer = getattr(llm_large, "stream", None)
                    if streamer is not None:
                        for tok in streamer(prompt):              # GERÇEK token delta'ları
                            loop.call_soon_threadsafe(queue.put_nowait, tok)
                    else:                                          # stream yoksa tek parça
                        loop.call_soon_threadsafe(queue.put_nowait, llm_large(prompt))
                except Exception as exc:  # noqa: BLE001 - hatayı SSE'ye ilet
                    loop.call_soon_threadsafe(queue.put_nowait, f"\n[stream hatası: {exc}]")
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, sentinel)

            loop.run_in_executor(None, _produce)
            while True:
                tok = await queue.get()
                if tok is sentinel:
                    break
                yield tok

        metadata = {
            "safety": safety.category,
            "rag_used": ctx.retrieved_context is not None,
            "streaming": "real-token",
        }
        return await stream_chat_response(token_generator(), metadata=metadata)

    except Exception as e:
        raise_internal_error("streaming", e, error_code=ErrorCode.PIPELINE_ERROR)


