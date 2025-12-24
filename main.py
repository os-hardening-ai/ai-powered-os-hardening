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
# 🛡️ AI-Powered OS Hardening API

## Proje Hakkında / About This Project

**Marmara Üniversitesi - Bilgisayar Mühendisliği Bitirme Projesi**
**Computer Engineering Graduation Project - Marmara University**

👥 **Geliştiriciler / Developers:** Engin, Mert, Tankut
📅 **Akademik Yıl / Academic Year:** 2024-2025

### 🎯 Projenin Amacı / Project Objective

Bu proje, işletim sistemi güvenlik sıkılaştırma (OS hardening) süreçlerini otomatikleştirmek ve yapay zeka destekli bir danışmanlık sistemi sunmak amacıyla geliştirilmiştir. **RAG (Retrieval Augmented Generation)** ve **Büyük Dil Modelleri (LLM)** kullanarak, güvenlik profesyonellerine ve sistem yöneticilerine akıllı, bağlama duyarlı güvenlik önerileri sunar.

This project automates OS hardening processes and provides an AI-powered security consultation system. Using **RAG** and **Large Language Models**, it delivers intelligent, context-aware security recommendations to security professionals and system administrators.

### 💡 Neden Bu Projeyi Yaptık? / Why We Built This

**Tespit Edilen Problemler:**
- ⏱️ Manuel güvenlik sıkılaştırma süreçleri zaman alıcı ve hata yapmaya açık
- 📖 CIS Benchmark gibi kapsamlı dokümanlarda bilgi bulmak zahmetli
- 🔧 Her platform için farklı komutlar ve yapılandırmalar öğrenmek zor
- 📊 Güvenlik standartlarına uyum sürekli güncel bilgi gerektiriyor

**Sunduğumuz Çözüm:**
- 🤖 **AI-destekli otomatik script üretimi** - Platform-specific güvenlik scriptleri
- 📚 **CIS Benchmark RAG entegrasyonu** - Anında dokümantasyon erişimi
- 🎯 **Akıllı intent tanıma** - %90.48 doğrulukla kullanıcı niyetini anlama
- ⚡ **Hızlı yanıt süreleri** - 2-4 saniyede kapsamlı güvenlik önerileri

### 🔬 Teknik Yenilikler / Technical Innovations

1. **Hybrid ML Intent Detection** - Pattern + ML model (%90.48 test accuracy)
2. **Smart RAG Integration** - CIS Benchmark semantic search
3. **4-Layer Security Pipeline** - Safety → Intent → Routing → Generation
4. **Adaptive Model Selection** - Task complexity-based LLM routing
5. **Multi-Provider Support** - Groq (free), OpenAI, Ollama

---

### 🎯 Core Architecture

#### **4-Layer Security Pipeline**

##### **Layer 1: Safety Classification**
- LLM-based threat detection and content filtering
- Categories:
  - ✅ `safe_defensive` - Defensive security operations
  - ✅ `safe_educational` - Learning and training content
  - ⚠️ `ambiguous` - Requires additional context
  - ❌ `unsafe_offensive` - Potentially harmful content
  - ❌ `unsafe_spam` - Spam or irrelevant content
- Fast pre-filtering before pipeline execution

##### **Layer 2: Intent Detection**
- **Hybrid ML + Pattern-based** intent classification
- **ML Model Performance:**
  - 📊 **Test Accuracy: 90.48%**
  - 📊 **Cross-Validation Mean: 82.10%**
  - 📊 Training Dataset: 1677 examples
  - ⚡ Latency: ~5-10ms per prediction
  - 💰 Cost: $0 (no API calls)
- Intent Categories:
  - 🤝 `greeting` - User greetings and pleasantries
  - 👋 `farewell` - Goodbyes and closing statements
  - 🙏 `thanks` - Expressions of gratitude
  - ❓ `help` - Assistance requests
  - 📚 `info_request` - Information and explanation queries
  - ⚙️ `action_request` - Script generation and configuration
  - 🚫 `out_of_scope` - Non-security related topics

##### **Layer 3: Intelligent Routing**
- **3A - Pattern Responder**
  - Instant responses for greetings/thanks
  - ⚡ Latency: ~0ms
  - 💰 Cost: $0
- **3B - Info Pipeline**
  - RAG-enhanced information retrieval
  - Complexity-based model selection
  - CIS Benchmark document search
- **3C - Action Pipeline**
  - Security script generation
  - Strict validation and safety checks
  - Platform-specific templates
- **OUT_OF_SCOPE Handler**
  - Polite rejection for non-security topics
  - Context-aware explanations

##### **Layer 4: Adaptive Generation**
- **Dynamic Model Selection:**
  - 🚀 Groq Llama 3.1 8B (fast, free)
  - 🎯 Groq Llama 3.3 70B (complex queries)
  - 🔧 Configurable fallback chain
- **Smart RAG Integration:**
  - Semantic search over CIS Benchmarks
  - Automatic relevance filtering
  - Source attribution
- **Chain-of-Thought (CoT) Reasoning**
  - Step-by-step problem decomposition
  - Enhanced accuracy for complex scenarios

---

### ✨ Key Features

#### **🔍 RAG-Powered Search**
- Semantic search over CIS Benchmark documents
- Vector similarity using sentence transformers
- Configurable relevance thresholds
- Multi-source aggregation

#### **💬 Intelligent Chat Interface**
- RAG + LLM integrated security consulting
- Context-aware conversation flow
- Multi-turn dialogue support
- Source attribution and transparency

#### **🎛️ Adaptive Intelligence**
- Task complexity-based model selection
- Automatic routing optimization
- Cost-performance trade-offs
- Graceful degradation

#### **🔌 Multi-Provider Support**
- **Groq** (Free, ultra-fast)
  - Llama 3.1 8B Instant
  - Llama 3.3 70B Versatile
- **OpenAI** (Premium quality)
  - GPT-4o-mini
  - GPT-4o
- **Ollama** (Local, private)
  - Self-hosted models
  - No API costs

#### **📊 Source Transparency**
- Every response cites sources
- CIS Benchmark section references
- Confidence scores
- Retrieval relevance metrics

#### **🚫 Smart Scope Management**
- Out-of-scope topic detection
- Polite rejection with explanations
- Context-aware redirection
- Educational guidance

---

### 🔒 Security & Protection

#### **🚦 Rate Limiting**
- **100 requests/minute** per IP address
- **5-minute ban** period for violations
- Automatic IP tracking and blocking
- Sliding window algorithm
- Configurable thresholds

#### **✅ Input Validation**
- **Maximum length:** 5000 characters
- Empty input detection
- Field-level validation (Pydantic)
- SQL injection prevention
- XSS filtering
- Command injection protection

#### **🛡️ Security Headers**
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

#### **🧹 Output Sanitization**
- LLM prompt leakage protection
- System instruction filtering
- Sensitive data masking
- Response validation

#### **🌐 CORS & Host Protection**
- Configurable CORS origins
- Trusted host validation
- GZip compression
- Request timeout enforcement

#### **📝 Audit Logging**
- All requests logged
- Error tracking
- Performance metrics
- Security event monitoring

---

### 📈 Performance Monitoring

#### **⏱️ Real-time Metrics**
- Request latency tracking (avg, min, max, p50, p95, p99)
- Error rate monitoring
- Token usage statistics
- LLM provider breakdown
- Success/failure rates

#### **🎯 Performance Benchmarks**
- **Average Response Time:** 2-4 seconds
- **Throughput:** 500+ tokens/second (Groq)
- **Concurrent Requests:** Up to 100
- **Metrics Retention:** 24 hours
- **Uptime Target:** 99.9%

#### **📊 Monitoring Endpoints**
| Endpoint | Purpose |
|----------|---------|
| `/metrics` | Aggregated performance statistics |
| `/metrics/errors` | Recent error logs and diagnostics |
| `/metrics/slow` | Slowest request analysis |
| `/health` | Service health status |
| `/analytics/summary` | Usage analytics dashboard |

---

### 📚 API Documentation

#### **Interactive Documentation**
- **Swagger UI:** [`/docs`](/docs) - Try API endpoints interactively
- **ReDoc:** [`/redoc`](/redoc) - Beautiful API documentation
- **OpenAPI Spec:** `/openapi.json` - Machine-readable API schema

#### **Health & Status**
- **Health Check:** [`/health`](/health) - Service status verification
- **Version Info:** Included in all responses

---

### 🚀 Quick Start

#### **1. RAG Search Example**
```bash
curl -X POST "http://localhost:8000/rag/search" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "SSH hardening best practices",
    "top_k": 3
  }'
```

#### **2. Chat Query Example**
```bash
curl -X POST "http://localhost:8000/chat/query" \\
  -H "Content-Type: application/json" \\
  -d '{
    "question": "Ubuntu 22.04 SSH portunu nasıl değiştiririm?",
    "use_rag": true
  }'
```

#### **3. Health Check Example**
```bash
curl "http://localhost:8000/health"
```

---

### 📞 Support & Resources

- **Project Repository:** GitHub
- **Documentation:** `/docs` endpoint
- **Issue Tracker:** GitHub Issues
- **Version:** v1.0.0

"""

TAGS_METADATA = [
    {
        "name": "chat",
        "description": """
## 💬 Chat - RAG + LLM Integrated Endpoints

**Primary Interface** for security consultations and hardening assistance.

### Features:
- 🔍 **RAG-Enhanced Responses** - Enriched with CIS Benchmark context
- 🤖 **ML Intent Detection** - 90.48% accuracy, 7 intent categories
- 🎯 **Adaptive Routing** - Complexity-based model selection
- 📊 **Source Attribution** - Every answer cites sources
- ⚡ **Fast Responses** - 2-4 second average latency

### Use Cases:
- Security configuration questions
- Best practice inquiries
- Hardening script generation
- Compliance guidance
- Threat mitigation strategies
        """,
    },
    {
        "name": "rag",
        "description": """
## 🔍 RAG - Retrieval Augmented Generation

**Direct semantic search** over CIS Benchmark knowledge base.

### Features:
- 📚 **Vector Search** - Sentence transformer embeddings
- 🎯 **Relevance Filtering** - Configurable similarity thresholds
- 📄 **Multi-Document Support** - Ubuntu, Debian, RHEL, Windows
- 🔗 **Source Metadata** - Section references and scores

### Use Cases:
- Quick document lookups
- Specific section retrieval
- Compliance reference checks
- Backward compatibility with old clients
        """,
    },
    {
        "name": "health",
        "description": """
## ❤️ Health - System Status & Diagnostics

**Real-time service health** monitoring and diagnostics.

### Endpoints:
- ✅ `/health` - Overall system status
- 🔍 `/health/detailed` - Component-level health
- 🧪 `/health/dependencies` - External service status

### Checks:
- API availability
- LLM provider connectivity
- RAG system functionality
- Database connections
- Memory usage
        """,
    },
    {
        "name": "monitoring",
        "description": """
## 📊 Monitoring - Performance Analytics

**Comprehensive metrics** and performance tracking.

### Endpoints:
- 📈 `/metrics` - Aggregated statistics
- ❌ `/metrics/errors` - Error logs and diagnostics
- 🐌 `/metrics/slow` - Slow request analysis
- 📊 `/analytics/summary` - Usage dashboard

### Metrics Tracked:
- Request latency (p50, p95, p99)
- Token usage and costs
- Error rates and types
- Provider distribution
- User interaction patterns
        """,
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

    # Advanced analytics
    app.include_router(analytics_router, prefix="/api", tags=["monitoring"])

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
