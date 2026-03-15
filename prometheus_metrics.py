from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from prometheus_fastapi_instrumentator import Instrumentator


# ── Layer latency ──────────────────────────────────────────────────────────────

LAYER_LATENCY = Histogram(
    "pipeline_layer_duration_seconds",
    "Duration of each pipeline layer in seconds",
    ["layer"],
    buckets=[0.005, 0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
)

# ── Query outcomes ──────────────────────────────────────────────────────────────

QUERY_COUNTER = Counter(
    "pipeline_queries_total",
    "Total queries processed by the pipeline",
    ["status", "intent", "complexity", "model", "rag_used"],
)

REJECTION_COUNTER = Counter(
    "pipeline_rejections_total",
    "Total queries rejected",
    ["layer"],
)

# ── Safety checks ───────────────────────────────────────────────────────────────

SAFETY_CHECK_COUNTER = Counter(
    "pipeline_safety_checks_total",
    "Safety classification results",
    ["category", "outcome"],
)

# ── Token usage ─────────────────────────────────────────────────────────────────

TOKEN_COUNTER = Counter(
    "llm_tokens_total",
    "Total LLM tokens consumed",
    ["type"],  # "input" | "output"
)

# ── RAG retrieval ───────────────────────────────────────────────────────────────

RAG_RETRIEVAL_LATENCY = Histogram(
    "rag_retrieval_duration_seconds",
    "RAG retrieval duration in seconds",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

RAG_RESULTS_COUNT = Histogram(
    "rag_retrieval_results_count",
    "Number of chunks returned by RAG",
    buckets=[0, 1, 2, 3, 5, 10, 20],
)

RAG_TOP_SCORE = Gauge(
    "rag_retrieval_top_score",
    "Top similarity score from the most recent RAG retrieval",
)


# ── Public helpers ───────────────────────────────────────────────────────────────


@contextmanager
def layer_timer(layer: str) -> Generator[None, None, None]:
    """Context manager that records wall-clock time spent in a pipeline layer."""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        LAYER_LATENCY.labels(layer=layer).observe(time.perf_counter() - t0)


def record_query(
    status: str,
    intent: str,
    complexity: str,
    model: str,
    rag_used: bool,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Record a completed pipeline query."""
    QUERY_COUNTER.labels(
        status=status,
        intent=str(intent),
        complexity=str(complexity),
        model=str(model),
        rag_used=str(rag_used).lower(),
    ).inc()
    if input_tokens:
        TOKEN_COUNTER.labels(type="input").inc(input_tokens)
    if output_tokens:
        TOKEN_COUNTER.labels(type="output").inc(output_tokens)


def record_rejection(layer: str) -> None:
    """Record a query rejection at the given pipeline layer."""
    REJECTION_COUNTER.labels(layer=layer).inc()


def record_safety_check(category: str, outcome: str) -> None:
    """Record a safety classification result.

    Args:
        category: SafetyCategory value (e.g. "safe_defensive", "unsafe_offensive")
        outcome: "passed" or "blocked"
    """
    SAFETY_CHECK_COUNTER.labels(category=category, outcome=outcome).inc()


def record_rag_retrieval(
    duration_s: float,
    results_count: int,
    top_score: float,
) -> None:
    """Record metrics for a single RAG retrieval call."""
    RAG_RETRIEVAL_LATENCY.observe(duration_s)
    RAG_RESULTS_COUNT.observe(results_count)
    RAG_TOP_SCORE.set(top_score)


# ── App setup ────────────────────────────────────────────────────────────────────


def setup_metrics(app: FastAPI) -> None:
    """Instrument the FastAPI app and expose /metrics/prometheus for Prometheus scraping."""
    Instrumentator().instrument(app).expose(app, endpoint="/metrics/prometheus")
