"""
Prometheus metrics + Jaeger tracing setup for ai-powered-os-hardening backend.

Usage in main.py:
    from prometheus_metrics import setup_metrics, setup_tracing
    setup_metrics(app)   # Prometheus — exposes /metrics/prometheus
    setup_tracing(app)   # Jaeger — sends OTLP traces to OTEL_EXPORTER_OTLP_ENDPOINT

Usage for pipeline events:
    from prometheus_metrics import record_query, record_safety_check, record_rejection, record_rag_retrieval, layer_timer

    with layer_timer("1"):
        result = run_safety_check(query)

    record_query(status="answered", intent="os_hardening", rag_used=True, ...)
    record_rag_retrieval(duration_s=0.4, results_count=5, top_score=0.87)
"""

import os
from contextlib import contextmanager

from prometheus_client import Counter, Histogram
# NOT: `prometheus_fastapi_instrumentator` OPSİYONELDİR ve yalnızca setup_metrics()
# içinde kullanılır → import'u modül tepesinde DEĞİL, fonksiyon içinde (lazy) yapılır.
# Aksi halde paket kurulu değilse (CI, yük testi, minimal dev) tüm uygulama import'u
# çöker. Custom metrikler (aşağıdaki Counter/Histogram) prometheus_client ile çalışır.


# ── Query counters ─────────────────────────────────────────────────────────────

hardening_queries_total = Counter(
    "hardening_queries_total",
    "Total number of hardening API queries",
    [
        "status",       # answered | rejected | error
        "intent",       # os_hardening | script_or_config | conceptual_explanation | ...
        "complexity",   # simple | moderate | complex
        "model",        # model name
        "rag_used",     # true | false
    ],
)

hardening_llm_tokens_total = Counter(
    "hardening_llm_tokens_total",
    "Total LLM tokens consumed",
    ["model", "token_type"],  # token_type: input | output
)

hardening_safety_checks_total = Counter(
    "hardening_safety_checks_total",
    "Safety check outcomes by category",
    ["category", "outcome"],  # outcome: passed | blocked
)

hardening_rejections_total = Counter(
    "hardening_rejections_total",
    "Queries rejected by pipeline layer",
    ["layer"],  # "1" | "2" | "3" | "4"
)


# ── Pipeline latency ───────────────────────────────────────────────────────────

pipeline_layer_duration = Histogram(
    "hardening_pipeline_layer_duration_seconds",
    "Time spent in each pipeline layer",
    ["layer"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)


# ── RAG-specific metrics ───────────────────────────────────────────────────────

rag_retrieval_duration = Histogram(
    "hardening_rag_retrieval_duration_seconds",
    "Time spent on RAG retrieval (embedding + vector search)",
    buckets=[0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0],
)

rag_top_similarity_score = Histogram(
    "hardening_rag_top_similarity_score",
    "Top similarity score returned by vector search",
    buckets=[0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 1.0],
)

rag_results_count = Histogram(
    "hardening_rag_results_count",
    "Number of chunks returned by RAG retrieval",
    buckets=[0, 1, 2, 3, 5, 8, 10],
)

# RAG cevap-groundedness (ClaimVerifier güven skoru). RAG cevap KALİTESİNİN en doğrudan
# göstergesi — bitirme için "cevaplar kaynaklara dayanıyor mu" kanıtı. 0-1 arası.
rag_verification_confidence = Histogram(
    "hardening_rag_verification_confidence",
    "Answer groundedness confidence from ClaimVerifier (0-1)",
    buckets=[0.0, 0.3, 0.45, 0.55, 0.6, 0.7, 0.8, 0.9, 1.0],
)


# ── End-to-end & cost ────────────────────────────────────────────────────────

# Uçtan uca istek süresi (tüm katmanlar dahil). layer_duration katman-bazlı; bu
# kullanıcının gerçekte beklediği toplam süredir → SLO/p95 için kritik.
query_total_duration = Histogram(
    "hardening_query_duration_seconds",
    "End-to-end pipeline duration per query (all layers)",
    ["intent"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 15.0],
)

# Tahmini LLM maliyeti (USD). Ücretsiz/düşük-maliyet hedefinin kanıtı + bütçe izleme.
query_estimated_cost_total = Counter(
    "hardening_query_estimated_cost_usd_total",
    "Cumulative estimated LLM cost in USD",
    ["intent"],
)


# ── LLM fallback chain health ────────────────────────────────────────────────

# Çoklu-sağlayıcı (Cerebras→SambaNova→Gemini→Novita) zincirinin sağlığı. Hangi
# sağlayıcının kaç kez servis ettiği + fallback/başarısızlık → dayanıklılık kanıtı.
llm_provider_calls_total = Counter(
    "hardening_llm_provider_calls_total",
    "LLM calls served, by role and provider",
    ["role", "provider"],  # role: small|large
)

llm_fallback_total = Counter(
    "hardening_llm_fallback_total",
    "LLM calls that fell back to a non-primary provider",
    ["role"],
)

llm_chain_failure_total = Counter(
    "hardening_llm_chain_failure_total",
    "LLM calls where the ENTIRE provider chain failed",
    ["role"],
)


# ── Setup ──────────────────────────────────────────────────────────────────────

def setup_metrics(app) -> None:
    """
    Attach Prometheus metrics to a FastAPI app.
    Call once inside create_app(), before registering routers.
    Exposes /metrics/prometheus — scraped by Prometheus.

    `prometheus_fastapi_instrumentator` opsiyoneldir: kuruluysa otomatik HTTP
    instrumentation + /metrics/prometheus ucu eklenir. Kurulu değilse (CI, yük testi,
    minimal dev) custom metrikler (Counter/Histogram) yine ÇALIŞIR; sadece otomatik
    uç atlanır — uygulama import'u/başlangıcı bu yüzden ASLA çökmez.
    """
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
    except ImportError:   # ModuleNotFoundError dahil — kısmi/eksik kurulumu da yakalar
        import logging as _lg
        _lg.getLogger(__name__).warning(
            "[Metrics] prometheus_fastapi_instrumentator kurulu degil — otomatik HTTP "
            "instrumentation atlandi (custom metrikler aktif). "
            "Kurulum: pip install prometheus-fastapi-instrumentator")
        return

    Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_instrument_requests_inprogress=True,
        inprogress_labels=True,
    ).instrument(app).expose(app, endpoint="/metrics/prometheus", include_in_schema=False)


def setup_tracing(app, service_name: str | None = None) -> None:
    """
    Initialise OpenTelemetry tracing and send spans to Jaeger via OTLP.
    Call once inside create_app(), after setup_metrics().

    Environment variables:
        OTEL_EXPORTER_OTLP_ENDPOINT  (default: http://localhost:4317)
        OTEL_SERVICE_NAME            (default: hardening-api)
        OTEL_SERVICE_VERSION         (default: 1.0.0)

    Auto-instruments:
        - FastAPI  → HTTP server spans (method, path, status_code)
        - HTTPX    → outgoing spans (Novita, Groq, Qdrant calls)
    """
    # Standart OTEL_SDK_DISABLED env'i ile tracing tamamen kapatılabilir.
    # Jaeger/OTLP collector erişilemezse (örn. yük testi, CI, local dev) her span
    # export denemesi ~1sn timeout/retry yiyip istekleri yavaşlatır — bu kapı onu önler.
    if os.getenv("OTEL_SDK_DISABLED", "").lower() in ("1", "true", "yes"):
        import logging as _lg
        _lg.getLogger(__name__).info("[OTel] OTEL_SDK_DISABLED set — tracing devre dışı")
        return

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    svc_name = service_name or os.getenv("OTEL_SERVICE_NAME", "hardening-api")
    svc_ver  = os.getenv("OTEL_SERVICE_VERSION", "1.0.0")
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: svc_name, SERVICE_VERSION: svc_ver})
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()


# ── Context managers ───────────────────────────────────────────────────────────

@contextmanager
def layer_timer(layer: str):
    """
    Sync context manager — measures pipeline layer duration.

    Example:
        with layer_timer("1"):
            result = run_safety_check(query)
    """
    with pipeline_layer_duration.labels(layer=layer).time():
        yield


# ── Record helpers ─────────────────────────────────────────────────────────────

def record_query(
    *,
    status: str = "answered",
    intent: str = "unknown",
    complexity: str = "unknown",
    model: str = "unknown",
    rag_used: bool = False,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Increment counters after a query completes."""
    hardening_queries_total.labels(
        status=status,
        intent=intent,
        complexity=complexity,
        model=model,
        rag_used=str(rag_used).lower(),
    ).inc()
    if input_tokens:
        hardening_llm_tokens_total.labels(model=model, token_type="input").inc(input_tokens)
    if output_tokens:
        hardening_llm_tokens_total.labels(model=model, token_type="output").inc(output_tokens)


def record_safety_check(category: str, outcome: str) -> None:
    """Record a safety check result. outcome: 'passed' | 'blocked'"""
    hardening_safety_checks_total.labels(category=category, outcome=outcome).inc()


def record_rejection(layer: str) -> None:
    """Record that a query was rejected at a pipeline layer."""
    hardening_rejections_total.labels(layer=layer).inc()


def record_rag_retrieval(
    *,
    duration_s: float,
    results_count: int,
    top_score: float = 0.0,
) -> None:
    """Record RAG retrieval stats after a vector search completes."""
    rag_retrieval_duration.observe(duration_s)
    rag_results_count.observe(results_count)
    if top_score > 0:
        rag_top_similarity_score.observe(top_score)


def record_query_outcome(
    *,
    intent: str = "unknown",
    total_time_s: float = 0.0,
    estimated_cost: float = 0.0,
    verification_confidence: float | None = None,
) -> None:
    """Record per-query end-to-end signals (latency, cost, groundedness).

    Hepsi in-process observe/inc — I/O yok, ihmal edilebilir maliyet. secure_v2.run()
    sonunda mevcut record_query çağrısının yanında çağrılır."""
    query_total_duration.labels(intent=intent).observe(max(total_time_s, 0.0))
    if estimated_cost and estimated_cost > 0:
        query_estimated_cost_total.labels(intent=intent).inc(estimated_cost)
    if verification_confidence is not None:
        rag_verification_confidence.observe(verification_confidence)


def record_llm_provider_call(role: str, provider: str, *, was_fallback: bool) -> None:
    """Record a successful LLM call served by `provider` for `role` (small|large)."""
    llm_provider_calls_total.labels(role=role, provider=provider).inc()
    if was_fallback:
        llm_fallback_total.labels(role=role).inc()


def record_llm_chain_failure(role: str) -> None:
    """Record that the entire provider chain failed for a role."""
    llm_chain_failure_total.labels(role=role).inc()
