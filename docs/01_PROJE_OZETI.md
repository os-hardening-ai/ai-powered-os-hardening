# Proje Özeti

## Proje Adı
**AI-Powered OS Hardening - RAG + LLM Tabanlı İşletim Sistemi Güvenlik Sıkılaştırma Asistanı**

*Marmara Üniversitesi - Bilgisayar Mühendisliği Bitirme Projesi*
**Geliştiriciler:** Engin, Mert, Tankut | **Akademik Yıl:** 2024-2025 | **Tarih:** 2026-05-29

## Proje Amacı
CIS Benchmark dokümanlarını kullanarak işletim sistemi güvenlik yapılandırmalarını analiz eden ve öneriler sunan yapay zeka asistanı. RAG (Retrieval-Augmented Generation) ve LLM (Large Language Model) teknolojilerini birleştirerek güvenlik uzmanlarına hızlı, doğru ve güvenilir bilgi sağlar.

## Neler Yaptık?

### 1. 4-Katmanlı Güvenlik Pipeline'ı
Güvenlik odaklı mimari tasarladık:
- **Katman 1 - Safety Classification**: LLM tabanlı tehdit tespiti (~250ms)
- **Katman 2 - Intent Detection**: Pattern matching (<1ms) + ML model (5–10ms) hibrit yaklaşımı
- **Katman 3 - Routing**: İsteği doğru handler'a yönlendirir (Pattern/Info/Action)
  - **3A Pattern Responder**: Selamlama/veda gibi sorular anında yanıtlanır ($0, <20ms)
  - **3B Info Pipeline**: Bilgi soruları RAG + LLM ile yanıtlanır (~3-4s)
  - **3C Action Pipeline**: Script/hardening istekleri CoT ile üretilir (~4-5s)
- Gerçek SSE token-streaming yanıtlar desteklenir
- Provider fallback zinciri (fail-fast): Cerebras → SambaNova → Gemini 3.1 Flash Lite → Novita

### 2. Makine Öğrenmesi Tabanlı Intent Detection
- **Dataset**: **5,362 etiketli örnek** (7 intent kategorisi) — Türkçe/İngilizce varyasyonlar
- **Model**: Logistic Regression + TF-IDF
- **Hibrit Yaklaşım**: Pattern matching (birincil, %72 kapsama) + ML fallback (%28 kapsama)
- **Performans**:
  - Test Accuracy: **%93.48**
  - Cross-Validation Mean: %91.68 (±0.97)
  - Latency: ~5-10ms (API çağrısı yok, yerel inference)
  - Maliyet: **$0**
- **Model Konumu**: `llm/ml/models/` (intent_model.joblib, intent_vectorizer.joblib)

Intent Kategorileri:
- `smalltalk_greeting`, `smalltalk_farewell`, `smalltalk_other` → Pattern Responder (3A)
- `os_hardening`, `conceptual_explanation`, `incident_analysis`, `generic_qna` → Info Pipeline (3B)
- `script_or_config` → Action Pipeline (3C)
- `out_of_scope` → Kibarca red

### 3. Gelişmiş RAG (Retrieval-Augmented Generation) Sistemi
- **Embedding**: Novita `qwen/qwen3-embedding-8b` (4096 boyut, Qdrant cloud)
- **Redis Embedding Cache**: SHA256 anahtar, 24 saatlik TTL — tekrar eden sorgularda embedding latency sıfır
- **Vector Store**: Qdrant Cloud (yönetilen servis, yerel kurulum gerektirmez)
- **Koleksiyon**: `cis_ubuntu_2404_windows11_winserver2025_with_rules`
- **Hibrit Retrieval**: BM25 (sparse) + Dense RRF fusion, MMR diversity reranking
- **Query Planning**: Her sorguda paralel 3 LLM çağrısıyla query genişletme:
  - Subqueries (bileşik soruyu parçalara ayırır)
  - HyDE (hypothetical answer passage — denser retrieval için)
  - Stepback (daha geniş context için genelleştirilmiş sorgu)
- **FilterAgent**: OS türü ve kullanıcı rolünü otomatik çıkarır (pattern → LLM fallback)
- **Session Desteği**: Redis tabanlı oturum saklama, follow-up sorular bağımsız hale getirilir
- Retrieval parametreleri: top_k=3, min_score=0.5, max_results=6

Desteklenen CIS Kaynakları:
| Kaynak | Tür | Öncelik |
|--------|-----|---------|
| CIS Ubuntu Linux 24.04 LTS Benchmark | PDF | 1 |
| CIS Microsoft Windows Server 2025 Benchmark | PDF | 2 |
| Ubuntu 24.04 CIS Rules (312 kural, YAML) | YAML | 3 |
| CIS Microsoft Windows 11 Stand-alone Benchmark | PDF | 4 |
| Windows 11 CIS Rules (YAML) | YAML | 5 |

### 4. LLM Provider Entegrasyonu
- **Primary Provider: Cerebras** (ücretsiz tier, 1M token/gün, `gpt-oss-120b`, özel donanım ~1.4s)
  - Small + Large: `gpt-oss-120b` (Safety/QueryPlanner ve yanıt üretimi)
- **Fallback zinciri (fail-fast, `max_retries=0`):** Cerebras → SambaNova (`gpt-oss-120b`) → Gemini 3.1 Flash Lite (OpenRouter, 1M context) → Novita (düşük ücretli güvenlik ağı)
- **Embedding Provider: Novita** — `qwen/qwen3-embedding-8b` (4096 dim; LLM için değil, embedding için)
- *Groq / Ollama / HuggingFace — DEPRECATED (otomatik zincirden çıkarıldı; yalnız açıkça seçilirse)*
- Tüm ayarlar `config/config.json` + `.env` üzerinden yapılandırılabilir

### 5. Domain: Rule Engine + Artifact Generator
- **Rule Engine**: CIS kural çakışması tespiti, topological sıralama, execution plan üretimi
- **Artifact Generator**: Seçilen CIS kurallarından otomatik script üretimi
  - Format: `bash`, `powershell`, `ansible`, `reg`, `gpo`
- API: `GET /api/rules`, `POST /api/rules/plan`, `POST /api/rules/conflicts`, `POST /api/artifacts/generate`

### 6. Güvenlik Özellikleri
- Rate Limiting: 100 istek/dakika per IP, 5 dakika ban
- Input Validation: Pydantic şema kontrolü (max 5000 karakter)
- Output Sanitization: LLM çıktıları API'ye dönmeden önce temizlenir
- Security Headers: HSTS, CSP, X-Frame-Options, X-Content-Type-Options
- Safety Classification: Saldırı amaçlı sorgular Layer 1'de reddedilir
- CORS yapılandırması

### 7. Gözlemlenebilirlik
- **Prometheus Metrikleri**: `/metrics` endpoint'i
- **Yapılandırılmış Loglama**: `logs/` altında ayrı dosyalar
  - `pipeline_metrics.log` — her isteğin katman bazlı zamanlaması
  - `api_requests.log` — HTTP istek logları
  - `app.log` — genel uygulama logları
- **Per-step timing**: `qplan=`, `rag_ret=`, `llm=`, `verify=` ayrı ayrı ölçülür

---

## Teknoloji Stack'i

### Backend
- **FastAPI** + **Uvicorn**: REST API + SSE streaming
- **Pydantic v2**: Veri validasyonu
- **Redis**: Embedding cache + Session store

### Machine Learning
- **scikit-learn**: Logistic Regression, TF-IDF (intent detection)
- **joblib**: Model persistance

### LLM & RAG
- **Cerebras**: Birincil LLM provider (`gpt-oss-120b`, ücretsiz tier, özel donanım ~1.4s) → SambaNova → Gemini 3.1 Flash Lite → Novita (fail-fast fallback)
- **Novita**: Embedding provider (qwen3-embedding-8b, 4096 dim)
- **Qdrant**: Cloud vektör veritabanı
- **BM25**: Sparse retrieval (hibrit RAG)

### Altyapı
- **Docker + Docker Compose**: Container ortamı
  - `docker-compose.yml`: Production config
  - `docker-compose.override.yml`: Dev config (kaynak kod volume mount)

---

## Performans Metrikleri

| Metrik | Değer |
|--------|-------|
| ML Intent Accuracy | %93.48 |
| Ortalama Yanıt (info + RAG) | ~3-4s (Cerebras; eski Groq ~8s) |
| Tek LLM çağrısı | ~1.36s (Cerebras gpt-oss-120b) |
| Agent plan / harden (medyan) | ~3.55s / ~4.62s (H3 <5sn ✓) |
| Ortalama Yanıt (basit sorgu) | ~1.5s |
| Pattern Response | <20ms |
| Safety Classification | ~250ms |
| QueryPlanner (3 parallel) | ~500ms |
| RAG Retrieval (Qdrant) | ~1-2.5s |
| Maliyet (Cerebras free tier) | ~$0 (ücretsiz) |
| Pattern Response Oranı | ~%35 (LLM çağrısı yok) |

**pipeline_metrics.log örnek çıktısı:**
```
intent=info_request path=1→2→3B
layer1=0.248s layer2=0.002s layer3=8.018s
qplan=0.566s rag_ret=4.044s llm=3.405s verify=0.000s
total=8.018s rag=True chunks=7 cost=$0.0006
```

### ML Model Sınıf Bazlı Performans
| Intent | Precision | Recall | F1-Score |
|--------|-----------|--------|----------|
| action_request | 94% | 100% | 97% |
| info_request | 94% | 92% | 93% |
| greeting | 97% | 78% | 86% |
| farewell | 100% | 67% | 80% |
| thanks | 100% | 85% | 92% |
| help | 50% | 17% | 25% |
| out_of_scope | 45% | 96% | 62% |

---

## Tamamlanan Özellikler

| Özellik | Durum |
|---------|-------|
| 4-katmanlı güvenlik pipeline | ✅ |
| ML tabanlı intent detection (%93.48) | ✅ |
| RAG — CIS Benchmark PDF indeksleme | ✅ |
| RAG — YAML kural indeksleme (312 kural) | ✅ |
| Hibrit retrieval (BM25 + Dense) | ✅ |
| MMR diversity reranking | ✅ |
| Query Planning (subqueries + HyDE + stepback) | ✅ |
| FilterAgent (OS/rol inference) | ✅ |
| Redis embedding cache | ✅ |
| Redis session store | ✅ |
| SSE streaming yanıtlar | ✅ |
| Rule Engine + Artifact Generator | ✅ |
| Docker Compose (prod + dev override) | ✅ |
| Per-step pipeline timing logları | ✅ |
| Prometheus metrikleri | ✅ |
| OpenAI-compatible API endpoint | ✅ |

## Eksik / Production Blocker

| Özellik | Öncelik |
|---------|---------|
| ~~Authentication / Authorization~~ → **JWT + RBAC + Audit eklendi ✅** | Tamam |
| HTTPS/SSL (production) | P0 — Kritik |
| Cerebras RPM rate limit (ücretsiz tier, 30 RPM) — fallback zinciri telafi eder | P1 — Önemli |
| ClaimVerifier kalibrasyonu (İP-5 groundedness 0.81→0.90) | P2 |
| Windows Server 2025 YAML kuralları (şu an boş) | P2 |

---

## API Özeti

| Endpoint | Açıklama |
|----------|----------|
| `POST /api/chat` | Ana chat endpoint (RAG + LLM + 4-layer pipeline) |
| `POST /api/chat/stream` | Streaming versiyonu (SSE) |
| `GET /api/rules` | CIS kural listesi |
| `POST /api/artifacts/generate` | Script üretimi (bash/powershell/ansible/reg/gpo) |
| `POST /v1/chat/completions` | OpenAI-compatible endpoint |
| `GET /health` | Sistem sağlık durumu |
| `GET /metrics` | Prometheus metrikleri |
| `GET /docs` | Swagger UI |

---

## Proje Yapısı (Güncel)

```
ai-powered-os-hardening/
├── main.py                    # FastAPI uygulama fabrikası
├── log_manager.py             # Loglama altyapısı
├── config/
│   ├── config.json            # RAG, embedding, LLM, Redis ayarları
│   └── config_loader.py       # Config yükleme ve doğrulama
├── api/                       # FastAPI router'ları ve middleware
├── llm/
│   ├── pipelines/
│   │   ├── secure_v2.py       # Ana 4-katmanlı pipeline
│   │   └── layers/
│   │       ├── safety_classifier.py      # Katman 1
│   │       ├── hybrid_intent_detector.py # Katman 2 (ML + pattern)
│   │       ├── pattern_responder.py      # Katman 3A
│   │       ├── info_pipeline.py          # Katman 3B (RAG + LLM)
│   │       └── action_pipeline.py        # Katman 3C (script üretimi)
│   ├── clients/               # Cerebras/SambaNova/Gemini (openai_compatible) + Novita + registry/FallbackLLM
│   └── ml/models/             # intent_model.joblib, intent_vectorizer.joblib
├── rag/
│   ├── query/                 # QueryPlanner, FilterAgent, QueryRewriter
│   ├── retrieval/             # HybridRetriever, MMRReranker
│   ├── embeddings/            # NovitaEmbeddingClient
│   ├── verify/                # ClaimVerifier (şu an devre dışı)
│   └── cache/                 # Redis embedding cache
├── domain/
│   ├── rule_engine/           # Çakışma tespiti, execution plan
│   └── artifact_generator/    # Script üretimi
├── data/
│   ├── rules/                 # ubuntu_24_04_rules.yaml (312 kural)
│   └── intent_training_dataset.csv
├── logs/                      # Runtime logları (volume mount)
├── docker-compose.yml         # Production Docker config
└── docker-compose.override.yml # Dev Docker config (otomatik yüklenir)
```

---

## Hızlı Başlangıç

```bash
# Docker ile başlat (önerilen)
cp .env.example .env   # API key'leri doldur
docker compose up -d

# Swagger UI
http://localhost:8000/docs

# Test isteği
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Ubuntu 24.04 SSH hardening nasıl yapılır?", "use_rag": true}'
```
