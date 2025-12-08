# Kullanılan Teknolojiler

## Teknoloji Stack'i Özeti

Bu projede **modern AI/ML teknolojileri** kullanarak production-ready bir güvenlik asistanı geliştirilmiştir.

```
┌─────────────────────────────────────────────────────────────┐
│                    TECHNOLOGY STACK                          │
├─────────────────────────────────────────────────────────────┤
│  Backend Framework: FastAPI + Uvicorn                       │
│  Machine Learning: scikit-learn + TF-IDF                    │
│  LLM: Groq (Llama 3.3 70B, Llama 3.1 8B)                   │
│  RAG: Cohere Embeddings + Qdrant/FAISS                     │
│  Orchestration: LangChain                                   │
│  Testing: pytest + custom evaluators                        │
│  Security: Rate limiting, input validation, HSTS            │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Backend Framework

### FastAPI
**Versiyon**: 0.109+
**Neden Seçtik?**
- Modern, hızlı (Starlette tabanlı)
- Otomatik API dokümantasyonu (Swagger/ReDoc)
- Pydantic ile güçlü tip kontrolü
- Async/await desteği
- Python 3.12+ type hints desteği

**Kullanım Alanları:**
- REST API endpoints ([router_chat.py](../api/router_chat.py:1-100), [router_rag.py](../api/router_rag.py:1-50))
- Request/Response validation
- Middleware (CORS, security headers, rate limiting)
- Health check ve metrics endpoints

**Örnek Kod:**
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="AI-Powered OS Hardening")

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000)
    os: Optional[str] = None

@app.post("/api/chat")
async def chat(request: ChatRequest):
    # Pipeline processing
    return {"answer": "..."}
```

### Uvicorn
**Versiyon**: 0.27+
**Neden Seçtik?**
- Hızlı ASGI server
- Async support
- Production-ready

**Kullanım:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Pydantic
**Versiyon**: 2.6+
**Neden Seçtik?**
- Güçlü veri validasyonu
- Type safety
- JSON schema generation (Swagger için)

**Kullanım Alanları:**
- Request body validation
- Response models
- Configuration management
- Data classes ([models.py](../llm/models.py:1-100))

---

## 2. Machine Learning

### scikit-learn
**Versiyon**: 1.4+
**Neden Seçtik?**
- Industry-standard ML library
- Hızlı training ve inference
- Model persistence (joblib)
- Mature ve stable

**Kullandığımız Modüller:**

#### TfidfVectorizer
**Amaç**: Metin vektörizasyonu (text → numerical features)

**Parametreler:**
```python
TfidfVectorizer(
    max_features=5000,      # Max vocabulary size
    ngram_range=(1, 3),     # Unigram, bigram, trigram
    min_df=2,               # Min document frequency
    max_df=0.8,             # Max document frequency (remove too common)
    sublinear_tf=True       # Log scaling
)
```

**Çıktı**: 544 özellik (1,230 örnek dataset'ten)

#### LogisticRegression
**Amaç**: Intent classification (ana model)

**Parametreler:**
```python
LogisticRegression(
    max_iter=1000,
    C=1.0,                  # Regularization strength
    solver='lbfgs',         # Optimization algorithm
    multi_class='multinomial',  # 7 class
    random_state=42
)
```

**Performans**:
- Training accuracy: 91.16%
- Test accuracy: 82.52%
- CV accuracy: 85.37% ± 2.72%

#### LinearSVC (Secondary Model)
**Amaç**: Alternative classifier (currently not used in hybrid, but available)

**Kullanım:**
```python
from sklearn.svm import LinearSVC

svm_model = LinearSVC(C=1.0, max_iter=1000)
svm_model.fit(X_train, y_train)
```

### joblib
**Versiyon**: 1.3+
**Neden Seçtik?**
- Efficient model serialization
- Sklearn'le entegrasyon
- Hızlı load/save

**Kullanım:**
```python
import joblib

# Save
joblib.dump(model, 'models/intent_model.joblib')
joblib.dump(vectorizer, 'models/intent_vectorizer.joblib')

# Load
model = joblib.load('models/intent_model.joblib')
vectorizer = joblib.load('models/intent_vectorizer.joblib')
```

**Model Boyutları:**
- intent_model.joblib: ~50KB
- intent_vectorizer.joblib: ~20KB

---

## 3. LLM (Large Language Models)

### Groq
**Neden Seçtik?**
- **ÜCRETSİZ** (no credit card required)
- **Çok hızlı** (500+ tokens/second)
- Llama 3.3 70B ve Llama 3.1 8B desteği
- API rate limits: 30 requests/minute (free tier)

**Kullandığımız Modeller:**

#### llama-3.3-70b-versatile
**Use Case**: Info ve Action pipelines (Layer 3B, 3C)
**Özellikler**:
- 70 billion parameters
- Context window: 128K tokens
- Çok yüksek kalite yanıtlar
- Hız: ~500 token/s

**Örnek Kullanım:**
```python
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": "Sen bir siber güvenlik uzmanısın."},
        {"role": "user", "content": "SSH nedir?"}
    ],
    temperature=0.1,
    max_tokens=2000
)

answer = response.choices[0].message.content
```

#### llama-3.1-8b-instant
**Use Case**: Safety classification (Layer 1)
**Özellikler**:
- 8 billion parameters
- Ultra fast (~800 token/s)
- Safety classification için yeterli
- Daha düşük maliyet

**Neden 8B Model?**
Safety classification basit bir task → 8B model yeterli → Daha hızlı yanıt

### OpenAI (Optional)
**Neden Kullanmadık (primary olarak)?**
- Ücretli (GPT-4: $0.03/1K tokens)
- Groq ücretsiz ve yeterince iyi

**Ancak Destekliyoruz:**
`.env` dosyasında:
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

### Ollama (Optional)
**Use Case**: Tamamen yerel çalıştırma
**Neden Kullanmadık (primary olarak)?**
- Yavaş (CPU inference)
- GPU gereksinimi (ideal performans için)

**Ancak Destekliyoruz:**
```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 4. RAG (Retrieval-Augmented Generation)

### Cohere Embeddings
**Model**: embed-multilingual-v3.0
**Neden Seçtik?**
- Çok dilli destek (Türkçe + İngilizce)
- 1024 dimensions
- Free tier: 100 requests/month

**Kullanım:**
```python
import cohere

co = cohere.Client(api_key=os.getenv("COHERE_API_KEY"))

embeddings = co.embed(
    texts=["SSH hardening best practices"],
    model="embed-multilingual-v3.0",
    input_type="search_query"
).embeddings
# embeddings: [1024-dim vector]
```

### Qdrant
**Versiyon**: 1.7+
**Neden Seçtik?**
- Open-source vector database
- Hızlı semantic search
- Docker ile kolay kurulum
- REST API desteği

**Kullanım:**
```python
from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")

# Search
results = client.search(
    collection_name="cis_benchmarks",
    query_vector=embedding,  # 1024-dim
    limit=5,
    score_threshold=0.7
)
```

**Collection Structure:**
```python
{
    "id": "chunk_ubuntu_22_04_ssh_001",
    "vector": [0.123, -0.456, ...],  # 1024-dim
    "payload": {
        "source": "CIS_Ubuntu_22.04_Benchmark_v2.0.0",
        "section": "5.2.3 Ensure SSH access is limited",
        "content": "SSH configuration best practices...",
        "os": "ubuntu_22_04"
    }
}
```

### FAISS (Alternative)
**Neden FAISS?**
- Facebook AI Similarity Search
- Tamamen yerel (Docker gerektirmez)
- Hızlı (C++ implementation)

**Kullanım:**
```python
import faiss
import numpy as np

# Index oluştur
dimension = 1024
index = faiss.IndexFlatL2(dimension)
index.add(vectors)  # numpy array

# Search
D, I = index.search(query_vector, k=5)
```

**Trade-off: Qdrant vs FAISS**
| Özellik | Qdrant | FAISS |
|---------|--------|-------|
| Setup | Docker gerekli | Pip install yeter |
| Metadata | JSON payload | Ayrı dict gerekli |
| Filtering | Built-in | Manuel |
| Scalability | Daha iyi | Sınırlı |

---

## 5. LLM Orchestration

### LangChain
**Versiyon**: 0.1+
**Neden Seçtik?**
- LLM workflow orchestration
- Prompt management
- Chain of Thought (CoT) desteği
- Multi-LLM support

**Kullandığımız Modüller:**

#### PromptTemplate
```python
from langchain.prompts import PromptTemplate

prompt = PromptTemplate(
    input_variables=["context", "question"],
    template="""Sen bir siber güvenlik uzmanısın.

Context (CIS Benchmark):
{context}

User Question:
{question}

Answer (Türkçe, detaylı):"""
)

formatted = prompt.format(context=rag_context, question=user_q)
```

#### ChatGroq
```python
from langchain_groq import ChatGroq

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.1,
    api_key=os.getenv("GROQ_API_KEY")
)

response = llm.invoke(messages)
```

---

## 6. Testing ve Quality

### pytest
**Versiyon**: 7.4+
**Neden Seçtik?**
- Industry standard
- Fixtures desteği
- Parametrized testing
- Coverage reporting

**Kullanım:**
```python
import pytest

@pytest.fixture
def pipeline():
    return create_pipeline_v2(use_ml=True, debug=False)

def test_greeting_intent(pipeline):
    ctx = RequestContext(user_question="Merhaba")
    result = pipeline.process(ctx)
    assert result.intent.type == "smalltalk"
    assert result.intent.subtype == "greeting"
```

**Test Türleri:**
- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- Pipeline evaluation: `tests/pipeline_evaluator.py` (50 test cases)

### Custom Evaluator
**Dosya**: [tests/pipeline_evaluator.py](../tests/pipeline_evaluator.py:1-200)

**Özellikler:**
- 50 test case ile değerlendirme
- Expected intent check
- Layer path validation
- Performance metrics (time, cost)

**Örnek Test Case:**
```python
{
    "question": "Ubuntu 22.04 için SSH hardening scripti oluştur",
    "expected_intent": "action_request",
    "expected_path": "1->2->3C->4",
    "context": {
        "os": "ubuntu_22_04",
        "role": "admin"
    }
}
```

---

## 7. Security

### slowapi
**Versiyon**: 0.1.9+
**Amaç**: Rate limiting

**Kullanım:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/chat")
@limiter.limit("100/minute")
async def chat(request: Request, ...):
    ...
```

### Security Headers Middleware
**Dosya**: [api/middleware.py](../api/middleware.py:1-50)

**Eklediğimiz Header'lar:**
```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

### Input Validation
**Teknoloji**: Pydantic

**Örnek:**
```python
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000)
    os: Optional[str] = Field(None, pattern="^(ubuntu_22_04|ubuntu_24_04|centos_9)$")
    security_level: str = Field("balanced", pattern="^(minimal|balanced|strict)$")
```

**Validation Errors:**
- Otomatik 422 response
- Detaylı error messages
- Field-level validation

---

## 8. Data Processing

### pandas
**Versiyon**: 2.1+
**Kullanım Alanı**: Dataset processing

```python
import pandas as pd

# Load intent dataset
df = pd.read_data("data/intent_training_dataset.csv")
print(f"Dataset: {len(df)} samples")
print(df["intent"].value_counts())
```

### numpy
**Versiyon**: 1.24+
**Kullanım Alanı**: Numerical operations

```python
import numpy as np

# TF-IDF vectors
X_train = vectorizer.fit_transform(texts)  # Sparse matrix
X_dense = X_train.toarray()  # Dense numpy array
```

---

## 9. Environment ve Configuration

### python-dotenv
**Versiyon**: 1.0+
**Amaç**: `.env` file loading

```python
from dotenv import load_dotenv
import os

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
```

### Config Management
**Dosya**: [llm/models.py](../llm/models.py:50-100)

```python
class Config:
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY")
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "cohere")
    VECTOR_STORE: str = os.getenv("VECTOR_STORE_PROVIDER", "qdrant")
```

---

## 10. Deployment ve Production

### Docker (Optional)
**Use Case**: Qdrant vector database

```dockerfile
# docker-compose.yml
version: '3'
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - ./qdrant_storage:/qdrant/storage
```

### Gunicorn (Production)
**Alternative to Uvicorn** (multi-worker)

```bash
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

---

## Teknoloji Seçim Kriterleri

### Neden Bu Teknolojiler?

| Kriter | Seçim | Alternatif | Neden Tercih? |
|--------|-------|------------|---------------|
| **Backend** | FastAPI | Flask, Django | Modern, async, auto docs |
| **LLM** | Groq | OpenAI | ÜCRETSİZ, hızlı |
| **ML** | scikit-learn | PyTorch, TF | Basit task, hızlı |
| **Embeddings** | Cohere | OpenAI | Çok dilli, ücretsiz trial |
| **Vector DB** | Qdrant | Pinecone, Weaviate | Open-source, Docker |
| **Orchestration** | LangChain | Custom | Prompt management |
| **Testing** | pytest | unittest | Fixtures, parametrize |

---

## Dependency Management

### requirements.txt
```txt
# Backend
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.6.0

# ML
scikit-learn==1.4.0
numpy==1.24.0
pandas==2.1.0
joblib==1.3.0

# LLM
groq==0.4.0
langchain==0.1.0
langchain-groq==0.0.1

# RAG
cohere==4.37
qdrant-client==1.7.0
# faiss-cpu==1.7.4  # Alternative

# Security
slowapi==0.1.9

# Utils
python-dotenv==1.0.0
```

### Installation
```bash
pip install -r requirements.txt
```

---

## Performans Özeti

| Teknoloji | Latency | Cost | Avantaj |
|-----------|---------|------|---------|
| FastAPI | <1ms | $0 | Hızlı, modern |
| ML Intent Detection | <10ms | $0 | Çok hızlı, ücretsiz |
| Groq Llama 8B | ~200ms | $0 | Ücretsiz, hızlı |
| Groq Llama 70B | ~500ms | $0 | Ücretsiz, kaliteli |
| Cohere Embeddings | ~100ms | $0* | Çok dilli (*free tier) |
| Qdrant Search | ~50ms | $0 | Open-source, hızlı |

**Toplam Pipeline (Action Request)**: ~3s, ~$0

---

## Gelecek İyileştirmeler

1. **Caching**: Redis ile yanıt cache'leme
2. **Async RAG**: Parallel embedding generation
3. **Model Fine-tuning**: Domain-specific Llama model
4. **GraphQL**: Alternative to REST
5. **WebSocket**: Real-time chat
6. **Monitoring**: Prometheus + Grafana

---

## Sonraki Adımlar

- 📖 [LLM Uygulamaları](06_LLM_UYGULAMALARI.md) - ML ve LLM detayları
- 📖 [Kurulum](03_KURULUM_VE_KULLANIM.md) - Nasıl kurulur?
