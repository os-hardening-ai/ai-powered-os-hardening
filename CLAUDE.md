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
- **Active LLM provider: Groq** (`llama-3.1-8b-instant` small, `llama-3.3-70b-versatile` large)
- **Embeddings provider: Novita** (`qwen/qwen3-embedding-8b`, 4096-dim) — RAG için ayrı provider
- Provider fallback chain: Groq → Novita → OpenAI → Ollama (configurable via `config/config.json`, `LLM_PROVIDER` env var)

**API base**: `http://localhost:8000` | **Swagger UI**: `/docs` | **Metrics**: `/metrics`

---

## Repository Layout

```
ai-powered-os-hardening/
├── main.py                    # FastAPI app factory + middleware registration
├── log_manager.py             # Custom logging setup (get_logger())
├── requirements.txt           # Production dependencies (Python 3.12+, minimum versions)
├── requirements-python311.txt # Docker dependencies (Python 3.11, pinned versions)
├── pytest.ini                 # Pytest configuration
├── SECURITY_AUDIT_REPORT.md   # Security audit findings
├── .env / .env.example        # Environment variables (API keys, model config)
├── config/
│   ├── config.json            # RAG, embedding, vector store, LLM, Redis settings
│   ├── config_loader.py       # Loads and validates config.json (primary config system)
│   └── schemas.py             # Pydantic schemas: AppConfigRoot, RedisConfig, etc.
├── api/                       # FastAPI routers and middleware
│   ├── router_chat.py         # POST /api/chat, POST /api/chat/stream (session_id destekli)
│   ├── router_artifacts.py    # GET /api/rules, POST /api/rules/plan|conflicts, POST /api/artifacts/generate
│   ├── router_openai.py       # POST /v1/chat/completions, GET /v1/models (OpenAI-compatible)
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
│   │   ├── context.py              # RequestContext (central pipeline state), SafetyCategory, IntentType
│   │   ├── config.py               # Legacy Config dataclass (reads .env directly)
│   │   ├── session_store.py        # In-memory session store (dev/single-instance)
│   │   └── redis_session_store.py  # Redis-backed session store (production, TTL support)
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
│   │   └── novita_llm_client.py   # Novita API (default provider)
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
│   │   └── integration.py        # RAGContextBuilder: retrieve_balanced, retrieve_multi, refinement loop
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
│   ├── cache/
│   │   └── embedding_cache.py    # Redis-backed embedding cache (SHA256 key, TTL configurable)
│   ├── chunking/
│   │   ├── base.py
│   │   ├── pdf_chunker.py
│   │   ├── semantic_pdf_chunker.py
│   │   ├── cis_section_chunker.py    # Chunks CIS PDFs by section number
│   │   └── yaml_rules_chunker.py     # One chunk per CIS rule (includes audit + remediation)
│   ├── embeddings/
│   │   ├── base.py
│   │   ├── embeddings.py
│   │   ├── novita_embeddings.py   # Primary: Novita qwen3-embedding-8b (4096-dim), cache-aware
│   │   └── cohere_embeddings.py
│   ├── query/
│   │   ├── query_planner.py    # QueryPlanner: subqueries + HyDE + stepback expansion
│   │   ├── query_rewriter.py   # QueryRewriter: follow-up → standalone (coreference resolution)
│   │   └── filter_agent.py     # FilterAgent: OS/role inference from free-text query
│   ├── retrieval/
│   │   ├── hybrid_retriever.py  # InContextHybridScorer: BM25 + dense RRF fusion
│   │   ├── reranker.py          # MMRReranker: diversity-aware reranking
│   │   └── rag_retriever.py
│   ├── verify/
│   │   └── claim_verifier.py    # ClaimVerifier: RAG-grounded fact checking
│   ├── vector_store/
│   │   ├── base.py
│   │   ├── vector_store.py
│   │   └── qdrant_store.py      # Qdrant cloud vector store (OS soft-filter support)
│   ├── indexing/
│   │   └── index_pipeline.py
│   └── metadata/
│       └── cis_benchmark_parser.py
├── domain/                   # Domain logic (Rule Engine + Artifact Generator)
│   ├── rule_engine/
│   │   └── rule_engine.py    # RuleEngine: conflict detection, topological ordering, execution plan
│   └── artifact_generator/
│       └── generator.py      # ArtifactGenerator: Bash / PowerShell / Ansible / REG / GPO
├── evaluation/               # Academic evaluation framework
│   ├── ragas_evaluator.py    # RAGASEvaluator: LLM-as-judge faithfulness/relevancy/precision/recall
│   └── ablation_study.py     # AblationStudy: baseline vs +hybrid/+mmr/+queryplan/full
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
│   ├── run_evaluation.py       # RAGAS + Ablation Study runner (--mode ragas|ablation|both)
│   └── start_api.py
├── src/
│   └── config_manager.py
├── logs/                       # Runtime application logs + evaluation results (JSON)
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

# Sonraki başlatmalar (override otomatik yüklenir, kod değişince rebuild gerekmez)
docker compose up -d

# Kod değişince (rebuild olmadan):
docker compose restart api

# Sadece production config (override olmadan):
docker compose -f docker-compose.yml up -d
```

Docker yapılandırması:
- **`Dockerfile`**: `python:3.11-slim` base, `libgomp1` + `libgl1` + `libglib2.0-0` sistem kütüphaneleri, `requirements-python311.txt`
- **`docker-compose.yml`**: production config — sadece `./logs:/app/logs` volume mount, `env_file: .env`
- **`docker-compose.override.yml`**: dev config — kaynak klasörler volume mount (`./llm`, `./api`, `./rag`, `./config` vs.), `ENABLE_DEBUG_LOGS=true`. `docker compose up -d` bunu **otomatik** yükler.
- **`.dockerignore`**: `.git`, `__pycache__`, `.env`, `logs/`, `tests/`, `docs/`, `data/cache/`, `docker-compose.override.yml` hariç tutulur

> **Önemli**: `docker restart api` container'ı yeniden başlatır ama `.env` değişikliklerini okumaz. `.env` değiştirdiysen `docker compose up -d` kullan (container'ı yeniden oluşturur).

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

| Variable | Description | Aktif Değer |
|----------|-------------|---------|
| `LLM_PROVIDER` | Primary provider: `groq`, `novita`, `openai`, `ollama` | **`groq`** |
| `GROQ_API_KEY` | Groq API key (free tier) | required |
| `GROQ_SMALL_MODEL_NAME` | Fast/cheap Groq model | `llama-3.1-8b-instant` |
| `GROQ_LARGE_MODEL_NAME` | Powerful Groq model | `llama-3.3-70b-versatile` |
| `NOVITA_API_KEY` | Novita API key (**embeddings için hâlâ gerekli**) | required |
| `OPENAI_API_KEY` | OpenAI key (fallback) | optional |
| `QDRANT_API_KEY` | Qdrant cloud key | required for RAG |
| `QDRANT_URL` | Qdrant cloud endpoint | required for RAG |
| `SMALL_MODEL_TEMPERATURE` | Temperature for small model | `0.3` |
| `LARGE_MODEL_TEMPERATURE` | Temperature for large model | `0.2` |
| `MAX_TOKENS` | Max response tokens (**Groq TPM limit nedeniyle 2048**) | **`2048`** |
| `REQUEST_TIMEOUT` | API timeout (seconds) | `60` |
| `MAX_RETRIES` | Retry attempts on failure | `2` |
| `ENABLE_DEBUG_LOGS` | Verbose pipeline logging | `false` |
| `ENABLE_JUDGE_STEP` | Output quality checking | `true` |
| `ENABLE_CORRECTION_STEP` | Auto-correct bad outputs | `true` |

> **Not**: `NOVITA_API_KEY` LLM için kullanılmıyor (provider=groq) ama embedding için `rag/embeddings/novita_embeddings.py` tarafından hâlâ kullanılıyor — silme.

---

## API Endpoints

### Chat
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Main chat: RAG + LLM + 4-layer SecurePipelineV2 (session_id destekli) |
| `POST` | `/api/chat/stream` | `/api/chat` ile **aynı** pipeline, SSE ile kelime-kelime akıtılır |
| `POST` | `/api/chat/fast` | **Hızlı RAG** (non-stream): intent routing YOK, doğrudan RAG-grounded |
| `POST` | `/api/chat/stream/fast` | **Hızlı RAG** (SSE, gerçek token-token): intent routing YOK |

> **Chat modları** — iki mod da RAG kullanır; fark RAG'de değil, *yönlendirmede*.
> **Tam (akıllı)** (`/api/chat[/stream]`) Layer 2/3'ü koşar: smalltalk→pattern responder
> ($0, RAG yok), info→RAG, kapsam-dışı→red. **Hızlı RAG** (`/api/chat/fast`,
> `/api/chat/stream/fast`) intent/routing/complexity/doğrulamayı atlar, her girdiyi doğrudan
> RAG-grounded üretir ("uzman/konsol"; smalltalk için uygun değildir). `/api/chat/stream` ⟂
> `/api/chat` davranış paritesi ortak `_run_pipeline()` helper'ı ile garanti edilir
> (`api/router_chat.py`). **Streaming kapalıyken Hızlı RAG yine çalışır** → `/api/chat/fast`.

### Domain — Rule Engine & Artifact Generator
| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/rules` | CIS kural listesi (level/category/auto_remediate filtresi, script blobs hariç) |
| `POST` | `/api/rules/plan` | Seçili kurallar için execution plan (topological sort + çakışma tespiti) |
| `POST` | `/api/rules/conflicts` | Kural çakışması tespiti (config_file / kernel_module overlap) |
| `POST` | `/api/artifacts/generate` | CIS kural ID'lerinden artifact üretimi (bash/powershell/ansible/reg/gpo) |

### OpenAI-Compatible
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/chat/completions` | **OpenAI-compatible** — herhangi bir OpenAI istemcisi ile kullanılabilir |
| `GET`  | `/v1/models` | Model listesi |

### RAG / Health / Monitoring
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/rag/search` | Direct RAG semantic search |
| `GET`  | `/health` | Service health status |
| `GET`  | `/health/detailed` | Component-level health (vector_store, embedding, llm) |
| `GET`  | `/metrics` | Aggregated performance stats |
| `GET`  | `/metrics/errors` | Recent error log |
| `GET`  | `/metrics/slow` | Slowest requests |
| `GET`  | `/api/analytics` | Full analytics dashboard |
| `GET`  | `/api/analytics/cost` | Cost breakdown by intent/complexity/model |
| `GET`  | `/api/analytics/patterns` | Top N common query patterns |
| `GET`  | `/api/analytics/rag` | RAG usage and effectiveness |
| `GET`  | `/api/analytics/errors` | Error analysis and recent errors |
| `GET`  | `/api/analytics/trends` | Performance trends over time window |
| `GET`  | `/docs` | Swagger UI |
| `GET`  | `/redoc` | ReDoc UI |

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
  "timeout": 60,
  "session_id": "user-abc-123"
}
```

`session_id` verilirse: geçmiş turlar Redis'ten yüklenir, follow-up sorular QueryRewriter ile standalone hale getirilir, cevap sonrası yeni turlar Redis'e kaydedilir (TTL: `session_ttl_seconds`, default 3600s).

### `/api/chat` Response Schema

```json
{
  "answer": "...",
  "intent": "action_request",
  "safety_category": "safe_defensive",
  "layer_path": "1->2->3C->4",
  "rag_sources": [{"id": "source_1", "score": 0.85, "source": "CIS Ubuntu 24.04", "section": "5.2.4"}],
  "stats": {
    "total_time_s": 4.2,
    "session_id": "user-abc-123",
    "history_turns": 2,
    "query_rewritten": false,
    "inferred_os": null
  },
  "request_id": "req_abc123",
  "estimated_cost": 0.0025,
  "verification_confidence": 0.87
}
```

### `/api/artifacts/generate` Request Schema

```json
{
  "rule_ids": ["1.1.1.1", "5.2.1", "5.2.2"],
  "format": "bash",
  "os_target": "ubuntu_24_04",
  "security_level": "balanced"
}
```

`format` seçenekleri: `bash` | `powershell` | `ansible` | `reg` | `gpo`

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
- **Collection**: `cis_ubuntu_2404_windows11_winserver2025_with_rules`
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
  "rag": {
    "retrieval": { "top_k": 3, "min_score": 0.5, "max_results": 6 },
    "late_chunking": { "enabled": false },
    "enhanced": {
      "enabled": true,
      "use_hybrid": true,
      "use_query_planning": true,
      "use_claim_verification": false,
      "use_filter_agent": true
    }
  },
  "vector_store": { "provider": "qdrant", "qdrant": { "collection_name": "cis_ubuntu_2404_windows11_winserver2025_with_rules" } },
  "llm": { "default_provider": "groq" }
}
```

> **`use_claim_verification: false`** — ClaimVerifier devre dışı. Aktif olduğunda RAG-tabanlı claim doğrulaması için 3-5 ekstra LLM call yapıyor ve ~38s ekliyor. Groq free tier'da TPM limitini tüketiyor. Ayrıca confidence skoru 0.00 dönüyor (kalibrasyon problemi). Tekrar açmadan önce `rag/verify/claim_verifier.py` düzeltilmeli.

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

| Component | Measured (Groq) |
|-----------|----------------|
| Pattern response (3A) | <20ms |
| Safety classification | ~250ms |
| QueryPlanner (3 parallel) | ~500ms |
| RAG retrieval (Qdrant) | ~4s |
| LLM generation (large model) | ~3-4s |
| Total — info_request with RAG | **~8s** |
| Simple info (no RAG) | ~1.5s |
| Script generation (action_request) | ~5-7s |
| ML intent detection | 5–10ms |

**Aktif pipeline_metrics.log formatı:**
```
intent=info_request path=1→2→3B layer1=0.248s layer2=0.002s layer3=8.018s
qplan=0.566s rag_ret=4.044s llm=3.405s verify=0.000s total=8.018s
rag=True chunks=7 cost=$0.0006
```

**Groq free tier limitleri:**

| Model | RPM | TPM | Darboğaz |
|-------|-----|-----|---------|
| `llama-3.1-8b-instant` | 30 | 6,000 | Safety(1) + QueryPlanner(3) + FilterAgent(0-1) = 4-5 call/req |
| `llama-3.3-70b-versatile` | 30 | 14,400 | Generation = 1 call/req |

6000 TPM / ~1000 token per call = max ~6 small-model call/dakika → eş zamanlı kullanımda rate limit riski var.

**Cost target**: $0.0006 average per query (Groq free tier).

---

## LLM Call Budget (per request)

Her request tipinin toplam LLM API çağrısı:

| Request Tipi | Layer 1 | QueryPlanner | FilterAgent | Generation | ClaimVerifier | **Toplam** |
|---|---|---|---|---|---|---|
| Smalltalk (3A) | 1 (small) | — | — | 0 | — | **1** |
| Info + RAG, simple (3B) | 1 (small) | **0** (atlanır) | 0-1 (small) | 1 (small) | 0 (kapalı) | **2-3** |
| Info + RAG, medium/complex (3B) | 1 (small) | 3 (small, parallel) | 0-1 (small) | 1 (large) | 0 (kapalı) | **5-6** |
| Action/Script (3C) | 1 (small) | — | — | 1 (large) | — | **2** |

**QueryPlanner detayı** (`rag/query/query_planner.py`):
- `_decompose`: 1 call → `max_subqueries=2` subquery üretir
- `_generate_hyde`: 1 call → hypothetical answer passage
- `_stepback`: 1 call → broader context query
- Hepsi `ThreadPoolExecutor(max_workers=3)` ile **parallel** — wall-clock ~500ms

**Rate limit aşıldığında**: `groq_client.py` `RuntimeError` fırlatır, `info_pipeline.py` catch edip Türkçe hata mesajı döner.

---

## Known Limitations / Production Blockers

The following are missing for production readiness (see `docs/10_ARCHITECTURE_ANALYSIS.md`):

- **Authentication** (P0 critical) — No API key or user auth implemented
- **Authorization** (P0 critical) — No RBAC
- **DDoS protection** (P1) — Rate limiting alone is insufficient
- **HTTPS/SSL** (P0) — Must configure before public deployment
- **Groq TPM limit** (P1) — Free tier: 6000 TPM/min for small model; 4-5 small-model calls per request → ~4 concurrent request/min max. Çözüm: paid plan veya QueryPlanner için farklı model.
- **ClaimVerifier kalibrasyonu** (P2) — `use_claim_verification: false` ayarlı. 0.00 confidence veriyor; düzeltilmeden açma.
- **Streaming tests** — Not yet covered by test suite
- **Windows YAML rules** — `windows_2025_rules.yaml` boş; Windows kuralları sadece PDF üzerinden gelir

Tamamlananlar (production blocker olmaktan çıktı):
- ~~Redis embedding cache~~ ✅ — `rag/cache/embedding_cache.py`, SHA256 key, TTL 24h
- ~~Session persistence~~ ✅ — `llm/core/redis_session_store.py`, TTL 1h, in-memory fallback
- ~~Provider latency~~ ✅ — Novita (~64s) → Groq (~8s)
- ~~Per-step timing~~ ✅ — `pipeline_metrics.log` her layer'ı ayrı ayrı ölçüyor

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
| Qdrant connection failed | Cloud Qdrant kullanıyoruz — `QDRANT_URL` ve `QDRANT_API_KEY` doğru mu? |
| Slow RAG queries | Groq ile ~8s normal; darboğaz `rag_ret` (~4s) Qdrant latency |
| ML model not found | Ensure `llm/ml/models/*.joblib` files are present |
| sklearn compatibility error | Re-train model with current sklearn version using `data/intent_training_dataset.csv` |
| Groq 500/rate limit error | `docker compose up -d` ile container yeniden başlat; 1 dakika bekle |
| `.env` değişikliği çalışmıyor | `docker compose up -d` kullan (restart değil) — restart .env'i yeniden okumaz |
| Kod değişikliği aktif değil | `docker compose restart api` — override.yml ile mount edildiği için rebuild gerekmez |
| Empty log files created | `log_manager.py`'de `FileHandler(delay=True)` var, ilk yazıya kadar dosya oluşmaz |
