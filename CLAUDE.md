# CLAUDE.md — AI-Powered OS Hardening

This file provides guidance for AI assistants working in this codebase.

---

## Project Overview

**AI-Powered OS Hardening** is a Python/FastAPI backend that provides RAG + LLM-based security hardening guidance for operating systems. It was built as a Marmara University Computer Engineering graduation project.

Core capabilities:
- Answers OS security questions by semantically searching CIS Benchmark PDFs (RAG)
- Generates platform-specific hardening scripts via LLM
- Routes requests through a 4-layer security pipeline (Safety → Intent → Routing → Generation)
- Classifies user intent with a local ML model (90.48% accuracy, 5–10ms, $0 cost)
- Supports streaming responses via Server-Sent Events (SSE)
- Provider fallback chain: Groq → OpenAI → Ollama

**API base**: `http://localhost:8000` | **Swagger UI**: `/docs` | **Metrics**: `/metrics`

---

## Repository Layout

```
ai-powered-os-hardening/
├── main.py                    # FastAPI app factory + middleware registration
├── requirements.txt           # Production dependencies
├── .env / .env.example        # Environment variables (API keys, model config)
├── config/
│   ├── config.json            # RAG, embedding, vector store settings
│   ├── config_loader.py       # Loads config.json
│   └── schemas.py             # Pydantic schemas for config
├── api/                       # FastAPI routers and middleware
│   ├── router_chat.py         # POST /api/chat, POST /api/chat/stream
│   ├── router_rag.py          # POST /rag/search
│   ├── router_health.py       # GET /health, /health/detailed
│   ├── router_analytics.py    # GET /api/analytics/summary
│   ├── schemas.py             # Shared Pydantic models
│   ├── security.py            # RateLimitMiddleware, input validation, output sanitization
│   ├── middleware.py          # RequestIDMiddleware, ResponseMetadataMiddleware, ProviderHeadersMiddleware
│   ├── metrics.py             # MetricsMiddleware + metrics_collector
│   ├── errors.py              # APIError, ErrorCode, error handlers
│   └── streaming.py           # SSE streaming helpers
├── llm/                       # LLM pipeline and clients
│   ├── __init__.py
│   ├── core/
│   │   ├── context.py         # RequestContext (central pipeline state object)
│   │   ├── config.py          # CONFIG singleton (reads .env)
│   │   └── session_store.py   # In-memory session state
│   ├── pipelines/
│   │   ├── secure_v2.py       # SecurePipelineV2 — primary 4-layer pipeline
│   │   ├── optimized.py       # OptimizedPipeline — complexity-routing pipeline
│   │   └── layers/
│   │       ├── safety_classifier.py      # Layer 1: LLM-based threat detection
│   │       ├── hybrid_intent_detector.py # Layer 2: Pattern + ML intent classification
│   │       ├── pattern_responder.py      # Layer 3A: Instant smalltalk responses
│   │       ├── info_pipeline.py          # Layer 3B: RAG + LLM for info queries
│   │       ├── action_pipeline.py        # Layer 3C: Hardening script generation
│   │       ├── zt_enrichment.py          # Zero Trust principles enrichment
│   │       └── output_validator.py       # Output safety validation
│   ├── clients/
│   │   ├── __init__.py        # get_llm_clients() factory
│   │   ├── groq_client.py     # Groq API (primary — free tier)
│   │   ├── openai_client.py   # OpenAI API (fallback)
│   │   ├── ollama_client.py   # Ollama local (offline fallback)
│   │   ├── huggingface_client.py
│   │   ├── adaptive_router.py # Complexity-based model selection
│   │   └── fallback_handler.py
│   ├── ml/
│   │   ├── intent_detector.py            # Logistic Regression + TF-IDF classifier
│   │   └── models/
│   │       ├── intent_model.joblib       # Trained model (do not delete)
│   │       └── intent_vectorizer.joblib  # TF-IDF vectorizer (do not delete)
│   ├── prompts/
│   │   ├── cot_prompts.py     # Chain-of-Thought prompts for complex queries
│   │   ├── few_shot_examples.py
│   │   └── simple_prompts.py  # Minimal prompts for simple/medium queries
│   ├── rag/
│   │   └── integration.py     # RAG context builder used by pipelines
│   ├── utils/
│   │   ├── logger.py
│   │   ├── monitoring.py
│   │   ├── analytics_collector.py
│   │   ├── input_validator.py
│   │   ├── output_validator.py
│   │   ├── local_responder.py     # Zero-cost pattern-matched responses
│   │   ├── question_classifier.py # simple/medium/complex classifier
│   │   ├── parameter_inference.py
│   │   └── langchain_helpers.py
│   ├── cli/
│   │   └── chat.py            # CLI chat interface
│   ├── examples/              # Usage examples
│   ├── tests/                 # LLM-specific tests (pipeline_evaluator, etc.)
│   └── archive/               # Deprecated step-based pipeline (do not use)
├── core/                      # RAG core components
│   ├── chunking/
│   │   ├── base.py
│   │   ├── pdf_chunker.py
│   │   └── Semantic_pdf_chunker.py
│   ├── embeddings/
│   │   ├── base.py
│   │   ├── embeddings.py
│   │   ├── novita_embeddings.py   # Primary: Novita (4096-dim qwen3-embedding-8b)
│   │   └── cohere_embeddings.py
│   ├── vector_store/
│   │   ├── base.py
│   │   ├── vector_store.py
│   │   └── qdrant_store.py        # Qdrant cloud vector store
│   ├── retrieval/
│   │   └── rag_retriever.py
│   ├── indexing/
│   │   └── index_pipeline.py
│   └── metadata/
│       └── cis_benchmark_parser.py
├── data/
│   ├── source/
│   │   └── CIS_Ubuntu_Linux_24.04_LTS_Benchmark_v1.0.0.pdf  # Source document
│   ├── rules/
│   │   └── ubuntu_24_04_rules.yaml
│   └── intent_training_dataset.csv   # 1677 examples across 7 intent categories
├── scripts/
│   └── build_index_ubuntu.py   # Build Qdrant index from PDF
├── src/
│   └── config_manager.py
├── tests/                      # Main test suite
│   ├── README.md
│   ├── unit/
│   │   └── test_novita_embedding.py
│   ├── integration/
│   │   ├── test_rag_llm_integration.py
│   │   ├── test_rag_query.py
│   │   ├── test_rag_api.py
│   │   └── test_comprehensive_pipeline.py
│   └── system/
│       └── test_comprehensive_system.py
└── docs/                       # Documentation (Turkish + English)
    ├── 01_PROJE_OZETI.md through 09_*.md   # Turkish docs
    ├── 10_ARCHITECTURE_ANALYSIS.md          # English: architecture & weaknesses
    ├── 11_PERFORMANCE_ANALYSIS.md           # English: performance benchmarks
    ├── 12_FRONTEND_INTEGRATION.md           # English: React/Vue/SSE integration
    └── archive/                             # Old documentation
```

---

## Key Architecture: 4-Layer Security Pipeline

The primary pipeline is `SecurePipelineV2` (`llm/pipelines/secure_v2.py`). Every request flows through:

```
User Input
    ↓
[Layer 1] Safety Classification   — Groq Llama 8B, ~200ms
    ↓ categories: safe_defensive | safe_educational | ambiguous | unsafe_offensive | unsafe_spam
    ↓ unsafe → REJECT immediately
[Layer 2] Intent Detection        — Pattern matching (<1ms) + ML fallback (5–10ms)
    ↓ intents: greeting | farewell | thanks | help | info_request | action_request | out_of_scope
[Layer 3] Routing
    ├── 3A Pattern Responder      — Greeting/thanks/help → instant template response ($0)
    ├── 3B Info Pipeline          — Info questions → RAG search + LLM answer
    ├── 3C Action Pipeline        — Script requests → CoT generation + strict validation
    └── Out-of-Scope              — Polite rejection
[Layer 4] Adaptive Generation
    ├── Simple queries → llm_small (Llama 3.1 8B)
    ├── Complex queries → llm_large (Llama 3.3 70B)
    └── RAG context injected when relevant
```

**Central state object**: `RequestContext` (`llm/core/context.py`) — a Pydantic model passed through every layer.

---

## Development Setup

### Prerequisites
- Python 3.12+
- Qdrant (cloud or local Docker)
- API keys: Groq (required), Novita (required for RAG), optionally OpenAI

### Installation

```bash
git clone <repo>
cd ai-powered-os-hardening

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env: set GROQ_API_KEY, NOVITA_API_KEY, QDRANT_API_KEY

# Fix PYTHONPATH if imports fail
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Start API server
python main.py
# → http://localhost:8000
# → Swagger UI: http://localhost:8000/docs
```

### Qdrant (local development)

```bash
docker run -p 6333:6333 qdrant/qdrant
```

### Build RAG Index (first time or after PDF update)

```bash
python scripts/build_index_ubuntu.py
```

---

## Environment Variables (`.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | Primary provider: `groq`, `openai`, `ollama` | `groq` |
| `GROQ_API_KEY` | Groq API key (free tier) | required |
| `GROQ_SMALL_MODEL_NAME` | Fast/cheap model | `llama-3.1-8b-instant` |
| `GROQ_LARGE_MODEL_NAME` | Powerful model | `llama-3.3-70b-versatile` |
| `OPENAI_API_KEY` | OpenAI key (fallback) | optional |
| `NOVITA_API_KEY` | Novita embeddings key | required for RAG |
| `QDRANT_API_KEY` | Qdrant cloud key | required for RAG |
| `SMALL_MODEL_TEMPERATURE` | Temperature for small model | `0.3` |
| `LARGE_MODEL_TEMPERATURE` | Temperature for large model | `0.2` |
| `MAX_TOKENS` | Max response tokens | `2048` |
| `REQUEST_TIMEOUT` | API timeout (seconds) | `60` |
| `MAX_RETRIES` | Retry attempts on failure | `2` |
| `ENABLE_DEBUG_LOGS` | Verbose pipeline logging | `false` |
| `ENABLE_JUDGE_STEP` | Output quality checking | `true` |
| `ENABLE_CORRECTION_STEP` | Auto-correct bad outputs | `true` |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Main chat: RAG + LLM + 4-layer pipeline |
| `POST` | `/api/chat/stream` | Streaming version (SSE) |
| `POST` | `/rag/search` | Direct RAG semantic search |
| `GET` | `/health` | Service health status |
| `GET` | `/health/detailed` | Component-level health |
| `GET` | `/metrics` | Aggregated performance stats |
| `GET` | `/metrics/errors` | Recent error log |
| `GET` | `/metrics/slow` | Slowest requests |
| `GET` | `/api/analytics/summary` | Usage analytics dashboard |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/redoc` | ReDoc UI |

### `/api/chat` Request Schema

```json
{
  "question": "How do I harden SSH on Ubuntu 24.04?",
  "os": "ubuntu_24_04",
  "role": "sysadmin",
  "security_level": "balanced",
  "zt_maturity": "medium",
  "use_rag": true,
  "rag_top_k": 5,
  "rag_min_score": 0.7,
  "stream": false,
  "timeout": 60
}
```

### `/api/chat` Response Schema

```json
{
  "answer": "...",
  "intent": "action_request",
  "safety_category": "safe_defensive",
  "layer_path": "1->2->3C->4",
  "rag_sources": [{"id": "source_1", "score": 0.85, "source": "CIS Ubuntu 24.04", "section": "5.2.4"}],
  "stats": {"total_time_s": 4.2, "layer_path": "1->2->3C->4"},
  "request_id": "req_abc123",
  "estimated_cost": 0.0025
}
```

---

## Coding Conventions

### Python Style
- **Python 3.12+** — use modern type hints
- `from __future__ import annotations` at top of all files
- Type hints are **required** for all function parameters and return values
- Pydantic models for all data structures (see `llm/core/context.py` for patterns)
- Docstrings required for all public classes and functions

### Pydantic Patterns
- Use `BaseModel` with `Field(...)` for required fields and documentation
- Use `Field(default_factory=list)` for mutable defaults
- Use `Literal[...]` for constrained string types
- Use `ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)` on context models

### Pipeline Development
- All pipeline layers receive and return `RequestContext`
- Do not mutate context fields directly without type-safe setters
- Use `ctx.extra` dict for ad-hoc metadata that doesn't belong in the schema
- Wrap external API calls (LLM, RAG) in try/except; never let exceptions propagate unhandled to the user

### LLM Client Convention
- LLM clients are callables: `LLMCallable = Callable[[str], str]`
- Get initialized clients from `llm/clients/__init__.py`: `from llm.clients import get_llm_clients`
- Two tiers: `llm_small` (fast/cheap) and `llm_large` (powerful/expensive)
- Never hardcode model names — read from `CONFIG` or `.env`

### Error Handling
- Use `APIError(status_code, error_code, message, details)` for all API-level errors
- Use `ErrorCode` enum from `api/errors.py` for error classification
- Pipeline errors should always produce a user-facing answer, not a raw exception

### Security Rules
- Never disable input validation — `api/security.py` `validate_chat_input()` must run on all user text
- Always call `sanitize_output()` before returning LLM responses to clients
- Do not widen CORS or trusted host settings in production without explicit sign-off
- Rate limit is 100 req/min per IP — do not bypass

---

## Testing

### Running Tests

```bash
# All tests
python -m pytest tests/

# By category
python -m pytest tests/unit/
python -m pytest tests/integration/
python -m pytest tests/system/

# With coverage report
python -m pytest tests/ --cov=llm --cov-report=html

# LLM-specific pipeline tests
python llm/tests/run_all_tests.py
```

### Test Requirements
- `.env` must have `GROQ_API_KEY` and `NOVITA_API_KEY` set
- Qdrant must be running for integration tests
- Tests are independent — no shared state between test cases

### Test Coverage Targets
| Area | Current | Target |
|------|---------|--------|
| RAG System | 100% | 100% |
| ML Intent Detection | 100% | 100% |
| LLM Integration | 100% | 100% |
| API Endpoints | 70% | >80% |
| Safety Layer | 100% | 100% |

### Missing Tests (TODO)
- Streaming endpoint (`/api/chat/stream`)
- Provider fallback chain
- Timeout handling
- Rate limiting behavior

### Test Standards
1. Follow pytest conventions (functions named `test_*`)
2. Include docstrings explaining what each test validates
3. No inter-test dependencies (each test is self-contained)
4. Clean up any created resources in teardown
5. Use meaningful assertions with helpful failure messages

---

## ML Intent Detection

The hybrid intent detector (`llm/pipelines/layers/hybrid_intent_detector.py`) runs in two stages:

1. **Pattern matching** (72% coverage, <1ms) — regex/keyword rules, no API cost
2. **ML fallback** (28% coverage, 5–10ms) — Logistic Regression + TF-IDF (`llm/ml/intent_detector.py`)

**Do not delete** `llm/ml/models/intent_model.joblib` or `llm/ml/models/intent_vectorizer.joblib` — these are pre-trained artifacts.

To retrain: use `data/intent_training_dataset.csv` (1677 examples, 7 categories).

Intent categories:
- `greeting`, `farewell`, `thanks`, `help` → Pattern Responder (3A)
- `info_request` → Info Pipeline (3B)
- `action_request` → Action Pipeline (3C)
- `out_of_scope` → Polite rejection

---

## RAG System

### Architecture
- **Embeddings**: Novita `qwen/qwen3-embedding-8b` (4096 dimensions) via `core/embeddings/novita_embeddings.py`
- **Vector Store**: Qdrant cloud (`core/vector_store/qdrant_store.py`)
- **Chunking**: Semantic PDF chunking with sliding window (`core/chunking/`)
- **Source document**: `data/source/CIS_Ubuntu_Linux_24.04_LTS_Benchmark_v1.0.0.pdf`

### Smart RAG Triggering
RAG is only invoked for security-relevant queries — approximately 45% of queries skip RAG entirely (greetings, generic questions), reducing latency and cost.

### Config (`config/config.json`)
```json
{
  "embedding": { "provider": "novita", "model_name": "qwen/qwen3-embedding-8b", "dim": 4096 },
  "vector_store": { "provider": "qdrant", "qdrant": { "collection_name": "cis_ubuntu_24_04" } }
}
```

---

## Middleware Stack (Order in `main.py`)

Middleware is applied in **reverse order** (last added = first executed on requests):

1. `CORSMiddleware` — Allow cross-origin requests
2. `TrustedHostMiddleware` — Host validation
3. `GZipMiddleware` — Response compression (>1KB)
4. `RateLimitMiddleware` — 100 req/min per IP, 5-min ban
5. `MetricsMiddleware` — Latency/error tracking
6. `RequestIDMiddleware` — Assign `X-Request-ID`
7. `ResponseMetadataMiddleware` — Inject processing time, version headers
8. `ProviderHeadersMiddleware` — Inject `X-LLM-Provider`, `X-LLM-Model`
9. `SecurityHeadersMiddleware` — CSP, HSTS, X-Frame-Options, etc.

---

## Performance Targets

| Component | Target Latency |
|-----------|---------------|
| Pattern response (3A) | <20ms |
| Simple info (no RAG) | ~1.2s |
| Medium info (with RAG) | ~2.5s |
| Complex CoT + RAG | ~4.2s |
| Script generation | ~4.5s |
| ML intent detection | 5–10ms |
| RAG embedding | ~2.1s |

**Cost target**: $0.0004 average per query (free-tier Groq).

---

## Known Limitations / Production Blockers

The following are missing for production readiness (see `docs/10_ARCHITECTURE_ANALYSIS.md`):

- **Authentication** (P0 critical) — No API key or user auth implemented
- **Authorization** (P0 critical) — No RBAC
- **Redis embedding cache** (P1) — RAG is slow without it (~2.1s per embedding)
- **DDoS protection** (P1) — Rate limiting alone is insufficient
- **HTTPS/SSL** (P0) — Must configure before public deployment
- **Streaming tests** — Not yet covered by test suite

---

## Documentation

| File | Language | Contents |
|------|----------|----------|
| `docs/01_PROJE_OZETI.md` | Turkish | Project overview |
| `docs/02_PIPELINE_VE_ROUTELAR.md` | Turkish | Pipeline & routing details |
| `docs/03_KURULUM_VE_KULLANIM.md` | Turkish | Setup & usage |
| `docs/04_API_DOKUMANTASYONU.md` | Turkish | API documentation |
| `docs/05_TEKNOLOJILER.md` | Turkish | Technology stack rationale |
| `docs/06_LLM_UYGULAMALARI.md` | Turkish | LLM applications |
| `docs/07_RAG_SISTEMI.md` | Turkish | RAG system details |
| `docs/08_TEST_DOKUMANTASYONU.md` | Turkish | Testing methodology |
| `docs/09_GELECEK_IYILESTIRMELER.md` | Turkish | Future improvements roadmap |
| `docs/10_ARCHITECTURE_ANALYSIS.md` | English | Architecture analysis & 12 weaknesses |
| `docs/11_PERFORMANCE_ANALYSIS.md` | English | Performance benchmarks |
| `docs/12_FRONTEND_INTEGRATION.md` | English | React/Vue/SSE integration guide |
| `docs/archive/` | Mixed | Deprecated/historical docs |
| `llm/archive/` | Mixed | Deprecated step-based pipeline code |

---

## Git Workflow

- Branch naming: feature branches should be descriptive (e.g., `feat/redis-cache`)
- Commit message format follows conventional commits: `type: description`
  - Types: `feat`, `fix`, `docs`, `refactor`, `test`, `security`, `perf`
- Run `python -m pytest tests/` before committing
- Do not commit `.env` (it's gitignored) — use `.env.example` for documentation

---

## Common Troubleshooting

| Issue | Solution |
|-------|----------|
| `ImportError` on startup | `export PYTHONPATH="${PYTHONPATH}:$(pwd)"` |
| API key not found | Check `.env` file exists and has correct keys |
| Qdrant connection failed | `docker run -p 6333:6333 qdrant/qdrant` |
| Slow RAG queries | Add Redis embedding cache (see `docs/10_ARCHITECTURE_ANALYSIS.md`) |
| ML model not found | Ensure `llm/ml/models/*.joblib` files are present |
| sklearn compatibility error | Re-train model with current sklearn version using `data/intent_training_dataset.csv` |
