# API Dokumantasyonu

## Base URL

```
http://localhost:8000
```

## Architecture

4-Layer Security Pipeline:
- **Layer 1**: Safety Classification (threat detection)
- **Layer 2**: Intent Detection (smalltalk/info/action/out-of-scope)
- **Layer 3**: Routing (Pattern/Info/Action handlers)
- **Layer 4**: Generation (LLM + RAG)

## Endpoints

### 1. Chat API

**POST /api/chat**

RAG + LLM entegre sohbet (4-layer security pipeline).

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "SSH hardening best practices?",
    "os": "ubuntu_24_04",
    "role": "sysadmin",
    "security_level": "balanced",
    "zt_maturity": "medium"
  }'
```

**Parameters**:
- `question` (required): Kullanici sorusu (max 5000 char)
- `os` (optional): Operating system (ubuntu_22_04, ubuntu_24_04, centos_9, windows_server_2022, etc.)
- `role` (optional): User role (sysadmin, soc, developer, devops)
- `security_level` (optional): "minimal", "balanced", "strict" (default: "balanced")
- `zt_maturity` (optional): Zero Trust maturity level - "low", "medium", "high" (default: "medium")
- `use_rag` (optional): RAG kullan (default: true)
- `rag_top_k` (optional): RAG chunk sayisi (default: 5, max: 20)
- `rag_min_score` (optional): Minimum relevance score (default: 0.7)

**Response**:
```json
{
  "answer": "SSH hardening icin...",
  "intent": "info_request",
  "safety_category": "safe_defensive",
  "layer_path": "1->2->3B->4",
  "rag_sources": [
    {
      "id": "source_1",
      "score": 0.89,
      "source": "CIS_Ubuntu_24.04_Benchmark_v1.0.0",
      "section": "5.2.3 SSH Configuration"
    }
  ],
  "stats": {
    "total_time_s": 2.45,
    "layer_path": "1->2->3B->4"
  },
  "request_id": "req_abc123",
  "estimated_cost": 0.0015
}
```

**Layer Paths**:
- `1->2->UNSAFE`: Unsafe content rejected
- `1->2->3A`: Pattern response (smalltalk, greetings)
- `1->2->OUT_OF_SCOPE`: Non-security topic rejected
- `1->2->3B->4`: Info request (with/without RAG)
- `1->2->3C->4`: Action request (script generation)

### 2. RAG Search

**POST /rag/search**

Sadece doküman arama.

```bash
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "cramfs disable",
    "top_k": 5
  }'
```

### 3. Metrics

**GET /metrics**

Performance metrikleri.

```bash
curl http://localhost:8000/metrics
```

### 4. Health Check

**GET /health**

```bash
curl http://localhost:8000/health
```

## Swagger UI

Interactive API documentation: http://localhost:8000/docs

## Rate Limits

- 100 requests/minute per IP
- 5 minute ban for violations
