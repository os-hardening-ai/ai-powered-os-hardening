from __future__ import annotations

import asyncio
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
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
from api.streaming import stream_chat_response, format_sse_event

# Intent detection + smalltalk handling (streaming path da Layer 2/3A kullansın diye)
from llm.pipelines.layers.hybrid_intent_detector import HybridIntentDetector, is_smalltalk
from llm.pipelines.layers.pattern_responder import PatternResponderHandler

from log_manager import get_logger

_conv_logger = get_logger("conversations")

router = APIRouter()

# Module-level singletons — ML modelleri (joblib) request başına yeniden yüklenmesin diye.
# Streaming endpoint bunları Layer 2 (intent) + Layer 3A (smalltalk) için kullanır.
_intent_detector = HybridIntentDetector(use_ml=True, debug=False)
_pattern_handler = PatternResponderHandler(debug=False)

# Layer 3 "out-of-scope" red mesajı — SecurePipelineV2._handle_out_of_scope ile aynı metin.
_OUT_OF_SCOPE_MESSAGE = (
    "KAPSAM DIŞI SORU\n\n"
    "Ben sadece siber güvenlik ve işletim sistemi sıkılaştırma (OS hardening) "
    "konularında yardımcı olabiliyorum.\n\n"
    "Size yardımcı olabileceğim konular:\n"
    "- SSH, RDP, Firewall hardening\n"
    "- CIS Benchmarks ve NIST 800-207 uygulamaları\n"
    "- Zero Trust Architecture\n"
    "- Güvenlik yapılandırmaları ve scriptleri\n"
    "- Vulnerability assessment ve risk azaltma\n\n"
    "Lütfen güvenlik veya sistem sıkılaştırma ile ilgili bir soru sorun."
)

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


def _parse_rag_sources(metadata: dict) -> List["RAGSource"]:
    """Metadata dict'inden RAGSource listesi üret. Hem /chat hem /chat/stream kullanır."""
    sources: List[RAGSource] = []
    for idx, sd in enumerate(metadata.get("rag_sources", []), start=1):
        try:
            sources.append(RAGSource(
                id=f"source_{idx}",
                score=sd.get("score", 0.0),
                source=sd.get("source") or "Unknown",
                section=sd.get("section") or "N/A",
                text=sd.get("text"),
            ))
        except Exception:
            pass
    return sources


def _get_llm_clients():
    """Get or initialize LLM clients"""
    global _llm_small, _llm_large

    if _llm_small is None or _llm_large is None:
        _llm_small, _llm_large = get_llm_clients()

    return _llm_small, _llm_large


def get_llm_client_provider_stats() -> dict:
    """Cached singleton LLM balancer'ın GERÇEK kümülatif provider/lane dağılımı.

    `_set_llm_request_metrics` /metrics'e statik `cfg.llm.default_provider` yazıyordu →
    lane'ler aktifken bile dashboard yalnız 'cerebras' gösteriyordu. Bu, FallbackLLM/
    LaneLoadBalancer'ın `by_provider` sayaçlarından (small+large paylaşımlı stats) GERÇEK
    dağılımı verir → cerebras dışı lane'lerin (deepseek/sambanova/openrouter...) gerçekten
    servis edip etmediği görülür. /metrics bunu 'llm_providers' olarak kullanır.
    """
    try:
        if _llm_small is not None and hasattr(_llm_small, "get_stats"):
            return dict(_llm_small.get_stats().get("by_provider", {}))
    except Exception:
        pass
    return {}


def get_llm_client_lane_diagnostics() -> dict:
    """Lane/provider başına ORTALAMA GECİKME (ms) + BAŞARISIZLIK sayısı → yavaş/ölü lane
    tespiti (ör. codestral 0 başarı + N fail → erişilemez; llama-1b avg 40s → yavaş)."""
    try:
        if _llm_small is not None and hasattr(_llm_small, "get_stats"):
            s = _llm_small.get_stats()
            return {
                "avg_latency_ms": dict(s.get("avg_latency_ms_by_provider", {})),
                "failures": dict(s.get("failures_by_provider", {})),
            }
    except Exception:
        pass
    return {"avg_latency_ms": {}, "failures": {}}


def _set_llm_request_metrics(request: Request, result) -> None:
    """Pipeline sonucundaki provider/model/token'ı MetricsMiddleware için request.state'e yaz
    → /metrics 'llm_providers'/'llm_models'/'tokens' panelleri dolar. HEM /chat HEM /chat/stream
    çağırır: stream de tam SecurePipelineV2 koştuğundan token sayısı yanıt akmadan ÖNCE bilinir.
    (Önceden yalnız non-stream /chat set ediyordu → streaming trafikte bu metrikler boş kalıyordu.)"""
    try:
        meta = result.metadata or {}
        model_tier = str(meta.get("model") or "").strip()    # "small"/"large"/"large+CoT"
        if not model_tier:
            # LLM ÜRETİMİ yok (smalltalk 3A / out-of-scope / reject) → provider/token kaydetme,
            # aksi halde "LLM sağlayıcı dağılımı" gerçekte çağrılmayan provider'ı sayar.
            return
        from config.config_loader import get_config as _gcfg
        cfg = _gcfg()
        provider = cfg.llm.default_provider
        provider_models = cfg.llm.providers.get(provider, {}).get("models", {})
        base_tier = model_tier.split("+")[0]                 # "large+CoT" → "large"
        model_name = provider_models.get(base_tier, {}).get("name") or model_tier
        request.state.llm_provider = provider
        request.state.llm_model = model_name
        request.state.llm_tokens = meta.get("tokens_used", 0)
    except Exception:
        pass


async def _run_pipeline(
    payload: "ChatRequest", timeout_seconds: int
) -> tuple["PipelineResult", str, Optional[str], List[Dict[str, str]]]:
    """
    /chat ve /chat/stream için ORTAK yol — tek bir SecurePipelineV2 koşumu.

    Yapılan işler (sırayla):
      1. Session history yükle (varsa)
      2. Context-aware query rewrite — smalltalk ise ATLA (is_smalltalk guard)
      3. RequestContext oluştur
      4. FilterAgent ile os/role çıkar (verilmemişse)
      5. RAGContextBuilder kur (use_rag ise)
      6. SecurePipelineV2.run() — timeout ile

    Returns:
        (result, effective_question, inferred_os, history)
    """
    llm_small, llm_large = _get_llm_clients()

    # 1) Session history
    session_id = payload.session_id or ""
    history: List[Dict[str, str]] = []
    turns: List = []
    if session_id:
        turns = _session_store.get_history(session_id)
        history = [{"role": t.role, "content": t.content} for t in turns]

    effective_question = payload.question

    # 1b) PENDING-PARAM follow-up: önceki asistan turu parametre sorduysa (ör. OS),
    #     bu mesaj o sorunun CEVABIDIR → orijinal action sorusuyla BİRLEŞTİR. Aksi halde
    #     "ubuntu 24.04" gibi kısa cevap sıfırdan sınıflandırılıp KAPSAM DIŞI'na düşer.
    pending_merged = False
    if turns and turns[-1].role == "assistant" and getattr(turns[-1], "intent", None) == "params_needed":
        original_q = next(
            (t.content for t in reversed(turns[:-1]) if t.role == "user"), None
        )
        if original_q:
            effective_question = f"{original_q} {payload.question}".strip()
            pending_merged = True
            _conv_logger.info(
                "[PendingParams] orijinal '%s' + cevap '%s' → '%s'",
                original_q[:40], payload.question[:30], effective_question[:70],
            )

    # 2) Query rewrite (follow-up → standalone). Smalltalk ASLA yeniden yazılmaz —
    #    aksi halde QueryRewriter geçmiş bağlamıyla "naber"i güvenlik sorusuna çevirir.
    #    Pending-param birleştirmesi yapıldıysa rewrite'a gerek yok (zaten standalone).
    if not pending_merged and history and not is_smalltalk(payload.question):
        try:
            from rag.query.query_rewriter import QueryRewriter
            _rewriter = QueryRewriter(llm_fn=llm_small)
            rewritten = _rewriter.rewrite(payload.question, history)
            if rewritten != payload.question:
                _conv_logger.info(
                    "[QueryRewriter] '%s' → '%s'", payload.question[:60], rewritten[:60]
                )
                effective_question = rewritten
        except Exception as _re:
            _conv_logger.warning("[QueryRewriter] failed (non-fatal): %s", _re)

    # 3) RequestContext
    ctx = RequestContext(
        user_question=effective_question,
        os=payload.os,
        role=payload.role,
        security_level=payload.security_level,  # type: ignore
        zt_maturity=payload.zt_maturity,  # type: ignore
        conversation_history=history,
    )

    # 4) FilterAgent — os/role çıkarımı
    inferred_os: Optional[str] = None
    if ctx.os is None or ctx.role is None:
        try:
            from rag.query.filter_agent import FilterAgent
            _fa = FilterAgent(llm_fn=llm_small)
            _filters = _fa.infer(payload.question)
            if _filters.os_type and ctx.os is None:
                ctx.os = _filters.os_type
                inferred_os = _filters.os_type
            if _filters.role and ctx.role is None:
                ctx.role = _filters.role
            _conv_logger.debug(
                "[FilterAgent] os=%s role=%s confidence=%.2f source=%s",
                _filters.os_type, _filters.role, _filters.confidence, _filters.source,
            )
        except Exception as _fe:
            _conv_logger.warning("[FilterAgent] failed (non-fatal): %s", _fe)

    # 5) RAG builder
    rag_builder = None
    if payload.use_rag:
        try:
            _os_for_rag = payload.os or inferred_os or None
            rag_builder = RAGContextBuilder(
                top_k=payload.rag_top_k,
                min_score=payload.rag_min_score,
                os_version=_os_for_rag,
            )
        except Exception as e:
            _conv_logger.warning("[RAG] Builder FAILED: %s", e)
    else:
        _conv_logger.debug("[RAG] use_rag=False skipped")

    # 6) SecurePipelineV2 — timeout ile
    pipeline = SecurePipelineV2(
        llm_ultra_fast=llm_small,
        llm_small=llm_small,
        llm_large=llm_large,
        rag_builder=rag_builder,
        debug=False,
    )
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(pipeline.run, ctx), timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        raise APIError(
            status_code=504,
            error_code=ErrorCode.TIMEOUT,
            message=f"Request timeout after {timeout_seconds} seconds. Try a simpler query or increase timeout.",
            details={"timeout": timeout_seconds, "suggestion": "increase_timeout_or_simplify_query"},
        )

    # request_id'yi metadata'ya koy (stream done_extra için)
    if result.metadata is not None:
        result.metadata.setdefault("request_id", ctx.request_id)

    return result, effective_question, inferred_os, history


def _assistant_turn_intent(result) -> Optional[str]:
    """Asistan turu için intent etiketi. Action pipeline parametre sorduysa (PARAMS_NEEDED)
    'params_needed' işaretle → sonraki tur bu cevabı orijinal soruyla BİRLEŞTİRİR
    (pending-param follow-up; kısa cevabın kapsam-dışı yanlış sınıflanmasını önler)."""
    try:
        if result.layer_path and "PARAMS_NEEDED" in result.layer_path:
            return "params_needed"
        return result.intent.type if result.intent else None
    except Exception:
        return None


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
        # /chat ve /chat/stream ORTAK yol — tek SecurePipelineV2 koşumu
        result, effective_question, _inferred_os, history = await _run_pipeline(
            payload, timeout_seconds
        )
        session_id = payload.session_id or ""

        # RAG kaynaklarini parse et (eger varsa - metadata'dan)
        rag_sources = _parse_rag_sources(result.metadata or {})

        # Sanitize output (remove any leaked prompts/instructions)
        sanitized_answer = sanitize_output(result.answer or "Cevap uretilemedi.")

        # Session history'ye kaydet
        if session_id:
            _session_store.add_turn(session_id, "user", effective_question)
            _session_store.add_turn(
                session_id, "assistant", sanitized_answer[:500],
                intent=_assistant_turn_intent(result),
            )

        # Log conversation (question + answer)
        _request_id = (result.metadata or {}).get("request_id")
        _conv_logger.info(
            f"--- [{_request_id}] intent={result.intent.type if result.intent else 'unknown'} "
            f"path={result.layer_path} total={result.total_time_s:.3f}s ---"
        )
        _conv_logger.info(f"Q: {payload.question}")
        _conv_logger.info(f"A: {sanitized_answer}")

        # Pipeline LLM bilgisini middleware için request.state'e yaz (provider/model/token)
        _meta = result.metadata or {}
        _set_llm_request_metrics(request, result)

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
            request_id=_request_id,
            estimated_cost=result.estimated_cost,
            verification_confidence=_meta.get("verification_confidence"),
            unsupported_claims=_meta.get("unsupported_claims", []) or [],
        )

    except APIError:
        raise
    except Exception as e:
        raise_internal_error("pipeline_execution", e, error_code=ErrorCode.PIPELINE_ERROR)


@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest, request: Request):
    """
    Gerçek token streaming — Server-Sent Events (SSE).

    Layer 1 (safety) + Layer 2 (intent) + RAG retrieval sync koşar;
    LLM üretim adımı Cerebras/SambaNova/OpenRouter stream() ile token-by-token akar.
    TTFT ≈ safety + intent + RAG (~4-5s), sonraki tokenlar gerçek zamanlı gelir.

    SSE event order:
        event: metadata  — intent, safety, rag_used, layer_path, session info
        event: sources   — rag_sources (RAG sonuç döndürdüyse)
        event: message   — her LLM token için bir olay
        event: done      — total_tokens, total_time_s, estimated_cost
    """
    timeout_seconds = payload.timeout or 60

    try:
        llm_small, llm_large = _get_llm_clients()

        # ── Session & query rewrite (run_pipeline ile aynı mantık) ──────────────
        session_id = payload.session_id or ""
        history: List[Dict[str, str]] = []
        turns: List = []
        if session_id:
            turns = _session_store.get_history(session_id)
            history = [{"role": t.role, "content": t.content} for t in turns]

        effective_question = payload.question
        pending_merged = False
        if turns and turns[-1].role == "assistant" and getattr(turns[-1], "intent", None) == "params_needed":
            original_q = next(
                (t.content for t in reversed(turns[:-1]) if t.role == "user"), None
            )
            if original_q:
                effective_question = f"{original_q} {payload.question}".strip()
                pending_merged = True

        if not pending_merged and history and not is_smalltalk(payload.question):
            try:
                from rag.query.query_rewriter import QueryRewriter
                rewritten = QueryRewriter(llm_fn=llm_small).rewrite(payload.question, history)
                if rewritten != payload.question:
                    effective_question = rewritten
            except Exception:
                pass

        ctx = RequestContext(
            user_question=effective_question,
            os=payload.os, role=payload.role,
            security_level=payload.security_level,  # type: ignore
            zt_maturity=payload.zt_maturity,  # type: ignore
            conversation_history=history,
        )

        inferred_os: Optional[str] = None
        if ctx.os is None or ctx.role is None:
            try:
                from rag.query.filter_agent import FilterAgent
                _filters = FilterAgent(llm_fn=llm_small).infer(payload.question)
                if _filters.os_type and ctx.os is None:
                    ctx.os = _filters.os_type
                    inferred_os = _filters.os_type
                if _filters.role and ctx.role is None:
                    ctx.role = _filters.role
            except Exception:
                pass

        rag_builder = None
        if payload.use_rag:
            try:
                rag_builder = RAGContextBuilder(
                    top_k=payload.rag_top_k,
                    min_score=payload.rag_min_score,
                    os_version=payload.os or inferred_os or None,
                )
            except Exception as e:
                _conv_logger.warning("[stream] RAG builder failed: %s", e)

        pipeline = SecurePipelineV2(
            llm_ultra_fast=llm_small, llm_small=llm_small, llm_large=llm_large,
            rag_builder=rag_builder, debug=False,
        )

        # ── Thread→async queue köprüsü ───────────────────────────────────────────
        # run_stream() sync generator → executor'da koş, olayları async queue'ya aktar.
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        sentinel = object()

        def _produce() -> None:
            try:
                for event in pipeline.run_stream(ctx):
                    loop.call_soon_threadsafe(queue.put_nowait, event)
            except Exception as exc:
                loop.call_soon_threadsafe(
                    queue.put_nowait, {"type": "error", "exc": exc}
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, sentinel)

        loop.run_in_executor(None, _produce)

        # ── SSE generator ────────────────────────────────────────────────────────
        _collected: List[str] = []
        _session_saved = False

        async def sse_generator():
            nonlocal _session_saved
            token_count = 0
            done_payload: dict = {}

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=timeout_seconds)
                except asyncio.TimeoutError:
                    yield format_sse_event("error", {"message": "stream timeout", "type": "TimeoutError"})
                    return

                if event is sentinel:
                    break

                etype = event.get("type")

                if etype == "pre_gen":
                    meta = dict(event.get("meta") or {})
                    meta.update({
                        "inferred_os": inferred_os,
                        "session_id": session_id or None,
                        "history_turns": len(history) // 2,
                        "query_rewritten": effective_question != payload.question,
                        "streaming": "real-token",
                    })
                    yield format_sse_event("metadata", meta)
                    sources = event.get("sources")
                    if sources:
                        yield format_sse_event("sources", {"rag_sources": sources})

                elif etype == "token":
                    content = event.get("content", "")
                    _collected.append(content)
                    token_count += 1
                    yield format_sse_event("message", {"token": content})

                elif etype == "done":
                    result = event.get("result")
                    if result:
                        _meta = result.metadata or {}
                        done_payload = {
                            "total_tokens": token_count,
                            "status": "completed",
                            "total_time_s": result.total_time_s,
                            "estimated_cost": result.estimated_cost,
                            "verification_confidence": _meta.get("verification_confidence"),
                            "request_id": _meta.get("request_id"),
                        }
                        # Session history kaydet
                        if session_id and not _session_saved:
                            try:
                                full_answer = sanitize_output("".join(_collected))
                                _session_store.add_turn(session_id, "user", effective_question)
                                _session_store.add_turn(
                                    session_id, "assistant", full_answer[:500],
                                    intent=_assistant_turn_intent(result),
                                )
                                _session_saved = True
                            except Exception:
                                pass
                        _set_llm_request_metrics(request, result)
                        _conv_logger.info(
                            f"--- [{_meta.get('request_id')}] intent={result.intent.type if result.intent else 'unknown'} "
                            f"path={result.layer_path} total={result.total_time_s:.3f}s [stream] ---"
                        )

                elif etype == "error":
                    exc = event.get("exc")
                    yield format_sse_event("error", {
                        "message": str(exc), "type": type(exc).__name__ if exc else "Unknown"
                    })
                    return

            if not done_payload:
                done_payload = {"total_tokens": token_count, "status": "completed"}
            yield format_sse_event("done", done_payload)

        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except APIError:
        raise
    except Exception as e:
        raise_internal_error("streaming", e, error_code=ErrorCode.PIPELINE_ERROR)


_FAST_REFUSAL = (
    "Bu istek savunma-amaçlı güvenlik kapsamı dışında görünüyor; bu konuda yardımcı olamıyorum."
)


async def _prepare_fast(payload: "ChatRequest") -> dict:
    """
    RAG-direct (intent routing YOK) ORTAK hazırlık — hem /chat/fast (non-stream)
    hem /chat/stream/fast kullanır.

    Yapılan: session/rewrite → ctx → FilterAgent → RAG builder → Layer-1 safety →
    (güvenliyse) RAG retrieve + grounded prompt. Intent/routing/complexity YOK;
    her girdi bir güvenlik/bilgi sorusu kabul edilir.

    Returns dict: safe, safety, prompt, llm_large, ctx, rag_sources_data,
                  effective_question, history, session_id.
    """
    llm_small, llm_large = _get_llm_clients()

    session_id = payload.session_id or ""
    history: List[Dict[str, str]] = []
    if session_id:
        turns = _session_store.get_history(session_id)
        history = [{"role": t.role, "content": t.content} for t in turns]

    effective_question = payload.question
    if history and not is_smalltalk(payload.question):
        try:
            from rag.query.query_rewriter import QueryRewriter
            rewritten = QueryRewriter(llm_fn=llm_small).rewrite(payload.question, history)
            if rewritten != payload.question:
                effective_question = rewritten
        except Exception as _re:
            _conv_logger.warning("[QueryRewriter][fast] failed (non-fatal): %s", _re)

    ctx = RequestContext(
        user_question=effective_question,
        os=payload.os,
        role=payload.role,
        security_level=payload.security_level,  # type: ignore
        zt_maturity=payload.zt_maturity,  # type: ignore
        conversation_history=history,
    )

    # FilterAgent — os/role çıkarımı (RAG soft-filter için)
    inferred_os: Optional[str] = None
    if ctx.os is None or ctx.role is None:
        try:
            from rag.query.filter_agent import FilterAgent
            _filters = FilterAgent(llm_fn=llm_small).infer(payload.question)
            if _filters.os_type and ctx.os is None:
                ctx.os = _filters.os_type
                inferred_os = _filters.os_type
            if _filters.role and ctx.role is None:
                ctx.role = _filters.role
        except Exception as _fe:
            _conv_logger.warning("[FilterAgent][fast] failed (non-fatal): %s", _fe)

    rag_builder = None
    if payload.use_rag:
        try:
            rag_builder = RAGContextBuilder(
                top_k=payload.rag_top_k,
                min_score=payload.rag_min_score,
                os_version=payload.os or inferred_os or None,
            )
        except Exception as e:
            _conv_logger.warning("[ChatAPI][fast] RAG init failed: %s", e)

    # ── Layer 1: Safety (fail-closed) ──
    from llm.pipelines.layers.safety_classifier import SafetyClassifier
    from llm.prompts.simple_prompts import get_prompt_for_complexity

    safety = await asyncio.to_thread(
        SafetyClassifier(llm_ultra_fast=llm_small).classify, payload.question
    )
    base = dict(
        safety=safety, llm_large=llm_large, ctx=ctx,
        effective_question=effective_question, history=history, session_id=session_id,
    )
    if not safety.is_safe:
        return {**base, "safe": False, "prompt": None, "rag_sources_data": None}

    # ── RAG bağlamı + kaynaklar → grounded üretim ──
    rag_sources_data = None
    if rag_builder is not None:
        try:
            _ctx_txt, _chunks = await asyncio.to_thread(
                rag_builder.retrieve_balanced, effective_question
            )
            if _ctx_txt:
                ctx.retrieved_context = _ctx_txt
            _srcs = _parse_rag_sources({"rag_sources": [
                {"score": c.get("score", 0.0), "source": c.get("source"),
                 "section": c.get("section", "N/A"), "text": (c.get("text") or "")[:500]}
                for c in (_chunks or [])
            ]})
            rag_sources_data = [s.model_dump() for s in _srcs] if _srcs else None
        except Exception as _re:
            _conv_logger.warning("[ChatAPI][fast] RAG retrieve başarısız (non-fatal): %s", _re)

    prompt = get_prompt_for_complexity(ctx, "medium")
    return {**base, "safe": True, "prompt": prompt, "rag_sources_data": rag_sources_data}


# DEVRE DIŞI ("Hızlı RAG" yolu): kod korundu ama route KAYIT EDİLMİYOR. Retrieval Explorer
# (/rag/search — ham RAG inceleme) + akıllı sohbet (/api/chat[/stream] — grounded cevap)
# bu ihtiyacı zaten karşılıyor; fast yol smalltalk'ı bozuyordu (naber→RAG) ve UI'ı
# karmaşıklaştırıyordu. Re-enable için aşağıdaki @router.post satırının yorumunu kaldır.
# @router.post("/chat/fast", response_model=ChatResponse)
async def chat_fast(payload: ChatRequest) -> ChatResponse:  # noqa: F811 (devre dışı — kayıtsız)
    """
    HIZLI RAG yanıtı (non-stream) — intent routing YOK.

    NOT: RAG burada da, tam pipeline (/api/chat) yolunda da kullanılır — fark RAG'de
    DEĞİL. Bu uç intent routing/smalltalk/complexity/doğrulama katmanlarını ATLAR ve
    doğrudan RAG-grounded üretime gider (daha hızlı, daha az LLM call).

    /api/chat/stream/fast'in akıtmayan ikizi: tek seferde tam ChatResponse döner.
    "Hızlı RAG" modu streaming KAPALIyken bu uca düşer (frontend `expertMode && !stream`).
    """
    try:
        prep = await _prepare_fast(payload)
        safety = prep["safety"]
        session_id = prep["session_id"]

        if not prep["safe"]:
            answer = sanitize_output(_FAST_REFUSAL)
            return ChatResponse(
                answer=answer, intent="info_request", safety_category=safety.category,
                layer_path="1→REJECT", rag_sources=[], stats={"rag_used": False},
            )

        llm_large = prep["llm_large"]
        ctx = prep["ctx"]
        answer = sanitize_output(await asyncio.to_thread(llm_large, prep["prompt"]))

        if session_id:
            try:
                _session_store.add_turn(session_id, "user", prep["effective_question"])
                _session_store.add_turn(session_id, "assistant", answer[:500])
            except Exception:
                pass

        rag_srcs = [RAGSource(**s) for s in (prep["rag_sources_data"] or [])]
        return ChatResponse(
            answer=answer,
            intent="info_request",
            safety_category=safety.category,
            layer_path="1→RAG→GEN(fast)",
            rag_sources=rag_srcs,
            stats={
                "rag_used": ctx.retrieved_context is not None,
                "rag_chunks": len(rag_srcs),
                "model": "large",
                "session_id": session_id or None,
                "history_turns": len(prep["history"]) // 2,
            },
        )
    except APIError:
        raise
    except Exception as e:
        raise_internal_error("chat_fast", e, error_code=ErrorCode.PIPELINE_ERROR)


# DEVRE DIŞI ("Hızlı RAG" stream): kod korundu, route KAYIT EDİLMİYOR (bkz. chat_fast notu).
# @router.post("/chat/stream/fast")
async def chat_stream_fast(payload: ChatRequest):  # noqa: F811 (devre dışı — kayıtsız)
    """
    HIZLI RAG gerçek-token streaming (RAG-grounded / konsol modu).

    NOT: RAG bu uçta da, /api/chat/stream tam pipeline'ında da kullanılır — fark RAG'de
    DEĞİL, yönlendirme + hızda.

    /api/chat/stream'den FARKI:
      • Intent routing (Layer 2/3) ATLANIR — girdi her zaman bir güvenlik/bilgi
        sorusu kabul edilir (smalltalk yönlendirmesi yok). Her sorunun güvenlik
        sorusu olduğu "uzman konsolu" akışları için.
      • llm_large.stream() ile GERÇEK token-token üretim → en düşük ilk-token gecikmesi.
        /chat/stream ise tam pipeline'ı koşup cevabı sonradan kelime kelime akıtır.
      • Korunanlar: Layer-1 safety (fail-closed), RAG grounding + kaynaklar, oturum geçmişi.

    Smalltalk (selam/naber) için UYGUN DEĞİLDİR — onları /api/chat/stream ele alır.

    SSE event order: metadata → sources → message(token) → done
    """
    try:
        prep = await _prepare_fast(payload)
        safety = prep["safety"]
        session_id = prep["session_id"]

        if not prep["safe"]:
            async def _refusal():
                yield _FAST_REFUSAL
            return await stream_chat_response(
                _refusal(),
                metadata={"safety": safety.category, "rag_used": False, "blocked": True},
            )

        llm_large = prep["llm_large"]
        ctx = prep["ctx"]
        prompt = prep["prompt"]
        effective_question = prep["effective_question"]
        _collected: List[str] = []

        async def token_generator():
            queue: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_running_loop()
            sentinel = object()

            def _produce():
                try:
                    streamer = getattr(llm_large, "stream", None)
                    if streamer is not None:
                        for tok in streamer(prompt):
                            loop.call_soon_threadsafe(queue.put_nowait, tok)
                    else:
                        loop.call_soon_threadsafe(queue.put_nowait, llm_large(prompt))
                except Exception as exc:  # noqa: BLE001 — hatayı SSE'ye ilet
                    loop.call_soon_threadsafe(queue.put_nowait, f"\n[stream hatası: {exc}]")
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, sentinel)

            loop.run_in_executor(None, _produce)
            while True:
                tok = await queue.get()
                if tok is sentinel:
                    break
                _collected.append(tok)
                yield tok
            if session_id:
                try:
                    _session_store.add_turn(session_id, "user", effective_question)
                    _session_store.add_turn(
                        session_id, "assistant", sanitize_output("".join(_collected))[:500])
                except Exception:
                    pass

        metadata = {
            "safety": safety.category,
            "intent": "info_request",  # bu endpoint intent routing yapmaz — sabit
            "layer_path": "1→RAG→GEN(fast)",
            "rag_used": ctx.retrieved_context is not None,
            "streaming": "real-token",
            "session_id": session_id or None,
            "history_turns": len(prep["history"]) // 2,
        }
        return await stream_chat_response(
            token_generator(), metadata=metadata, sources=prep["rag_sources_data"],
        )

    except APIError:
        raise
    except Exception as e:
        raise_internal_error("streaming_fast", e, error_code=ErrorCode.PIPELINE_ERROR)


