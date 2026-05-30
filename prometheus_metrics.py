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
from prometheus_fastapi_instrumentator import Instrumentator


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


# ── Setup ──────────────────────────────────────────────────────────────────────

def setup_metrics(app) -> None:
    """
    Attach Prometheus metrics to a FastAPI app.
    Call once inside create_app(), before registering routers.
    Exposes /metrics/prometheus — scraped by Prometheus.
    """
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
