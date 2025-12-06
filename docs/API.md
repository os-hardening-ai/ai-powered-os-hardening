# API Dokümantasyonu

## Base URL

```
http://localhost:8000
```

## Endpoints

### 1. Chat API

**POST /api/chat**

RAG + LLM entegre sohbet.

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "SSH hardening best practices?",
    "security_level": "balanced"
  }'
```

**Parameters**:
- `question` (required): Kullanıcı sorusu (max 5000 char)
- `security_level` (optional): "minimal", "balanced", "strict"
- `use_rag` (optional): RAG kullan (default: true)

**Response**:
```json
{
  "answer": "SSH hardening için...",
  "rag_sources": [...],
  "stats": {"total_time_ms": 2450}
}
```

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
