# 🔐 AI-Powered OS Hardening

**RAG + LLM tabanlı işletim sistemi güvenlik sıkılaştırma asistanı**

## 📋 İçindekiler

- [Özellikler](#-özellikler)
- [Kurulum](#-kurulum)
- [Kullanım](#-kullanım)
- [API Endpoints](#-api-endpoints)
- [Konfigürasyon](#️-konfigürasyon)
- [Proje Yapısı](#-proje-yapısı)

## ✨ Özellikler

### 🎁 100% Ücretsiz LLM Desteği
- **Groq**: Tamamen ücretsiz API, 500+ token/s hız (önerilen)
- **Ollama**: Lokal çalışan LLM'ler, internet gerekmez, tam gizlilik

### RAG (Retrieval Augmented Generation)
- CIS Benchmark dokümanlarından anlamsal arama
- Cohere/Novita embedding desteği
- Qdrant/FAISS vector store entegrasyonu
- Metadata extraction (CIS rule ID, profile, OS version)

### LLM Pipeline
- **Adaptive Routing**: Task karmaşıklığına göre model seçimi
- **Chain-of-Thought**: Karmaşık güvenlik analizi için CoT prompting
- **Multi-Provider**: OpenAI, Groq, HuggingFace desteği
- **Cost Optimization**: %81 maliyet düşüşü ($0.08 → $0.015)
- **Source Attribution**: Hangi kaynaklardan yanıt üretildi gösterimi

### Performans
- **Hız**: 10-15s → 2-4s (4x hızlı)
- **Maliyet**: $0.08 → $0.015 (%81 düşüş)
- **Kalite**: CoT ile daha tutarlı ve detaylı yanıtlar

## 🚀 Kurulum

### 1. Bağımlılıkları Yükle

```bash
# Root dependencies (RAG + API)
pip install -r requirements.txt

# LLM dependencies (optional, eğer LLM kullanacaksanız)
pip install -r llm/requirements.txt
```

### 2. Konfigürasyon

`.env` dosyası oluşturun:

```env
# ═══════════════════════════════════════════
# 🎁 ÜCRETSIZ SEÇENEKLER (Demo için önerilen)
# ═══════════════════════════════════════════

# Option 1: Groq (Tamamen ücretsiz, API key gerekli)
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_xxxxxxxxxxxxx  # https://console.groq.com/keys
GROQ_SMALL_MODEL_NAME=llama-3.1-8b-instant
GROQ_LARGE_MODEL_NAME=llama-3.3-70b-versatile

# Option 2: Ollama (Tamamen ücretsiz, lokal)
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_SMALL_MODEL_NAME=llama3.1:8b
# OLLAMA_LARGE_MODEL_NAME=llama3.1:70b

# ═══════════════════════════════════════════
# 💰 ÜCRETLI SEÇENEKLER (Production için)
# ═══════════════════════════════════════════

# OpenAI (Ücretli, en iyi kalite)
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-xxxxxxxxxxxxx
# OPENAI_SMALL_MODEL_NAME=gpt-4o-mini
# OPENAI_LARGE_MODEL_NAME=gpt-4o

# Embedding Provider (cohere veya sentence_transformers)
EMBEDDING_PROVIDER=cohere
COHERE_API_KEY=xxxxxxxxxxxxx

# Vector Store (qdrant veya faiss)
VECTOR_STORE_PROVIDER=qdrant
QDRANT_URL=http://localhost:6333
```

### 3. LLM Seçimine Göre Kurulum

#### Option A: Groq (Önerilen - Tamamen Ücretsiz)
```bash
# 1. https://console.groq.com/keys adresinden ücretsiz API key al
# 2. .env dosyasına ekle:
echo 'GROQ_API_KEY=gsk_your_key_here' >> .env
echo 'LLM_PROVIDER=groq' >> .env
```

#### Option B: Ollama (Lokal - Internet Gerektirmez)
```bash
# 1. Ollama'yı indir ve kur: https://ollama.ai/download
# 2. Modelleri indir:
ollama pull llama3.1:8b      # ~4.7GB
ollama pull llama3.1:70b     # ~40GB (opsiyonel, güçlü sistem gerekir)

# 3. .env dosyasını ayarla:
echo 'LLM_PROVIDER=ollama' >> .env
echo 'OLLAMA_BASE_URL=http://localhost:11434' >> .env
```

### 4. RAG Index Oluşturma

```bash
# CIS Benchmark PDF'lerini işle ve index oluştur
python -m scripts.build_index_ubuntu
```

### 5. Uygulamayı Başlat

```bash
# API server'ı başlat (http://0.0.0.0:8000)
python -m main
```

## 📖 Kullanım

### 1. RAG Search (Sadece Doküman Arama)

```bash
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Ubuntu 24.04 cramfs neden disable edilmeli?",
    "top_k": 5
  }'
```

**Yanıt:**
```json
{
  "results": [
    {
      "chunk_id": "cis-ubuntu-24.04-v1.0.0_page_965_chunk_2",
      "text": "cramfs filesystem modülü...",
      "score": 0.87,
      "metadata": {
        "cis_rule_id": "1.1.1.1",
        "os_version": "24.04",
        "profile_applicability": ["Level 1 - Server"]
      }
    }
  ]
}
```

### 2. Chat API (RAG + LLM Entegre)

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Ubuntu 24.04 sistemimde cramfs neden devre dışı bırakmalıyım?",
    "os": "ubuntu_24_04",
    "security_level": "balanced"
  }'
```

**Yanıt:**
```json
{
  "answer": "cramfs (Compressed ROM File System) kernel modülünü devre dışı bırakmanız önerilir çünkü:\n\n1. **Saldırı Yüzeyi Azaltma**: Kullanılmayan filesystem modülleri potansiyel güvenlik açıklarına yol açabilir\n2. **CIS Benchmark Uyumluluğu**: CIS Ubuntu 24.04 Level 1 profilinde gereklidir\n3. **Sıfır Kullanım**: Modern sistemlerde cramfs nadiren kullanılır\n\n**Uygulama Adımları:**\n```bash\n# Modülü blacklist'e ekle\necho 'install cramfs /bin/true' >> /etc/modprobe.d/cramfs.conf\n\n# Mevcut yüklü modülü kaldır\nrmmod cramfs\n```\n\n**Kaynak**: CIS Ubuntu Linux 24.04 LTS Benchmark v1.0.0, Rule 1.1.1.1",
  "rag_sources": [
    {
      "chunk_id": "cis-ubuntu-24.04-v1.0.0_page_965_chunk_2",
      "score": 0.87,
      "cis_rule_id": "1.1.1.1"
    }
  ],
  "stats": {
    "total_time_ms": 2450,
    "llm_calls": 1,
    "model_used": "llama-3.1-8b-instant",
    "cost_usd": 0.015
  }
}
```

## 🔌 API Endpoints

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/rag/search` | POST | RAG vektör arama (sadece doküman) |
| `/api/chat` | POST | RAG + LLM entegre sohbet |
| `/docs` | GET | Swagger API dokümantasyonu |

## ⚙️ Konfigürasyon

### `config.json` Ayarları

```json
{
  "embedding": {
    "provider": "cohere",
    "model_name": "embed-multilingual-v3.0",
    "dim": 1024
  },
  "vector_store": {
    "provider": "qdrant",
    "url": "http://localhost:6333",
    "collection_name": "cis_benchmarks"
  }
}
```

**Lokal Embedding (Cohere yerine):**
```json
{
  "embedding": {
    "provider": "sentence_transformers",
    "model_name": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "dim": 768
  },
  "vector_store": {
    "provider": "faiss"
  }
}
```

### LLM Konfigürasyonu

`.env` dosyasında:

```env
# Model seçimi
SMALL_MODEL_TEMPERATURE=0.3
LARGE_MODEL_TEMPERATURE=0.2
MAX_TOKENS=2048

# Pipeline davranışı
ENABLE_DEBUG_LOGS=false
ENABLE_JUDGE_STEP=true
ENABLE_CORRECTION_STEP=true

# API ayarları
REQUEST_TIMEOUT=60
MAX_RETRIES=2
```

## 📁 Proje Yapısı

```
ai-powered-os-hardening/
├── api/                    # FastAPI routers
│   ├── router_rag.py      # RAG search endpoint
│   └── router_chat.py     # RAG + LLM chat endpoint
├── llm/                    # LLM pipeline
│   ├── config.py          # LLM konfigürasyonu
│   ├── pipeline_optimized.py  # Ana pipeline
│   ├── rag_integration.py # RAG entegrasyon modülü
│   ├── models/            # LLM client'ları
│   ├── prompts/           # CoT ve basit promptlar
│   └── utils/             # Yardımcı fonksiyonlar
├── core/                   # RAG core
│   ├── embeddings.py      # Embedding providers
│   └── vector_stores.py   # Vector store providers
├── scripts/               # Utility scripts
│   ├── build_index_ubuntu.py  # Index oluşturma
│   └── test_rag_api.py    # RAG API test
├── config.json            # RAG konfigürasyonu
├── requirements.txt       # Python dependencies
└── main.py               # FastAPI uygulaması

```

## 📊 Performans Metrikleri

| Metrik | Eski Pipeline | Yeni Pipeline | İyileşme |
|--------|--------------|--------------|----------|
| **Süre** | 10-15s | 2-4s | 4x hızlı |
| **Maliyet** | $0.08 | $0.015 | %81 düşüş |
| **LLM Çağrısı** | 6-7 | 1-2 | %85 azalma |
| **Token Kullanımı** | ~12K | ~2K | %83 azalma |

## 🧪 Test Etme

```bash
# RAG API testi
python -m scripts.test_rag_api

# Novita embedding testi
python -m scripts.test_novita_embedding

# Entegrasyon testi
python test_rag_llm_integration.py
```

## 📝 İşlem Süreleri

```
[IndexPipeline] cis_ubuntu_24_04 için 1378 chunk oluşturuldu.
[IndexPipeline] Chunk embedding bulundu, API çağrısı yapılmayacak.
[IndexPipeline] cis_ubuntu_24_04 için index güncellendi.
[IndexPipeline] İstatistikler -> chunks: 1378, embed_time: 4739.20s, upsert_time: 96.61s
```

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/AmazingFeature`)
3. Değişikliklerinizi commit edin (`git commit -m 'feat: Add AmazingFeature'`)
4. Branch'inizi push edin (`git push origin feature/AmazingFeature`)
5. Pull Request açın

## 📄 Lisans

Bu proje MIT lisansı altındadır.

## 🙏 Teşekkürler

- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks) - Güvenlik standartları
- [Qdrant](https://qdrant.tech/) - Vector database
- [Cohere](https://cohere.ai/) - Multilingual embeddings
- [Groq](https://groq.com/) - Ultra-fast LLM inference
