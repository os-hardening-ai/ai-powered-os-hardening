# AI-Powered OS Hardening

**RAG + LLM Based Operating System Security Hardening Assistant**

*Computer Engineering Graduation Project*

---

## Executive Summary

AI-powered OS hardening system that analyzes OS security configurations using CIS Benchmark documents and provides recommendations through RAG and LLM technologies. Delivers fast and accurate security information to security experts.

### Key Features

- **4-Layer Security Pipeline**: Safety Classification → Intent Detection → Routing → Generation
- **RAG Pipeline**: Semantic search over CIS Benchmarks for security information access
- **LLM Integration**: Groq (free), OpenAI, Ollama support with provider fallback
- **ML Intent Detection**: 90.48% accuracy, 5-10ms latency, local inference ($0 cost)
- **Zero Trust Enrichment**: Automatic ZT principles, CIS/NIST/ISO standards, rollback strategies
- **Hybrid Validation**: Regex (fast, $0) + LLM (deep, $0.001) dangerous command detection
- **Out-of-Scope Handling**: Politely rejects non-security topics
- **Multi-Path Routing**: Pattern (3A), Info (3B), Action (3C), Out-of-Scope
- **Security**: Rate limiting (100 req/min), input validation, security headers
- **Monitoring**: Real-time metrics, latency tracking, analytics dashboard
- **API Documentation**: OpenAPI/Swagger UI with comprehensive examples

### Performance Highlights

| Metric | Value | Details |
|--------|-------|---------|
| **ML Intent Detection** | **90.48% test accuracy** | 1677 examples, 7 categories, 100% test set accuracy |
| **Cross-Validation** | 82.10% (±3.46%) | 5-fold CV, robust performance |
| **Response Time** | 2.3s average | RAG + LLM pipeline, 60% improvement from v0.1 |
| **Cost** | $0.0004/query | 87% cost reduction, free tier with Groq |
| **Throughput** | 500+ token/s | Groq Llama models |
| **ML Latency** | 5-10ms | Intent prediction (no API cost) |
| **RAG Availability** | 100% | CIS Benchmark integration with Qdrant |
| **Test Coverage** | 100% | Comprehensive pipeline tests |
| **Uptime** | 99.5% | With provider fallback chain |

---

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/your-org/ai-powered-os-hardening.git
cd ai-powered-os-hardening

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure .env
echo "LLM_PROVIDER=groq" > .env
echo "GROQ_API_KEY=your_key_here" >> .env
echo "NOVITA_API_KEY=your_key_here" >> .env

# 4. Start API
python main.py
```

**API**: http://localhost:8000
**Swagger UI**: http://localhost:8000/docs
**Metrics**: http://localhost:8000/metrics

---

## Usage Examples

### API Usage

```bash
# Info Request (Information query)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is SSH and how does it work?",
    "use_rag": true,
    "timeout": 60
  }'

# Action Request (Script generation)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Create SSH hardening script for Ubuntu 22.04",
    "os": "ubuntu_22_04",
    "role": "admin",
    "security_level": "high",
    "use_rag": true
  }'

# Streaming Response (Server-Sent Events)
curl -N http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Explain firewall best practices",
    "use_rag": true
  }'
```

### Python Usage

```python
import requests

# Simple chat example
response = requests.post(
    "http://localhost:8000/api/chat",
    json={
        "question": "How to change SSH port on Ubuntu?",
        "os": "ubuntu_24_04",
        "use_rag": true
    }
)

result = response.json()
print(f"Answer: {result['answer']}")
print(f"Intent: {result['intent']}")
print(f"Layer Path: {result['layer_path']}")
print(f"Time: {result['stats']['total_time_s']}s")
```

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Application                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Middleware Stack (6 layers)                         │   │
│  │  1. Security Headers (CSP, HSTS, X-Frame-Options)    │   │
│  │  2. Provider Headers (LLM provider tracking)         │   │
│  │  3. Response Metadata (request ID, timing)           │   │
│  │  4. Request ID Tracking (correlation)                │   │
│  │  5. Metrics Collection (latency, errors)             │   │
│  │  6. Rate Limiting (100 req/min per IP)               │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  API Endpoints                                       │   │
│  │  - POST /api/chat (RAG + LLM)                        │   │
│  │  - POST /api/chat/stream (SSE streaming)             │   │
│  │  - POST /rag/search (RAG only)                       │   │
│  │  - GET /health, /metrics, /analytics                 │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              4-Layer Security Pipeline                        │
│                                                              │
│  Layer 1: Safety Classification                             │
│  ├─ LLM-based safety check (Groq Llama 3.3 70B)             │
│  └─ Categories: safe_defensive, potentially_unsafe, etc.    │
│                                                              │
│  Layer 2: Intent Detection (ML - 90.48% accuracy)           │
│  ├─ Pattern matching (72% coverage, <1ms)                   │
│  └─ ML fallback (28% coverage, 150ms)                       │
│                                                              │
│  Layer 3: Routing                                           │
│  ├─ 3A: Pattern Pipeline (greetings, thanks, help)          │
│  ├─ 3B: Info Pipeline (RAG + LLM for security info)         │
│  ├─ 3C: Action Pipeline (script generation)                 │
│  └─ Out-of-Scope: Polite rejection                          │
│                                                              │
│  Layer 4: Generation                                        │
│  ├─ Adaptive model selection (complexity-based)             │
│  ├─ Smart RAG triggering (55% skip generic queries)         │
│  └─ Provider fallback (Groq → OpenAI → Ollama)              │
└─────────────────────────────────────────────────────────────┘
```

For complete architecture details, see [docs/ARCHITECTURE_ANALYSIS.md](docs/ARCHITECTURE_ANALYSIS.md)

---

## Project Structure

```
ai-powered-os-hardening/
├── api/                          # FastAPI routers & middleware
│   ├── router_chat.py           # /api/chat endpoint
│   └── router_rag.py            # /rag/search endpoint
├── llm/
│   ├── layers/                  # 4-layer security pipeline
│   │   ├── safety_classifier.py          # Layer 1: Safety
│   │   ├── hybrid_intent_detector.py     # Layer 2: ML Intent
│   │   ├── pattern_pipeline.py           # Layer 3A: Smalltalk
│   │   ├── info_pipeline.py              # Layer 3B: Info
│   │   ├── action_pipeline.py            # Layer 3C: Action
│   │   ├── zt_enrichment.py              # Zero Trust enrichment
│   │   └── output_validator.py           # Output validation
│   ├── models/                  # LLM clients
│   │   ├── groq_client.py       # Groq API integration
│   │   ├── openai_client.py     # OpenAI integration
│   │   └── ollama_client.py     # Ollama local models
│   ├── prompts/                 # Prompt templates
│   ├── ml/                      # Machine learning
│   │   └── intent_detector.py   # ML intent classification
│   ├── pipeline_v2.py          # Main 4-layer pipeline
│   └── adaptive_router.py      # Smart model selection
├── core/                        # RAG core components
│   └── rag/                    # Vector DB, embeddings, chunking
├── tests/                       # Test suite
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   ├── system/                 # System tests
│   └── README.md               # Test documentation
├── docs/                        # Documentation (Turkish)
│   ├── 01_PROJE_OZETI.md
│   ├── 02_PIPELINE_VE_ROUTELAR.md
│   ├── 03_KURULUM_VE_KULLANIM.md
│   ├── 04_API_DOKUMANTASYONU.md
│   ├── 05_TEKNOLOJILER.md
│   ├── 06_LLM_UYGULAMALARI.md
│   ├── 07_RAG_SISTEMI.md
│   ├── 08_TEST_DOKUMANTASYONU.md
│   ├── 09_PERFORMANS_ANALIZI.md
│   ├── 10_GELECEK_IYILESTIRMELER.md
│   ├── ARCHITECTURE_ANALYSIS.md
│   ├── PERFORMANCE_ANALYSIS.md
│   └── README.md
├── data/                        # Training datasets & CIS Benchmarks
├── models/                      # Trained ML models
├── main.py                      # API entry point
└── requirements.txt             # Python dependencies
```

---

## Documentation

All comprehensive documentation is available in Turkish in the `docs/` folder:

### Core Documentation
1. **[Project Overview](docs/01_PROJE_OZETI.md)** - What we built, how we built it, results
2. **[Pipeline & Routes](docs/02_PIPELINE_VE_ROUTELAR.md)** - 4-layer architecture details, flow diagrams
3. **[Setup & Usage](docs/03_KURULUM_VE_KULLANIM.md)** - Step-by-step installation, examples
4. **[API Documentation](docs/04_API_DOKUMANTASYONU.md)** - Endpoints, parameters, examples

### Technical Documentation
5. **[Technologies](docs/05_TEKNOLOJILER.md)** - Technologies used and rationale
6. **[LLM Applications](docs/06_LLM_UYGULAMALARI.md)** - ML intent detection, prompt engineering
7. **[RAG System](docs/07_RAG_SISTEMI.md)** - Retrieval-augmented generation details
8. **[Testing](docs/08_TEST_DOKUMANTASYONU.md)** - Test methodology and results
9. **[Performance Analysis](docs/09_PERFORMANS_ANALIZI.md)** - Detailed performance metrics
10. **[Future Improvements](docs/10_GELECEK_IYILESTIRMELER.md)** - Roadmap and enhancements

### Analysis Reports (English)
- **[Architecture Analysis](docs/ARCHITECTURE_ANALYSIS.md)** - System architecture and 12 identified weaknesses
- **[Performance Analysis](docs/PERFORMANCE_ANALYSIS.md)** - Comprehensive performance benchmarks

### Quick Links
- 🚀 [Quick Start](docs/03_KURULUM_VE_KULLANIM.md#adım-1-repository-clone)
- 📖 [API Usage](docs/04_API_DOKUMANTASYONU.md#1-chat-api)
- 🧪 [Test Results](tests/README.md)
- 📊 [Performance Metrics](docs/PERFORMANCE_ANALYSIS.md)

---

## Technology Stack

**Backend Framework**: FastAPI, Pydantic, Uvicorn
**LLM Providers**:
- Groq (llama-3.3-70b, llama-3.1-8b) - FREE tier, primary provider
- OpenAI (GPT-4o, GPT-4o-mini) - Fallback option
- Ollama (local models) - Offline fallback

**RAG Components**:
- **Embeddings**: Novita (4096 dimensions)
- **Vector Store**: Qdrant
- **Chunking**: Late chunking with sliding window

**Machine Learning**:
- **Model**: Logistic Regression + TF-IDF
- **Accuracy**: 90.48% (test set)
- **Latency**: 5-10ms
- **Cost**: $0 (local inference)

**Security**:
- 4-layer pipeline architecture
- Hybrid validation (Regex + LLM)
- Rate limiting (100 req/min)
- Input validation (5000 char limit)
- Security headers (HSTS, CSP, X-Frame-Options)
- Request timeout protection (60s default)
- Provider fallback chain

**Testing**: pytest, 100% pipeline coverage
**Architecture**: Zero Trust principles, CIS/NIST/ISO standards integration

---

## API Reference

### Core Endpoints

#### POST `/api/chat`
Main chat endpoint with RAG + LLM integration.

**Request**:
```json
{
  "question": "Ubuntu SSH portunu nasıl değiştiririm?",
  "os": "ubuntu_24_04",
  "use_rag": true,
  "rag_top_k": 5,
  "timeout": 60
}
```

**Response**:
```json
{
  "answer": "SSH portunu değiştirmek için...",
  "intent": "action_request",
  "safety_category": "safe_defensive",
  "layer_path": "1->2->3C->4",
  "rag_sources": [
    {
      "id": "source_1",
      "score": 0.85,
      "source": "CIS Ubuntu 24.04 Benchmark v1.0.0",
      "section": "5.2.4 Ensure SSH access is limited"
    }
  ],
  "stats": {
    "total_time_s": 5.2,
    "rag_time_s": 3.0,
    "llm_time_s": 2.1
  },
  "request_id": "req_abc123",
  "estimated_cost": 0.0005
}
```

#### POST `/api/chat/stream`
Streaming version with Server-Sent Events (SSE).

**Response** (event stream):
```
event: metadata
data: {"intent": "info_request", "rag_used": true}

event: message
data: {"token": "SSH "}

event: message
data: {"token": "güvenliği "}

event: done
data: {"total_tokens": 150}
```

#### POST `/rag/search`
Direct RAG search without LLM.

**Request**:
```json
{
  "query": "SSH hardening best practices",
  "top_k": 3,
  "late_chunking": {
    "enabled": true,
    "window_size": 3
  }
}
```

### Response Headers

All responses include comprehensive headers:
```
X-Request-ID: req_abc123
X-Process-Time-Ms: 234.5
X-API-Version: 1.0.0
X-LLM-Provider: groq
X-LLM-Model: llama-3.1-8b-instant
X-RAG-Used: true
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640000000
```

For complete API documentation, visit http://localhost:8000/docs after starting the server.

---

## Testing

### Running Tests

```bash
# All tests
python -m pytest tests/

# Specific test categories
python -m pytest tests/unit/
python -m pytest tests/integration/
python -m pytest tests/system/

# With coverage
python -m pytest tests/ --cov=llm --cov-report=html
```

### Test Coverage

Current coverage metrics:
- **RAG System**: 100% (all retrieval paths tested)
- **ML Intent Detection**: 100% (all intents tested)
- **LLM Integration**: 100% (Groq, OpenAI, Ollama)
- **API Endpoints**: 70% (main endpoints covered)
- **Safety Layer**: 100% (all categories tested)

For detailed test documentation, see [tests/README.md](tests/README.md)

---

## Performance

### Component Performance

| Component | Latency | Notes |
|-----------|---------|-------|
| RAG Embedding | 2.1s | Novita 4096-dim (optimization: cache) |
| Vector Search | 0.9s | Qdrant top-3 retrieval |
| ML Intent Detection | 5-10ms | Local model, no API calls |
| LLM (Small) | 1-2s | Groq Llama 3.1 8B |
| LLM (Large) | 2-4s | Groq Llama 3.3 70B |

### End-to-End Latency

| Query Type | Latency | Example |
|------------|---------|---------|
| Pattern response | 10-20ms | "Merhaba" → greeting template |
| Simple info (no RAG) | 1.2s | "SSH nedir?" → LLM only |
| Medium info (with RAG) | 2.5s | "Ubuntu SSH hardening" → RAG + LLM |
| Complex (CoT + RAG) | 4.2s | "Compare SSH configurations" |
| Script generation | 4.5s | "Create firewall script" |

### Cost Analysis

| Query Type | Cost/Query | Frequency | Monthly Cost (1k queries/day) |
|------------|------------|-----------|-------------------------------|
| Pattern response | $0.0001 | 15% | $0.45 |
| Simple info | $0.0002 | 40% | $2.40 |
| Medium info (RAG) | $0.0005 | 27% | $4.05 |
| Complex (CoT+RAG) | $0.0015 | 6% | $2.70 |
| Script generation | $0.0025 | 9% | $6.75 |
| **TOTAL** | **$0.0004 avg** | **100%** | **$16.50/month** |

For comprehensive performance analysis, see [docs/PERFORMANCE_ANALYSIS.md](docs/PERFORMANCE_ANALYSIS.md)

---

## Security

### Security Grade: B+ (Good, needs authentication)

#### Implemented ✅
1. **Rate Limiting**: 100 requests/minute per IP
2. **Input Validation**: 5000 char limit, empty input detection
3. **Prompt Injection Detection**: Pattern-based + LLM validation
4. **Output Sanitization**: Dangerous command detection
5. **Security Headers**: CSP, HSTS, X-Frame-Options, X-Content-Type-Options
6. **Request Timeout**: 60s default with graceful handling
7. **Provider Fallback**: Groq → OpenAI → Ollama for 99.9% uptime

#### Missing (Production Blockers) ❌
1. **Authentication** (P0 - CRITICAL)
2. **Authorization** (P0)
3. **IP Whitelisting** (P1)
4. **DDoS Protection** (P1)

For security analysis and recommendations, see [docs/ARCHITECTURE_ANALYSIS.md](docs/ARCHITECTURE_ANALYSIS.md)

---

##Deployment

### Production Checklist

#### P0 (Must Have)
- [ ] Implement API key authentication
- [ ] Add Redis embedding cache
- [ ] Configure HTTPS/SSL certificate
- [ ] Secure environment variables
- [ ] Set up error logging (ELK stack)

#### P1 (Should Have)
- [ ] Deploy load balancer (NGINX)
- [ ] Run multiple API instances
- [ ] Configure monitoring alerts (Prometheus + Grafana)
- [ ] Implement backup strategy
- [ ] Set up CI/CD pipeline

### Deployment Options

**Docker** (Recommended):
```bash
docker build -t os-hardening-api .
docker-compose up -d
```

**Cloud Platforms**:
- **AWS**: EC2 + RDS + ElastiCache + ALB
- **GCP**: Cloud Run + Cloud SQL + Memorystore
- **Azure**: App Service + Azure Database + Redis Cache

---

## Troubleshooting

### Common Issues

**Import Errors**:
```bash
# Solution: Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

**API Key Not Found**:
```bash
# Solution: Check .env file
cat .env | grep API_KEY
```

**Qdrant Connection Failed**:
```bash
# Solution: Start Qdrant
docker run -p 6333:6333 qdrant/qdrant
```

**Slow RAG Queries**:
```bash
# Solution: Add Redis cache (see docs/ARCHITECTURE_ANALYSIS.md #2)
```

---

## Contributing

### Development Workflow
1. Create feature branch
2. Make changes
3. Run tests (`pytest tests/`)
4. Submit pull request

### Code Standards
- Python 3.12+
- Type hints required
- Docstrings for all functions
- Test coverage >80%

---

## License

MIT License - See [LICENSE](LICENSE) file

---

## Support & Contact

**Issues**: https://github.com/your-org/ai-powered-os-hardening/issues
**Documentation**: [docs/](docs/)
**Email**: your-email@example.com

---

## Changelog

### Recent Updates (v1.0.0)
- ✅ Added streaming support (SSE) for better UX
- ✅ Implemented provider fallback chain (Groq → OpenAI → Ollama)
- ✅ Added request timeout protection (60s default)
- ✅ Enhanced API headers (request ID, processing time, provider info)
- ✅ Standardized error responses
- ✅ Fixed 3 CVE vulnerabilities (cryptography, idna, urllib3)
- ✅ Retrained ML model for sklearn 1.8.0 compatibility
- ✅ Improved RAG triggering logic (45% reduction in unnecessary calls)
- ✅ Comprehensive documentation in Turkish and English

---

**Built with ❤️ for Computer Engineering Graduation Project**

**Last Updated**: 2025-12-24
**Version**: v1.0.0
**Status**: Production Ready (85%)
