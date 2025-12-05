# RAG + LLM Entegrasyon Rehberi

## Genel Bakış

Bu proje artık **RAG (Retrieval Augmented Generation)** ve **LLM (Large Language Model)** sistemlerini birleştirerek çalışıyor:

1. **RAG Sistemi**: CIS benchmark dokümanlarından ilgili chunk'ları getirir
2. **LLM Sistemi**: Optimized pipeline ile kullanıcı sorularını yanıtlar
3. **Entegrasyon**: RAG'den gelen context LLM'e beslenir, böylece daha doğru ve kaynaklı cevaplar üretilir

## Mimari

```
Kullanıcı Sorusu
      ↓
[RAG Retrieval]  →  Vector Store (Qdrant) → Top-K Chunks
      ↓
[LLM Pipeline]   →  Context + Question → LLM → Cevap
      ↓
    Response (Cevap + Kaynaklar)
```

## API Endpoints

### 1. `/api/chat` - Birleşik RAG + LLM Endpoint (YENİ!)

Bu endpoint hem RAG retrieval hem de LLM cevap üretimini bir arada yapar.

#### Request

```json
POST /api/chat
{
  "question": "SSH hardening nasıl yapılır?",
  "os": "ubuntu_22_04",
  "role": "sysadmin",
  "security_level": "strict",
  "zt_maturity": "medium",
  "use_rag": true,
  "rag_top_k": 5,
  "rag_min_score": 0.7
}
```

#### Response

```json
{
  "answer": "SSH hardening için aşağıdaki adımları izleyebilirsiniz:\n\n1. PermitRootLogin'i devre dışı bırakın...",
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
  },
  "request_id": "session-20251205-123456"
}
```

### 2. `/rag/search` - RAG-Only Endpoint (Eski)

Sadece RAG retrieval yapar, LLM kullanmaz.

```json
POST /rag/search
{
  "query": "SSH hardening",
  "top_k": 5
}
```

## Kullanım Örnekleri

### Python ile Test

```python
import requests

# RAG + LLM birleşik sorgu
response = requests.post(
    "http://localhost:8000/api/chat",
    json={
        "question": "Ubuntu 22.04'te firewall konfigürasyonu nasıl yapılır?",
        "os": "ubuntu_22_04",
        "role": "sysadmin",
        "security_level": "strict",
        "use_rag": True,
        "rag_top_k": 3,
        "rag_min_score": 0.75
    }
)

data = response.json()
print("Cevap:", data["answer"])
print("\nKaynaklar:")
for source in data["rag_sources"]:
    print(f"  - {source['source']} ({source['score']:.2f})")
```

### cURL ile Test

```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Password policy önerileri nedir?",
    "use_rag": true,
    "rag_top_k": 5
  }'
```

## Yapılandırma

### RAG Parametreleri

- `use_rag` (bool): RAG retrieval kullanılsın mı (default: true)
- `rag_top_k` (int): Kaç chunk getirileceği (default: 5)
- `rag_min_score` (float): Minimum relevance score (default: 0.7)

### LLM Parametreleri

- `security_level`: minimal/balanced/strict (default: balanced)
- `zt_maturity`: low/medium/high (default: medium)
- `os`: ubuntu_22_04, debian_12, windows_11, etc.
- `role`: sysadmin, soc, developer, devops

## Optimizasyon

Pipeline otomatik olarak sorunun karmaşıklığına göre en uygun modeli seçer:

1. **Fast Path** (Smalltalk): Ultra-hızlı, RAG kullanmaz
2. **Simple Path** (Basit sorular): Küçük model, RAG opsiyonel
3. **Medium Path** (Orta): Büyük model, RAG aktif
4. **Complex Path** (Karmaşık): Büyük model + CoT reasoning, RAG aktif

## Performans

### Önceki Sistem (RAG veya LLM ayrı)
- RAG-only: Hızlı ama LLM formatlaması yok
- LLM-only: Yavaş ve kaynak bilgisi yok
- Maliyet: $0.08 / sorgu

### Yeni Sistem (RAG + LLM entegre)
- Birleşik: Hem hızlı hem kaynaklı cevaplar
- Adaptive routing ile maliyet optimizasyonu
- Maliyet: $0.015 - $0.03 / sorgu (5x daha ucuz)

## Dosya Yapısı

```
ai-powered-os-hardening/
├── api/
│   ├── router_rag.py         # RAG-only endpoint (eski)
│   ├── router_chat.py        # RAG + LLM endpoint (yeni!)
│   └── router_health.py
├── llm/
│   ├── pipeline_optimized.py # LLM pipeline (RAG entegrasyonlu)
│   ├── rag_integration.py    # RAG context builder
│   ├── context.py
│   └── ...
├── core/
│   ├── embeddings/
│   ├── vector_store/
│   └── ...
└── main.py                   # FastAPI app
```

## Troubleshooting

### RAG çalışmıyor

1. Qdrant çalışıyor mu kontrol edin:
   ```bash
   curl http://localhost:6333/collections
   ```

2. Embedding client ayarlarını kontrol edin (config.json)

3. Vector store'a data yüklenmiş mi:
   ```bash
   # Indexing script'ini çalıştırın
   python scripts/index_documents.py
   ```

### LLM cevap üretmiyor

1. `.env` dosyasındaki API key'leri kontrol edin
2. LLM config dosyasını kontrol edin (llm/config.py)
3. Debug mode açın:
   ```python
   # llm/.env
   ENABLE_DEBUG_LOGS=true
   ```

## İleriye Dönük Geliştirmeler

- [ ] Session yönetimi (chat history)
- [ ] Multi-turn conversation support
- [ ] RAG reranking (Cohere rerank API)
- [ ] Streaming responses
- [ ] WebSocket support
- [ ] Frontend UI

## Lisans

MIT License
