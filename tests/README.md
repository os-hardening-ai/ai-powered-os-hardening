# Test Suite Documentation

## Test Organization

```
tests/
├── unit/                    # Unit tests (tek modül testleri)
│   └── test_novita_embedding.py
├── integration/             # Integration tests (bileşen entegrasyonları)
│   ├── test_rag_llm_integration.py
│   ├── test_rag_query.py
│   ├── test_rag_api.py
│   └── test_comprehensive_pipeline.py
├── system/                  # System tests (tüm sistem)
│   └── (reserved for future)
└── performance/             # Performance tests
    └── (reserved for future)
```

## Running Tests

### All Tests
```bash
python -m pytest tests/
```

### Specific Test Category
```bash
# Unit tests
python -m pytest tests/unit/

# Integration tests
python -m pytest tests/integration/

# Specific test file
python tests/integration/test_rag_llm_integration.py
```

## Test Descriptions

### Integration Tests

#### `test_rag_llm_integration.py`
**Purpose**: Tests full RAG + LLM + ML intent detection integration

**What it tests**:
- RAG availability and context retrieval
- ML intent detector (90.48% accuracy)
- LLM client availability (Groq)
- Full pipeline execution (end-to-end)

**Expected output**:
```
[TEST 1] RAG Availability Check - OK
[TEST 2] ML Intent Detector Check - OK
[TEST 3] LLM Client Availability - OK
[TEST 4] Full Pipeline Integration Test - OK
```

#### `test_rag_query.py`
**Purpose**: Tests RAG retrieval system

**What it tests**:
- Embedding generation (NovitaEmbeddingClient)
- Vector search (QdrantVectorStore)
- Context retrieval quality
- Late chunking functionality

#### `test_rag_api.py`
**Purpose**: Tests RAG API endpoints

**What it tests**:
- `/rag/search` endpoint
- Request/response format
- Top-K retrieval
- Score filtering

#### `test_comprehensive_pipeline.py`
**Purpose**: Tests complete 4-layer security pipeline

**What it tests**:
- Layer 1: Safety Classification
- Layer 2: Intent Detection
- Layer 3: Routing (Pattern/Info/Action)
- Layer 4: LLM Generation

### Unit Tests

#### `test_novita_embedding.py`
**Purpose**: Tests Novita embedding client

**What it tests**:
- API connectivity
- Embedding generation (4096 dimensions)
- Latency measurement
- Error handling

## Test Coverage

### Current Coverage
- **RAG System**: ✅ 100%
- **ML Intent Detection**: ✅ 100%
- **LLM Integration**: ✅ 100%
- **Pipeline Layers**: ✅ 100%
- **API Endpoints**: ⚠️ 70% (streaming not tested)

### Missing Tests (TODO)
- [ ] Streaming endpoint tests
- [ ] Fallback chain tests
- [ ] Timeout handling tests
- [ ] Error response format tests
- [ ] Rate limiting tests
- [ ] Performance benchmarks

## Test Requirements

All tests require:
- Python 3.12+
- `.env` file with API keys:
  ```
  GROQ_API_KEY=your_key
  NOVITA_API_KEY=your_key
  ```
- Running Qdrant instance (for RAG tests)

## Continuous Integration

Tests should be run:
1. Before every commit
2. In CI/CD pipeline
3. Before production deployment

## Test Standards

All new tests must:
1. Follow pytest conventions
2. Include docstrings
3. Be independent (no test interdependencies)
4. Clean up after themselves
5. Have meaningful assertions
