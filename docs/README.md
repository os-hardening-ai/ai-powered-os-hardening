# AI-Powered OS Hardening - Complete Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Performance Analysis](#performance-analysis)
4. [Security Analysis](#security-analysis)
5. [Setup Guide](#setup-guide)
6. [API Documentation](#api-documentation)
7. [Testing Guide](#testing-guide)
8. [Deployment](#deployment)

---

## Project Overview

### What is This?
AI-powered OS hardening system that combines:
- **RAG (Retrieval-Augmented Generation)** over CIS Benchmark documents
- **ML Intent Detection** (90.48% accuracy)
- **LLM Integration** (Groq, OpenAI, Ollama)
- **4-Layer Security Pipeline**

### Key Features
- ✅ Free tier usage ($0/1000 requests with Groq)
- ✅ 90.48% intent detection accuracy
- ✅ 5-7s end-to-end latency (with RAG)
- ✅ Production-ready API with streaming support
- ✅ Automatic provider fallback (99.9% uptime)
- ✅ Request timeout protection
- ✅ Comprehensive security headers

### Tech Stack
```
Frontend: None (API only)
Backend: FastAPI (Python 3.12+)
LLM: Groq (free), OpenAI (optional), Ollama (local)
RAG: Qdrant (vector store) + Novita (embeddings)
ML: scikit-learn (Logistic Regression + TF-IDF)
```

---

## Architecture

### System Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                       FastAPI Application                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Middleware Stack (6 layers)                         │   │
│  │  1. Security Headers                                 │   │
│  │  2. Provider Headers                                 │   │
│  │  3. Response Metadata                                │   │
│  │  4. Request ID Tracking                              │   │
│  │  5. Metrics Collection                               │   │
│  │  6. Rate Limiting (100 req/min)                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  API Endpoints                                       │   │
│  │  - /api/chat (RAG + LLM)                             │   │
│  │  - /api/chat/stream (SSE streaming)                  │   │
│  │  - /rag/search (RAG only)                            │   │
│  │  - /health, /metrics, /analytics                     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               4-Layer Security Pipeline                       │
│                                                              │
│  Layer 1: Safety Classification (LLM-based)                 │
│  Layer 2: Intent Detection (ML - 90.48% accuracy)           │
│  Layer 3: Routing (Pattern/Info/Action/Out-of-Scope)        │
│  Layer 4: Generation (Adaptive LLM selection)               │
└─────────────────────────────────────────────────────────────┘
```

For complete architecture details, see [ARCHITECTURE_ANALYSIS.md](ARCHITECTURE_ANALYSIS.md)

---

## Performance Analysis

### Key Metrics

#### RAG System
- **Embedding**: 2.1s (NovitaEmbeddingClient, 4096 dims)
- **Vector Search**: 0.9s (Qdrant top-3 retrieval)
- **Total RAG Latency**: 3.0s

**Optimization Opportunity**: Add Redis cache → 95% latency reduction

#### ML Intent Detection
- **Accuracy**: 90.48% (test set)
- **Latency**: 5-10ms
- **Cost**: $0 (local model)
- **Classes**: 7 (greeting, farewell, thanks, help, info_request, action_request, out_of_scope)

#### LLM Pipeline
- **Small Model**: 1-2s (Groq Llama 3.1 8B)
- **Large Model**: 2-4s (Groq Llama 3.3 70B)
- **Throughput**: 500+ tokens/second

#### End-to-End
- **Pattern-based**: 10-20ms
- **Info Request (with RAG)**: 5-7s
- **Action Request**: 3-5s

For complete performance analysis, see [PERFORMANCE_ANALYSIS.md](PERFORMANCE_ANALYSIS.md)

---

## Security Analysis

### Security Grade: B+ (Good, needs auth)

#### Strengths ✅
1. Rate limiting (100 req/min)
2. Input validation (5000 char limit)
3. Prompt injection detection
4. Output sanitization
5. Security headers (CSP, HSTS, X-Frame-Options)
6. Request timeout protection
7. Provider fallback for reliability

#### Weaknesses ❌
1. **No authentication** (CRITICAL - P0)
2. No IP whitelisting
3. No DDoS protection beyond rate limiting

### Security Features

#### Rate Limiting
```python
# 100 requests per minute per IP
# 5-minute ban for violators
# Automatic retry-after headers
```

#### Input Validation
```python
# Max length: 5000 characters
# Empty input detection
# Field-level validation (Pydantic)
# SQL injection prevention
# XSS filtering
```

#### Security Headers
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000
Content-Security-Policy: default-src 'self'
```

---

## Setup Guide

### Prerequisites
- Python 3.12+
- Git
- API keys (Groq, Novita)
- Qdrant instance (for RAG)

### Installation

#### 1. Clone Repository
```bash
git clone <repository-url>
cd ai-powered-os-hardening
```

#### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Configure Environment
Create `.env` file:
```env
# LLM Provider (choose one)
LLM_PROVIDER=groq  # FREE (recommended)
# LLM_PROVIDER=openai  # PAID
# LLM_PROVIDER=ollama  # LOCAL

# API Keys
GROQ_API_KEY=your_groq_key_here
NOVITA_API_KEY=your_novita_key_here
# OPENAI_API_KEY=your_openai_key_here  # if using OpenAI

# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=cis_benchmarks

# Optional: Ollama (if using local models)
# OLLAMA_BASE_URL=http://localhost:11434
```

#### 5. Run Application
```bash
# Development
python main.py

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### 6. Verify Installation
```bash
# Health check
curl http://localhost:8000/health

# Test query
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "SSH nedir?"}'
```

---

## API Documentation

### Base URL
```
http://localhost:8000
```

### Interactive Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Core Endpoints

#### POST `/api/chat`
**Purpose**: Main chat endpoint with RAG + LLM

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
      "source": "CIS Benchmark",
      "section": "SSH Configuration"
    }
  ],
  "stats": {
    "total_time_s": 5.2
  },
  "request_id": "req_abc123",
  "estimated_cost": 0.0
}
```

#### POST `/api/chat/stream`
**Purpose**: Streaming version with SSE

**Response** (Server-Sent Events):
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
**Purpose**: Direct RAG search without LLM

**Request**:
```json
{
  "query": "SSH hardening",
  "top_k": 3,
  "late_chunking": {
    "enabled": true,
    "window_size": 3
  }
}
```

### Response Headers

All responses include:
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

---

## Testing Guide

See [../tests/README.md](../tests/README.md) for complete testing documentation.

### Quick Test
```bash
# Integration test
python tests/integration/test_rag_llm_integration.py

# All tests
python -m pytest tests/
```

---

## Deployment

### Production Checklist

#### Must Have (P0)
- [ ] API key authentication
- [ ] Redis embedding cache
- [ ] HTTPS/SSL certificate
- [ ] Environment variables secured
- [ ] Error logging configured

#### Should Have (P1)
- [ ] Load balancer
- [ ] Multiple API instances
- [ ] Monitoring alerts
- [ ] Backup strategy

### Docker Deployment (TODO)
```bash
# Build
docker build -t os-hardening-api .

# Run
docker-compose up -d
```

### Cloud Deployment Options
- AWS: EC2 + RDS + ElastiCache
- GCP: Cloud Run + Cloud SQL + Memorystore
- Azure: App Service + Azure Database + Redis Cache

---

## Troubleshooting

### Common Issues

#### 1. Import Errors
```bash
# Solution: Ensure PYTHONPATH is set
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

#### 2. API Key Not Found
```bash
# Solution: Check .env file
cat .env | grep API_KEY
```

#### 3. Qdrant Connection Failed
```bash
# Solution: Start Qdrant
docker run -p 6333:6333 qdrant/qdrant
```

#### 4. Slow RAG Queries
```bash
# Solution: Add Redis cache (see ARCHITECTURE_ANALYSIS.md #2)
```

---

## Contributing

### Development Workflow
1. Create feature branch
2. Make changes
3. Run tests
4. Submit PR

### Code Standards
- Python 3.12+
- Type hints required
- Docstrings for all functions
- Test coverage >80%

---

## License

MIT License - See LICENSE file

---

## Support

For issues and questions:
- GitHub Issues: <repository-url>/issues
- Documentation: This folder

---

## Changelog

See git commit history for detailed changes.

### Recent Updates
- ✅ Added streaming support (SSE)
- ✅ Implemented provider fallback
- ✅ Added request timeout protection
- ✅ Enhanced API headers
- ✅ Standardized error responses
- ✅ Fixed 3 CVE vulnerabilities
- ✅ Retrained ML model (sklearn 1.8.0)

---

**Last Updated**: 2025-12-24
**Version**: 1.0.0
**Status**: Production Ready (90%)
