from __future__ import annotations
import sys
import os
import io

# UTF-8 encoding fix for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.system('chcp 65001 > nul 2>&1')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from api.router_rag import router as rag_router
from api.router_chat import router as chat_router
from api.router_health import router as health_router
from api.router_analytics import router as analytics_router
from api.router_openai import router as openai_router
from api.router_artifacts import router as artifacts_router
from api.security import (
    RateLimitMiddleware,
    RateLimitConfig,
    SecurityHeadersMiddleware,
)
from api.middleware import (
    RequestIDMiddleware,
    ResponseMetadataMiddleware,
    ProviderHeadersMiddleware,
    RequestLogMiddleware,
)
from api.errors import (
    api_error_handler,
    generic_error_handler,
    APIError,
)
from api.metrics import (
    MetricsMiddleware,
    metrics_collector,
)
from prometheus_metrics import setup_metrics, setup_tracing
from config.config_loader import get_config
import uvicorn

# API Documentation metadata
DESCRIPTION = """
**Marmara Üniversitesi - Bilgisayar Mühendisliği Bitirme Projesi**
Geliştiriciler: Engin, Mert, Tankut | Akademik Yıl: 2024-2025

AI destekli OS sıkılaştırma sistemi. CIS Benchmark PDF'lerini RAG ile semantik olarak arar,
LLM ile güvenlik önerileri ve hardening scriptleri üretir.

**Mimari:** 4 katmanlı pipeline — Safety → Intent → Routing → Generation

**RAG:** Novita qwen3-embedding-8b (4096 dim) + Qdrant cloud vector store

**LLM:** Groq (primary) → OpenAI → Ollama fallback zinciri
"""

TAGS_METADATA = [
    {"name": "chat", "description": "RAG + LLM entegre güvenlik danışmanlığı ve hardening script üretimi."},
    {"name": "openai-compat", "description": "OpenAI-compatible endpoint. Herhangi bir OpenAI istemcisi veya araç `base_url=http://localhost:8000/v1` ile doğrudan bağlanabilir."},
    {"name": "rag", "description": "CIS Benchmark üzerinde doğrudan semantik arama."},
    {"name": "domain", "description": "Rule Engine (bağımlılık çözümü + çakışma tespiti) ve Artifact Generator (Bash/PowerShell/Ansible/REG/GPO)."},
    {"name": "health", "description": "Servis sağlık durumu ve bileşen diagnostiği."},
    {"name": "monitoring", "description": "İstek metrikleri, hata logları ve performans istatistikleri."},
]

def create_app() -> FastAPI:
    cfg = get_config()
    app = FastAPI(
        title="AI-Powered OS Hardening API",
        version=cfg.app.version,
        description=DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
        contact={
            "name": "Bilgisayar Mühendisliği Bitirme Projesi",
            "email": "your.email@university.edu.tr",
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        },
    )

    # Register error handlers
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)

    # Middleware stack (order matters - applied in reverse order)
    # 1. Security headers (applied last, affects all responses)
    app.add_middleware(SecurityHeadersMiddleware)

    # 2. Provider headers (add LLM provider info to responses)
    app.add_middleware(ProviderHeadersMiddleware)

    # 3. Response metadata (processing time, version)
    app.add_middleware(ResponseMetadataMiddleware, version=cfg.app.version)

    # 4. Request ID tracking (generates/accepts request IDs)
    app.add_middleware(RequestIDMiddleware)

    # 4b. Request logging — runs after RequestIDMiddleware so request_id is available
    app.add_middleware(RequestLogMiddleware)

    # 5. Metrics collection (tracks all requests)
    app.add_middleware(MetricsMiddleware, collector=metrics_collector)

    # Prometheus metrics — exposes /metrics/prometheus for scraping
    setup_metrics(app)

    # OpenTelemetry tracing — sends spans to Jaeger via OTLP
    setup_tracing(app)

    # 6. Rate limiting — config.json'dan okunur
    rate_limit_config = RateLimitConfig(
        requests_per_minute=cfg.api.rate_limit_requests,
        requests_per_hour=cfg.api.rate_limit_requests * 20,
        burst_size=10
    )
    app.add_middleware(RateLimitMiddleware, config=rate_limit_config)

    # 7. Compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # 8. Trusted host
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Production'da specific domains kullan
    )

    # CORS middleware — origins config.json'dan okunur
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.api.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        max_age=600,
    )

    # RAG-only endpoint (backward compatibility)
    app.include_router(rag_router, prefix="/rag", tags=["rag"])

    # RAG + LLM combined endpoint (yeni!)
    app.include_router(chat_router, prefix="/api", tags=["chat"])

    # Health check
    app.include_router(health_router)

    # Advanced analytics
    app.include_router(analytics_router, prefix="/api", tags=["monitoring"])

    # OpenAI-compatible endpoint
    app.include_router(openai_router, prefix="/v1", tags=["openai-compat"])

    # Rule Engine + Artifact Generator
    app.include_router(artifacts_router, prefix="/api", tags=["domain"])

    # ── Metrics Endpoint ──
    @app.get("/metrics", tags=["monitoring"])
    async def get_metrics(
        endpoint: str = None,
        window_minutes: int = None
    ):
        """
        Get performance metrics.

        Args:
            endpoint: Filter by specific endpoint (optional)
            window_minutes: Time window in minutes (optional, default: all time)

        Returns:
            Aggregated metrics including latency, error rate, token usage
        """
        agg_metrics = metrics_collector.get_aggregated_metrics(
            endpoint=endpoint,
            time_window_minutes=window_minutes
        )

        return {
            "requests": {
                "total": agg_metrics.total_requests,
                "successful": agg_metrics.successful_requests,
                "failed": agg_metrics.failed_requests,
                "error_rate": round(agg_metrics.error_rate * 100, 2),  # as percentage
            },
            "latency_ms": {
                "avg": round(agg_metrics.avg_latency_ms, 1),
                "min": round(agg_metrics.min_latency_ms, 1),
                "max": round(agg_metrics.max_latency_ms, 1),
                "p50": round(agg_metrics.p50_latency_ms, 1),
                "p95": round(agg_metrics.p95_latency_ms, 1),
                "p99": round(agg_metrics.p99_latency_ms, 1),
            },
            "tokens": {
                "total": agg_metrics.total_tokens,
                "avg_per_request": round(agg_metrics.avg_tokens_per_request, 0),
            },
            "llm_providers": agg_metrics.provider_stats,
            "llm_models": agg_metrics.model_stats,
        }

    @app.get("/metrics/errors", tags=["monitoring"])
    async def get_recent_errors(limit: int = 10):
        """
        Get recent errors.

        Args:
            limit: Number of recent errors to return (max 100)

        Returns:
            List of recent error requests
        """
        limit = min(limit, 100)  # Cap at 100
        errors = metrics_collector.get_recent_errors(limit=limit)

        return {
            "errors": [
                {
                    "timestamp": err.timestamp.isoformat(),
                    "endpoint": err.endpoint,
                    "method": err.method,
                    "status_code": err.status_code,
                    "duration_ms": round(err.duration_ms, 1),
                    "error": err.error,
                }
                for err in errors
            ]
        }

    @app.get("/metrics/slow", tags=["monitoring"])
    async def get_slow_requests(limit: int = 10):
        """
        Get slowest requests.

        Args:
            limit: Number of slow requests to return (max 100)

        Returns:
            List of slowest requests
        """
        limit = min(limit, 100)
        slow = metrics_collector.get_slowest_requests(limit=limit)

        return {
            "slow_requests": [
                {
                    "timestamp": req.timestamp.isoformat(),
                    "endpoint": req.endpoint,
                    "method": req.method,
                    "status_code": req.status_code,
                    "duration_ms": round(req.duration_ms, 1),
                    "llm_provider": req.llm_provider,
                    "llm_model": req.llm_model,
                }
                for req in slow
            ]
        }

    return app


app = create_app()

if __name__ == "__main__":
    _cfg = get_config()
    uvicorn.run(
        app,
        host=_cfg.api.host,
        port=_cfg.api.port,
    )
