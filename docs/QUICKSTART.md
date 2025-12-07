# 🚀 Hızlı Başlangıç Rehberi

## Sistem Gereksinimleri

- Python 3.10+
- Docker (Qdrant için)
- API Keys:
  - OpenAI API Key (veya Groq API Key)
  - Cohere API Key (embedding için)

## 1. Kurulum

### 1.1. Repository'yi Clone'la

```bash
git clone <repo-url>
cd ai-powered-os-hardening
```

### 1.2. Sanal Ortam Oluştur ve Bağımlılıkları Yükle

```bash
# Python virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# veya
venv\Scripts\activate  # Windows

# Ana bağımlılıklar
pip install -r requirements.txt

# LLM bağımlılıkları
cd llm
pip install -r requirements.txt
cd ..
```

### 1.3. Environment Variables Ayarla

`.env` dosyası oluştur (root directory):

```bash
# Cohere (Embedding ve Rerank için)
COHERE_API_KEY=your-cohere-api-key

# OpenAI (LLM için - opsiyonel)
OPENAI_API_KEY=your-openai-api-key

# Groq (Alternatif LLM - opsiyonel)
GROQ_API_KEY=your-groq-api-key

# Qdrant (Vector Store)
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=cis_benchmark
```

LLM için de `.env` dosyası oluştur (`llm/.env`):

```bash
# LLM Provider (openai, groq, huggingface)
LLM_PROVIDER=openai

# API Keys
OPENAI_API_KEY=your-openai-api-key
GROQ_API_KEY=your-groq-api-key

# Model seçimi
SMALL_MODEL=gpt-3.5-turbo  # veya llama3-8b-8192 (Groq)
LARGE_MODEL=gpt-4o-mini    # veya mixtral-8x7b-32768 (Groq)

# Debug
ENABLE_DEBUG_LOGS=true
```

## 2. Qdrant Vector Store'u Başlat

```bash
docker run -d -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/qdrant_storage:/qdrant/storage \
    qdrant/qdrant
```

Kontrol et:
```bash
curl http://localhost:6333/collections
```

## 3. Dokümanları İndeksle (İlk Kurulum)

CIS benchmark dokümanlarını vector store'a yükle:

```bash
# Data klasörüne dokümanları koy
ls data/
# cis_ubuntu_22_04.pdf
# cis_windows_server_2022.pdf
# ...

# İndeksleme script'ini çalıştır
python scripts/index_documents.py
```

## 4. API Sunucusunu Başlat

```bash
python main.py
```

API şu adreste çalışacak: `http://localhost:8000`

Swagger UI: `http://localhost:8000/docs`

## 5. API Endpoint'lerini Test Et

### 5.1. Health Check

```bash
curl http://localhost:8000/health
```

Beklenen çıktı:
```json
{
  "status": "healthy"
}
```

### 5.2. RAG-Only Endpoint (Sadece Retrieval)

```bash
curl -X POST "http://localhost:8000/rag/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SSH hardening",
    "top_k": 3
  }'
```

Beklenen çıktı:
```json
{
  "query": "SSH hardening",
  "top_k": 3,
  "results": [
    {
      "id": "chunk_123",
      "score": 0.92,
      "text": "SSH PermitRootLogin should be disabled...",
      "metadata": {
        "source": "CIS Ubuntu 22.04",
        "section": "5.2.5"
      }
    },
    ...
  ]
}
```

### 5.3. RAG + LLM Endpoint (Birleşik - YENİ!)

```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "SSH hardening için en önemli 3 adım nedir?",
    "os": "ubuntu_22_04",
    "security_level": "strict",
    "use_rag": true
  }'
```

Beklenen çıktı:
```json
{
  "answer": "SSH hardening için CIS benchmark'a göre en önemli 3 adım:\n\n1. **PermitRootLogin Devre Dışı**\n   - /etc/ssh/sshd_config dosyasında PermitRootLogin no\n   - Root kullanıcısının SSH ile giriş yapmasını engeller\n\n2. **Key-Based Authentication**\n   - Password authentication devre dışı\n   - Sadece SSH key ile giriş izni\n\n3. **Port ve Protocol Güvenliği**\n   - SSH Protocol 2 kullanımı zorunlu\n   - Default port (22) yerine custom port kullanımı önerilir\n\n[Kaynaklar: CIS Ubuntu 22.04 Benchmark, Sections 5.2.5, 5.2.8]",
  "intent": "os_hardening",
  "safety_category": "defensive_security",
  "rag_sources": [
    {
      "id": "source_1",
      "score": 0.92,
      "source": "CIS Ubuntu 22.04 Benchmark",
      "section": "5.2.5 - SSH PermitRootLogin"
    },
    {
      "id": "source_2",
      "score": 0.87,
      "source": "CIS Ubuntu 22.04 Benchmark",
      "section": "5.2.8 - SSH Key-Based Auth"
    }
  ],
  "stats": {
    "total_calls": 1,
    "complex_path_count": 1,
    "rag_retrieval_count": 1,
    "total_cost_estimate": 0.015
  }
}
```

## 6. Python ile Test

```python
import requests

# RAG + LLM sorgusu
response = requests.post(
    "http://localhost:8000/api/chat",
    json={
        "question": "Firewall konfigürasyonu nasıl yapılır?",
        "os": "ubuntu_22_04",
        "role": "sysadmin",
        "security_level": "balanced",
        "use_rag": True,
        "rag_top_k": 5,
        "rag_min_score": 0.7
    }
)

data = response.json()
print("Cevap:", data["answer"])
print("\nKaynaklar:")
for source in data["rag_sources"]:
    print(f"  - {source['source']} ({source['score']:.2f})")
    print(f"    {source['section']}")
```

## 7. CLI Chatbot (Terminal)

LLM klasöründeki chatbot'u çalıştır:

```bash
cd llm
python run_chat.py
```

Örnek kullanım:
```
Sen: SSH hardening için öneriler ver
Asistan: [RAG'den bilgi getirir ve detaylı cevap verir]

Sen: /context os=ubuntu_22_04 role=soc level=strict
Baglam guncellendi!

Sen: /history
[Son konuşmaları gösterir]

Sen: /quit
```

## 8. Test Script'ini Çalıştır

Otomatik test suite:

```bash
python test_rag_llm_integration.py
```

Özel soru sor:
```bash
python test_rag_llm_integration.py "Ubuntu güvenlik önerileri nedir?"
```

## API Parametreleri

### `/api/chat` Endpoint Parametreleri

| Parametre | Tip | Varsayılan | Açıklama |
|-----------|-----|------------|----------|
| `question` | string | **zorunlu** | Kullanıcı sorusu |
| `os` | string | null | OS türü (ubuntu_22_04, windows_11, etc.) |
| `role` | string | null | Kullanıcı rolü (sysadmin, soc, developer) |
| `security_level` | string | "balanced" | Güvenlik seviyesi (minimal/balanced/strict) |
| `zt_maturity` | string | "medium" | Zero Trust maturity (low/medium/high) |
| `use_rag` | boolean | true | RAG retrieval kullanılsın mı |
| `rag_top_k` | integer | 5 | RAG'den kaç chunk getirileceği |
| `rag_min_score` | float | 0.7 | Minimum relevance score |

### Response Yapısı

```typescript
{
  answer: string;           // LLM'den gelen cevap
  intent: string | null;    // Tespit edilen intent
  safety_category: string | null;  // Güvenlik kategorisi
  rag_sources: Array<{      // RAG'den gelen kaynaklar
    id: string;
    score: number;
    source: string;
    section: string;
  }>;
  stats: {                  // İstatistikler
    total_calls: number;
    rag_retrieval_count: number;
    total_cost_estimate: number;
  };
  request_id: string | null;
}
```

## Troubleshooting

### Sorun 1: "RAG integration not available"

**Çözüm:** Qdrant çalışıyor mu kontrol et:
```bash
docker ps | grep qdrant
curl http://localhost:6333/collections
```

### Sorun 2: "LLM API key missing"

**Çözüm:** `.env` dosyalarını kontrol et:
```bash
cat .env
cat llm/.env
```

### Sorun 3: "No results from RAG"

**Çözüm:** Dokümanlar indekslendi mi kontrol et:
```bash
curl http://localhost:6333/collections/cis_benchmark
# points_count > 0 olmalı
```

Yeniden indeksle:
```bash
python scripts/index_documents.py
```

### Sorun 4: Import errors

**Çözüm:** Tüm bağımlılıklar yüklü mü:
```bash
pip install -r requirements.txt
cd llm && pip install -r requirements.txt
```

## Performans İpuçları

1. **RAG Score Threshold**: Düşük quality sonuçlar için `rag_min_score` değerini artır (0.7 → 0.8)
2. **Top-K Ayarı**: Daha fazla context için `rag_top_k` değerini artır (5 → 10)
3. **Model Seçimi**: Hızlı cevaplar için Groq kullan, kalite için OpenAI kullan
4. **Caching**: Sık sorulan sorular için Redis cache ekle

## Sonraki Adımlar

- [ ] Session yönetimi ile multi-turn conversation
- [ ] Streaming responses (SSE)
- [ ] Frontend UI (React/Vue)
- [ ] Reranking ile daha iyi retrieval
- [ ] Monitoring ve logging

## Destek

Sorular veya sorunlar için:
- GitHub Issues: [Repo URL]/issues
- Dokümantasyon: `RAG_LLM_INTEGRATION.md`
