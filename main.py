from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from api.router_rag import router as rag_router
from api.router_chat import router as chat_router
from api.router_health import router as health_router
from api.security import (
    RateLimitMiddleware,
    RateLimitConfig,
    SecurityHeadersMiddleware,
)
from api.metrics import (
    MetricsMiddleware,
    metrics_collector,
    format_metrics_summary,
)
import uvicorn

# API Documentation metadata
DESCRIPTION = """
## AI-Powered OS Hardening API

**Bilgisayar Muhendisligi Bitirme Projesi**

RAG (Retrieval Augmented Generation) + LLM tabanli isletim sistemi guvenlik sikilaştirma asistani.

### 4-Layer Security Pipeline

**Layer 1: Safety Classification**
* LLM-based threat detection
* Categories: safe_defensive, safe_educational, ambiguous, unsafe_offensive, unsafe_spam

**Layer 2: Intent Detection**
* Pattern-based routing (no LLM calls)
* Intent types: smalltalk, info_request, action_request, out_of_scope

**Layer 3: Routing**
* 3A - Pattern Responder: Instant responses for greetings/thanks (0ms, $0)
* 3B - Info Pipeline: Smart RAG + complexity-based model selection
* 3C - Action Pipeline: Script generation with strict validation
* OUT_OF_SCOPE: Polite rejection for non-security topics

**Layer 4: Generation**
* Adaptive model selection (Groq Llama 8B, GPT-4o-mini, GPT-4o)
* Smart RAG triggering (skip generic, use specific)
* CoT reasoning for complex queries

### Ozellikler

* **RAG Search**: CIS Benchmark dokumanllarindan anlamsal arama
* **LLM Chat**: RAG + LLM entegre guvenlik danipmanligi
* **Adaptive Routing**: Task karmasikligina gore otomatik model secimi
* **Multi-Provider**: Groq (ucretsiz), OpenAI, Ollama destegi
* **Source Attribution**: Hangi kaynaklardan yanit uretildigini gosterir
* **Out-of-Scope Handling**: Non-security topics politely rejected

### Guvenlik

**Rate Limiting:**
* 100 requests/dakika per IP
* 5 dakika ban süresi (rate limit ihlali)
* Otomatik IP tracking ve blocking

**Input Validation:**
* Max 5000 karakter input uzunluğu
* Empty input kontrolü
* Field-level validation (Pydantic)

**Security Headers:**
* X-Content-Type-Options: nosniff
* X-Frame-Options: DENY
* X-XSS-Protection: enabled
* Strict-Transport-Security (HSTS)
* Content-Security-Policy
* Permissions-Policy

**Output Sanitization:**
* LLM prompt leakage koruması
* System instruction filtering

**CORS ve Host Protection:**
* CORS middleware (yapılandırılabilir origins)
* Trusted host validation
* GZip compression

### Performance Monitoring

**Real-time Metrics:**
* Request latency tracking (avg, min, max, p50, p95, p99)
* Error rate monitoring
* Token usage statistics
* LLM provider breakdown

**Benchmarks:**
* Response time: ~2-4 saniye (avg)
* Throughput: 500+ token/saniye (Groq)
* 24 saat metrics retention
* Endpoint: `/metrics`

**Monitoring Endpoints:**
* `/metrics` - Aggregated performance metrics
* `/metrics/errors` - Recent error logs
* `/metrics/slow` - Slowest requests

### Dokumantasyon

* OpenAPI/Swagger UI: `/docs`
* ReDoc: `/redoc`
* Health Check: `/health`
"""

TAGS_METADATA = [
    {
        "name": "chat",
        "description": "**RAG + LLM entegre endpoint**. Kullanıcı sorusunu RAG ile zenginleştirip LLM'e gönderir.",
    },
    {
        "name": "rag",
        "description": "**Sadece RAG arama**. Vector database'den semantik arama (backward compatibility).",
    },
    {
        "name": "health",
        "description": "**Sistem sağlık kontrolleri**. API durumu, bağımlılıklar, metrikler.",
    },
    {
        "name": "monitoring",
        "description": "**Performance monitoring**. Request metrics, latency stats, error rates.",
    },
]

def create_app() -> FastAPI:
    app = FastAPI(
        title="AI-Powered OS Hardening API",
        version="1.0.0",
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

    # Middleware stack (order matters - applied in reverse order)
    # 1. Security headers (applied last, affects all responses)
    app.add_middleware(SecurityHeadersMiddleware)

    # 2. Metrics collection (tracks all requests)
    app.add_middleware(MetricsMiddleware, collector=metrics_collector)

    # 3. Rate limiting (100 requests per minute per IP)
    rate_limit_config = RateLimitConfig(
        max_requests=100,
        window_seconds=60,
        ban_duration_seconds=300  # 5 min ban for violators
    )
    app.add_middleware(RateLimitMiddleware, config=rate_limit_config)

    # 4. Compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # 5. Trusted host (Production'da specific domains kullan)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Production'da specific domains kullan
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Production'da specific origins kullan
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        max_age=600,  # Preflight cache 10 dakika
    )

    # RAG-only endpoint (backward compatibility)
    app.include_router(rag_router, prefix="/rag", tags=["rag"])

    # RAG + LLM combined endpoint (yeni!)
    app.include_router(chat_router, prefix="/api", tags=["chat"])

    # Health check
    app.include_router(health_router)

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
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )
