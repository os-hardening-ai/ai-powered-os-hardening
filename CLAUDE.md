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
- Provider fallback chain: Novita → Groq → OpenAI → Ollama (configurable via `config/config.json`)

**API base**: `http://localhost:8000` | **Swagger UI**: `/docs` | **Metrics**: `/metrics`

---

## Repository Layout

```
ai-powered-os-hardening/
├── main.py                    # FastAPI app factory + middleware registration
├── log_manager.py             # Custom logging setup (get_logger())
├── requirements.txt           # Production dependencies (Python 3.12+)
├── requirements-python311.txt # Python 3.11 compatible dependencies
├── pytest.ini                 # Pytest configuration
├── SECURITY_AUDIT_REPORT.md   # Security audit findings
├── .env / .env.example        # Environment variables (API keys, model config)
├── config/
│   ├── config.json            # RAG, embedding, vector store, LLM settings
│   ├── config_loader.py       # Loads and validates config.json (primary config system)
│   └── schemas.py             # Pydantic schemas for config validation
├── api/                       # FastAPI routers and middleware
│   ├── router_chat.py         # POST /api/chat, POST /api/chat/stream
│   ├── router_rag.py          # POST /rag/search
│   ├── router_health.py       # GET /, GET /health, GET /health/detailed
│   ├── router_analytics.py    # GET /api/analytics/* (6 sub-routes)
│   ├── schemas.py             # Shared Pydantic models (RagSearchRequest, LateChunkingOptions, etc.)
│   ├── security.py            # RateLimitMiddleware, input validation, output sanitization
│   ├── middleware.py          # RequestIDMiddleware, ResponseMetadataMiddleware,
│   │                          #   ProviderHeadersMiddleware, RequestLogMiddleware
│   ├── metrics.py             # MetricsCollector, MetricsMiddleware, AggregatedMetrics
│   ├── errors.py              # APIError, ErrorCode, error handlers
│   └── streaming.py           # SSE streaming helpers
├── llm/                       # LLM pipeline and clients
│   ├── __init__.py
│   ├── core/
│   │   ├── context.py         # RequestContext (central pipeline state), SafetyCategory, IntentType
│   │   ├── config.py          # Legacy Config dataclass (reads .env directly)
│   │   └── session_store.py   # In-memory session state
│   ├── pipelines/
│   │   ├── secure_v2.py       # SecurePipelineV2 — primary 4-layer pipeline
│   │   ├── optimized.py       # OptimizedPipeline — complexity-routing pipeline
│   │   └── layers/
│   │       ├── safety_classifier.py      # Layer 1: LLM-based threat detection
│   │       ├── hybrid_intent_detector.py # Layer 2: Pattern + ML intent classification
│   │       ├── intent_detector.py        # Legacy ML-only intent detector (do not use directly)
│   │       ├── pattern_responder.py      # Layer 3A: Instant smalltalk responses
│   │       ├── info_pipeline.py          # Layer 3B: RAG + LLM for info queries
│   │       ├── action_pipeline.py        # Layer 3C: Hardening script generation
│   │       ├── zt_enrichment.py          # Zero Trust principles enrichment
│   │       └── output_validator.py       # Output safety validation
│   ├── clients/
│   │   ├── __init__.py            # get_llm_clients() factory — returns (llm_small, llm_large)
│   │   ├── groq_client.py         # Groq API (free tier, llama models)
│   │   ├── openai_client.py       # OpenAI API (fallback)
│   │   ├── ollama_client.py       # Ollama local (offline fallback)
│   │   └── novita_llm_client.py   # Novita API (Qwen models — default provider)
│   ├── ml/
│   │   ├── intent_detector.py            # Logistic Regression + TF-IDF classifier
│   │   └── models/
│   │       ├── intent_model.joblib       # Trained model (do not delete)
│   │       └── intent_vectorizer.joblib  # TF-IDF vectorizer (do not delete)
│   ├── prompts/
│   │   ├── cot_prompts.py        # Chain-of-Thought prompts for complex queries
│   │   ├── few_shot_examples.py
│   │   ├── simple_prompts.py     # Minimal prompts for simple/medium queries
│   │   ├── loader.py             # Prompt template loader
│   │   └── templates/            # Prompt template files
│   ├── rag/
│   │   └── integration.py        # RAG context builder used by pipelines
│   ├── utils/
│   │   ├── logger.py
│   │   ├── monitoring.py
│   │   ├── analytics_collector.py
│   │   ├── output_validator.py
│   │   ├── local_responder.py       # Zero-cost pattern-matched responses
│   │   ├── question_classifier.py   # simple/medium/complex classifier
│   │   ├── parameter_inference.py
│   │   └── langchain_helpers.py
│   ├── cli/
│   │   └── __init__.py           # CLI module
│   └── tests/                    # LLM-specific tests
│       ├── test_dataset.py
│       ├── test_safety_classifier.py
│       ├── test_security_features.py
│       ├── unit/
│       └── integration/
├── rag/                      # RAG core components
│   ├── chunking/
│   │   ├── base.py
│   │   ├── pdf_chunker.py
│   │   ├── semantic_pdf_chunker.py
│   │   ├── cis_section_chunker.py    # Chunks CIS PDFs by section number
│   │   └── yaml_rules_chunker.py     # One chunk per CIS rule (includes audit + remediation)
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
│   │   ├── CIS_Ubuntu_Linux_24.04_LTS_Benchmark_v1.0.0.pdf
│   │   └── CIS_Microsoft_Windows_Server_2025_Benchmark_v2.0.0.pdf
│   ├── rules/
│   │   ├── ubuntu_24_04_rules.yaml     # 312 CIS rules with audit + remediation scripts (770KB)
│   │   └── windows_2025_rules.yaml     # Empty — Windows uses PDF only for now
│   ├── cache/                          # Embedding cache directory
│   └── intent_training_dataset.csv     # 1677 examples across 7 intent categories
├── scripts/
│   ├── build_index.py          # Config-driven: indexes all enabled sources from config.json
│   └── start_api.py
├── src/
│   └── config_manager.py
├── logs/                       # Runtime application logs
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
[Layer 1] Safety Classification   — LLM-based, ~200ms
    ↓ categories: defensive_security | offensive_illegal | generic_it | ambiguous
    ↓ offensive_illegal → REJECT immediately
[Layer 2] Intent Detection        — Pattern matching (<1ms) + ML fallback (5–10ms)
    ↓ intents: os_hardening | script_or_config | incident_analysis | conceptual_explanation
    ↓           generic_qna | smalltalk_greeting | smalltalk_farewell | smalltalk_other
[Layer 3] Routing
    ├── 3A Pattern Responder      — Smalltalk (greeting/farewell/other) → instant template ($0)
    ├── 3B Info Pipeline          — Info questions → RAG search + LLM answer
    ├── 3C Action Pipeline        — Script/hardening requests → CoT generation + strict validation
    └── Out-of-Scope              — Polite rejection
[Layer 4] Adaptive Generation
    ├── Simple queries → llm_small
    ├── Complex queries → llm_large
    └── RAG context injected when relevant
```

**Central state object**: `RequestContext` (`llm/core/context.py`) — a Pydantic model passed through every layer. Also defines `SafetyCategory`, `IntentType`, `SecurityLevel`, `ZeroTrustMaturity`, `ImpactLevel`, `SafetyResult`, `JudgeResult`, `StandardReference`, `RollbackInfo` enums/models.

---

## Development Setup

### Prerequisites
- Python 3.11+ (Docker) veya 3.12+ (manual)
- Qdrant Cloud (proje cloud Qdrant kullanır — local Qdrant gerekmez)
- API keys: Novita (required — LLM + embeddings), Groq (optional fallback), Qdrant (required for RAG)

### Seçenek A: Docker (Önerilen)

```bash
git clone <repo>
cd ai-powered-os-hardening

# .env oluştur ve key'leri doldur
cp .env.example .env

# Build et ve başlat (ilk build ~10-20dk — torch büyük)
docker compose up --build

# Sonraki başlatmalar (cache'den)
docker compose up -d
```

Docker yapılandırması:
- **`Dockerfile`**: `python:3.11-slim` base, `libgomp1` + `libgl1` + `libglib2.0-0` sistem kütüphaneleri, `requirements-python311.txt`
- **`docker-compose.yml`**: `build.context + dockerfile` belirtilmiş, `logs/` volume mount, `env_file: .env`
- **`.dockerignore`**: `.git`, `__pycache__`, `.env`, `logs/`, `tests/`, `docs/`, `data/cache/` hariç tutulur

### Seçenek B: Manuel (venv)

```bash
git clone <repo>
cd ai-powered-os-hardening

# Virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
# veya: .\venv\Scripts\Activate.ps1   (Windows PowerShell)

# Dependencies
pip install -r requirements.txt

# .env oluştur ve key'leri doldur
cp .env.example .env

# PYTHONPATH (import hatası alırsanız)
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# API başlat
python main.py
# → http://localhost:8000
# → Swagger UI: http://localhost:8000/docs
```

### Build RAG Index (ilk kurulum veya PDF güncellemesi sonrası)

```bash
python scripts/build_index.py
```

---

## Environment Variables (`.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | Primary provider: `novita`, `groq`, `openai`, `ollama` | `novita` |
| `GROQ_API_KEY` | Groq API key (free tier) | optional |
| `GROQ_SMALL_MODEL_NAME` | Fast/cheap Groq model | `llama-3.1-8b-instant` |
| `GROQ_LARGE_MODEL_NAME` | Powerful Groq model | `llama-3.3-70b-versatile` |
| `NOVITA_API_KEY` | Novita API key (LLM + embeddings) | required |
| `OPENAI_API_KEY` | OpenAI key (fallback) | optional |
| `QDRANT_API_KEY` | Qdrant cloud key | required for RAG |
| `QDRANT_URL` | Qdrant cloud endpoint | required for RAG |
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
| `GET` | `/` | Root — API info |
| `GET` | `/health` | Service health status |
| `GET` | `/health/detailed` | Component-level health (vector_store, embedding, llm) |
| `GET` | `/metrics` | Aggregated performance stats |
| `GET` | `/metrics/errors` | Recent error log |
| `GET` | `/metrics/slow` | Slowest requests |
| `GET` | `/api/analytics` | Full analytics dashboard |
| `GET` | `/api/analytics/cost` | Cost breakdown by intent/complexity/model |
| `GET` | `/api/analytics/patterns` | Top N common query patterns |
| `GET` | `/api/analytics/rag` | RAG usage and effectiveness |
| `GET` | `/api/analytics/errors` | Error analysis and recent errors |
| `GET` | `/api/analytics/trends` | Performance trends over time window |
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
  "rag_min_score": 0.5,
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
- Provider selection is controlled by `LLM_PROVIDER` env var; defaults to `novita` (config.json)
- Never hardcode model names — read from `config/config.json` via `config_loader.py`

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
- Provider fallback chain (Novita → Groq → OpenAI → Ollama)
- Timeout handling
- Rate limiting behavior
- Windows 2025 hardening (PDF-only path)

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

Intent categories (defined as `IntentType` enum in `llm/core/context.py`):
- `smalltalk_greeting`, `smalltalk_farewell`, `smalltalk_other` → Pattern Responder (3A)
- `os_hardening`, `conceptual_explanation`, `incident_analysis`, `generic_qna` → Info Pipeline (3B)
- `script_or_config` → Action Pipeline (3C)
- Out-of-scope detection → Polite rejection

---

## RAG System

### Architecture
- **Embeddings**: Novita `qwen/qwen3-embedding-8b` (4096 dimensions) via `rag/embeddings/novita_embeddings.py`
- **Vector Store**: Qdrant cloud (`rag/vector_store/qdrant_store.py`)
- **Collection**: `cis_ubuntu_24_04_and_cis_windows_2025_benchmarks_with_ubuntu_rules_yaml`
- **Chunkers**: `cis_section` (PDF) and `yaml_rules` (YAML) — see `rag/chunking/`
- **Late chunking**: Available but **disabled by default** in config.json

### Indexed Sources (`config/config.json` → `rag.source_documents`)

| ID | Type | File | Chunker | Priority |
|----|------|------|---------|----------|
| `cis_ubuntu_24_04` | PDF | `data/source/CIS_Ubuntu_Linux_24.04_LTS_Benchmark_v1.0.0.pdf` | `cis_section` | 1 |
| `cis_windows_2025` | PDF | `data/source/CIS_Microsoft_Windows_Server_2025_Benchmark_v2.0.0.pdf` | `cis_section` | 2 |
| `ubuntu_rules_yaml` | YAML | `data/rules/ubuntu_24_04_rules.yaml` | `yaml_rules` | 3 |

- `YamlRulesChunker` (`rag/chunking/yaml_rules_chunker.py`) creates one chunk per CIS rule — includes full audit + remediation bash scripts, metadata (section, level, tags, config_files, auto_remediate)
- `CisSectionChunker` (`rag/chunking/cis_section_chunker.py`) chunks CIS PDFs by section number
- `data/rules/windows_2025_rules.yaml` exists but is **empty** — Windows hardening uses PDF only for now
- To rebuild the index: `python scripts/build_index.py`

### Smart RAG Triggering
RAG is only invoked for security-relevant queries — approximately 45% of queries skip RAG entirely (greetings, generic questions), reducing latency and cost.

### Config (`config/config.json`)
```json
{
  "embedding": { "provider": "novita", "model_name": "qwen/qwen3-embedding-8b", "dim": 4096 },
  "rag": { "retrieval": { "top_k": 5, "min_score": 0.5 }, "late_chunking": { "enabled": false } },
  "vector_store": { "provider": "qdrant", "qdrant": { "collection_name": "cis_ubuntu_24_04_and_cis_windows_2025_benchmarks_with_ubuntu_rules_yaml" } }
}
```

---

## Middleware Stack (Order in `main.py`)

Middleware is applied in **reverse order** (last added = first executed on requests):

1. `CORSMiddleware` — Allow cross-origin requests (origins: `*` in dev)
2. `TrustedHostMiddleware` — Host validation
3. `GZipMiddleware` — Response compression (>1KB)
4. `RateLimitMiddleware` — 100 req/min per IP, 5-min ban
5. `MetricsMiddleware` — Latency/error tracking
6. `RequestIDMiddleware` — Assign `X-Request-ID` (uses `X-Client-Request-ID` if provided)
7. `ResponseMetadataMiddleware` — Inject `X-Process-Time-Ms`, `X-API-Version` headers
8. `ProviderHeadersMiddleware` — Inject `X-LLM-Provider`, `X-LLM-Model`, `X-RAG-Used` headers
9. `RequestLogMiddleware` — Structured request logging to `api_requests` logger
10. `SecurityHeadersMiddleware` — CSP, HSTS, X-Frame-Options, etc.

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
