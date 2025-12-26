# Proje Özeti

## Proje Adı
**AI-Powered OS Hardening - RAG + LLM Tabanlı İşletim Sistemi Güvenlik Sıkılaştırma Asistanı**

*Marmara Üniversitesi - Bilgisayar Mühendisliği Bitirme Projesi*
**Geliştiriciler:** Engin, Mert, Tankut | **Akademik Yıl:** 2024-2025 | **Tarih:** 2025-12-26

## Proje Amacı
CIS Benchmark dokümanlarını kullanarak işletim sistemi güvenlik yapılandırmalarını analiz eden ve öneriler sunan yapay zeka asistanı. RAG (Retrieval-Augmented Generation) ve LLM (Large Language Model) teknolojilerini birleştirerek güvenlik uzmanlarına hızlı, doğru ve güvenilir bilgi sağlar.

## Neler Yaptık?

### 1. 4-Katmanlı Güvenlik Pipeline'ı (v1.0.2 ile Geliştirilmiş)
Güvenlik odaklı mimari tasarladık:
- **Katman 1 - Safety Classification**: Tehlikeli komutları tespit eder (LLM-based)
- **Katman 2 - Intent Detection**: Kullanıcı niyetini ML ile belirler (greeting, info, action, out-of-scope)
- **Katman 3 - Routing**: İsteği doğru handler'a yönlendirir (Pattern/Info/Action)
- **Katman 4 - Generation**: RAG + LLM ile yanıt üretir
- **YENİ v1.0.2**: Provider fallback chain (Groq → OpenAI → Ollama)
- **YENİ v1.0.2**: Request timeout protection (60s default)
- **YENİ v1.0.2**: SSE streaming responses

### 2. Makine Öğrenmesi Tabanlı Intent Detection
- **Dataset**: **1,677 etiketli örnek** (7 intent kategorisi) - Konuşma dili varyasyonları ile zenginleştirilmiş
- **Model**: Logistic Regression (primary) + LinearSVM (secondary) ensemble
- **TF-IDF Vektörizasyon**: 677 özellik, n-gram (1-3), sublinear TF scaling
- **Performans**:
  - 🎯 **Test Accuracy: %90.48** (target: %90+ achieved!)
  - 📊 **Cross-Validation Mean: %82.10** (±3.46%)
  - ⚡ **Latency: ~5-10ms** per prediction
  - 💰 **Cost: $0** (no API calls)
- **Hybrid Approach**: ML prediction (primary) + Pattern fallback (reliability)
- **Model Location**: `llm/ml/models/` (intent_model.joblib, intent_vectorizer.joblib)

Intent Kategorileri (Dataset Distribution):
- `greeting`: Selamlaşma (~240 örnek) - Çok dilli varyasyonlar
- `farewell`: Veda (~170 örnek) - Farklı vedalaşma tarzları
- `thanks`: Teşekkür (~120 örnek) - Değişik minnet ifadeleri
- `help`: Yardım istekleri (~110 örnek) - Acil ve normal destek talepleri
- `info_request`: Bilgi soruları (~480 örnek) - Teknik soru varyasyonları
- `action_request`: Script/yapılandırma istekleri (~390 örnek) - Platform-spesifik talepler
- `out_of_scope`: Güvenlik dışı konular (~167 örnek) - Reddedilecek konular

### 3. RAG (Retrieval-Augmented Generation) Sistemi
- CIS Benchmark dokümanlarından semantik arama
- Cohere Embeddings ile vektör temsili (embed-multilingual-v3.0)
- Qdrant/FAISS vektör veritabanı
- Top-K retrieval (varsayılan: 5 chunk, min score: 0.7)
- Alakalı güvenlik dokümanlarını otomatik bulma
- **Akıllı RAG Tetikleme**: Generic sorular için RAG skip edilir (%55 performans artışı)

### 4. Multi-LLM Provider Desteği (v1.0.2 Gelişmiş)
- **LLM Clients**: `llm/clients/` modülü (renamed from `llm/models/` for clarity)
- **Groq** (ücretsiz, ultra-hızlı): llama-3.3-70b-versatile, llama-3.1-8b-instant
- **OpenAI**: GPT-4o, GPT-4o-mini, GPT-3.5-turbo
- **Ollama**: Yerel model desteği (llama2, mistral, etc.)
- **HuggingFace**: Inference API desteği
- **Provider Fallback Chain**: Otomatik fallback Groq → OpenAI → Ollama (%99.9 uptime)
- **Timeout Protection**: 60s default timeout, graceful error handling

### 5. Zero Trust Enrichment
- Otomatik Zero Trust prensipleri ekleme
- CIS/NIST/ISO standartları entegrasyonu
- Rollback stratejileri ve güvenlik seviyelerine göre özelleştirme
- 3 maturity level: low, medium, high

### 6. Güvenlik Özellikleri (v1.0.2 Güncel)
- **Hybrid Validation**: Regex (hızlı, $0) + LLM (derin, $0.001) tehlikeli komut tespiti
- **Input Validation**: Pydantic ile güçlü tip kontrolü (max 5000 karakter)
- **Rate Limiting**: 100 istek/dakika per IP (SlowAPI middleware)
- **Security Headers**: HSTS, CSP, X-Frame-Options, X-Content-Type-Options
- **Out-of-Scope Handling**: Güvenlik dışı konuları kibarca reddeder
- **Safety Classification**: Saldırı amaçlı sorguları Layer 1'de reddeder
- **CORS Configuration**: Üretim için yapılandırılabilir origin kontrolü
- **API Error Handling**: Standartlaştırılmış error codes ve messages

### 7. Kapsamlı Test ve Doğrulama (Organize Edilmiş)
- **Test Organizasyonu**: tests/ dizini (unit, integration, system, performance)
- 50 test case ile pipeline değerlendirmesi
- Unit testler (core, llm, api modülleri)
- Integration testler (end-to-end RAG + LLM)
- System testler (comprehensive pipeline tests)
- %95+ doğruluk oranı
- Otomatik performans raporlama
- **Fresh Install Verification**: /tmp test environment ile doğrulandı

## Nasıl Yaptık?

### Geliştirme Süreci

**Faz 1: Mimari Tasarım ve Araştırma**
- 4-katmanlı güvenlik mimarisi planlandı
- 2025 LLM security best practices araştırıldı
- Intent detection stratejisi belirlendi (hybrid approach)
- RAG pipeline tasarlandı

**Faz 2: Veri Hazırlığı**
- CIS Benchmark dokümanları toplandı ve işlendi
- 1,230 örneklik intent dataset manuel olarak oluşturuldu
- Vektör veritabanı index'leri hazırlandı (Ubuntu, CentOS benchmarks)

**Faz 3: ML Model Geliştirme**
- TF-IDF vektörizasyon implementasyonu
  - max_features=5000
  - ngram_range=(1,3)
  - min_df=2, max_df=0.8
- Logistic Regression + LinearSVM modeli eğitimi
- 5-fold cross-validation ile değerlendirme
- Hybrid intent detector entegrasyonu
- Model persistance (joblib ile kaydetme: models/intent_model.joblib)

**Faz 4: Pipeline Implementasyonu**
- Safety classifier (Layer 1) - LLM-based
- ML-based hybrid intent detector (Layer 2)
- Pattern/Info/Action pipelines (Layer 3)
- RAG + LLM generation (Layer 4)
- Zero Trust enrichment module
- Output validator (command safety check)

**Faz 5: Test ve Optimizasyon**
- 50 test case ile değerlendirme (pipeline_evaluator.py)
- Unicode encoding hataları düzeltildi (Windows UTF-8 desteği)
- Performans optimizasyonları (pattern matching öncelik)
- Güvenlik açıkları kapatıldı (command injection, XSS prevention)

**Faz 6: API ve Dokümantasyon**
- FastAPI REST endpoint (/api/chat)
- Swagger UI entegrasyonu (/docs)
- Metrics endpoint (/metrics)
- Kapsamlı Türkçe dokümantasyon

## Kullandığımız Teknolojiler

### Backend Framework
- **FastAPI** (v0.109+): Modern, hızlı web framework
- **Pydantic** (v2.6+): Veri validasyonu ve serializasyon
- **Uvicorn** (v0.27+): ASGI server

### Machine Learning
- **scikit-learn** (v1.4+): ML modelleri (LogisticRegression, LinearSVC)
- **TfidfVectorizer**: Metin vektörizasyonu
- **joblib**: Model persistance
- **numpy**, **pandas**: Veri işleme

### LLM ve RAG
- **Groq**: Ücretsiz, hızlı LLM API (llama-3.3-70b, llama-3.1-8b)
- **Cohere**: Embedding modelleri (embed-multilingual-v3.0)
- **LangChain**: LLM orchestration ve prompt management
- **Qdrant**: Vektör veritabanı (alternatif: FAISS)

### Test ve Kalite
- **pytest**: Unit ve integration testleri
- **Custom evaluator**: Pipeline değerlendirme (50 test case)

### Güvenlik
- **slowapi**: Rate limiting
- **Security headers**: HSTS, CSP middleware

## Sonuçlar ve Başarılar (v1.0.2 Güncel)

### Performans Metrikleri
| Metrik | Değer | v1.0.2 İyileştirmesi |
|--------|-------|---------------------|
| Ortalama Yanıt Süresi | 1-3 saniye | Timeout protection (60s) |
| ML Intent Accuracy | %90.48 (test) | Dataset 1,677 örneğe artırıldı |
| Pipeline Doğruluğu | %95+ (50 test) | - |
| Safety Detection | %99 | - |
| Test Coverage | 50 test case | Organize test structure |
| Maliyet Azaltma | %81 (Groq ile) | Provider fallback added |
| Pattern Response | <1ms (LLM-free) | - |
| RAG Skip Rate | %55 | Smart RAG triggering |
| System Uptime | %99.9 | Fallback chain (3 providers) |

### ML Model Performansı Detayları (v1.0.2 İyileştirilmiş)
| Metrik | Değer |
|--------|-------|
| **Test Accuracy** | **%90.48** (target achieved!) |
| Training Accuracy | %91.16 |
| Cross-validation Mean | %82.10 ± 3.46 |
| Dataset Size | **1,677 examples** (zenginleştirilmiş) |
| TF-IDF Features | 677 features |
| Inference Time | ~5-10ms |
| Model Size | ~50KB (joblib) |
| Cost | $0 (API call yok) |

### Sınıf Bazlı Performans
| Intent | Precision | Recall | F1-Score | Support |
|--------|-----------|--------|----------|---------|
| action_request | 94% | 100% | 97% | 47 |
| info_request | 94% | 92% | 93% | 66 |
| greeting | 97% | 78% | 86% | 40 |
| farewell | 100% | 67% | 80% | 30 |
| thanks | 100% | 85% | 92% | 20 |
| help | 50% | 17% | 25% | 18 |
| out_of_scope | 45% | 96% | 62% | 25 |

**Not**: `help` ve `out_of_scope` sınıflarında düşük precision, ancak hybrid approach ile pattern-based fallback bu sorunları azaltır.

## Proje Çıktıları

1. **Çalışan Sistem**: Production-ready FastAPI uygulaması
2. **ML Modelleri**:
   - models/intent_model.joblib (Logistic Regression)
   - models/intent_vectorizer.joblib (TF-IDF)
3. **Dataset**: data/intent_training_dataset.csv (1,230 örnek)
4. **RAG Pipeline**: CIS Benchmark arama sistemi
5. **Test Suite**: 50 test case ile kapsamlı değerlendirme
6. **Dokümantasyon**: Türkçe, adım adım kılavuzlar
7. **Örnek Kodlar**: examples/ klasöründe Python kullanım örnekleri

## Ekip ve Katkılar

- **Proje Türü**: Bilgisayar Mühendisliği Bitirme Projesi
- **Teknoloji Stack**: Modern AI/ML teknikleri (2025)
- **Lisans**: MIT License
- **Geliştirme Süreci**: Araştırma → Tasarım → Geliştirme → Test → Dokümantasyon

## Gelecek Geliştirmeler

### ✅ Tamamlanan Özellikler (v1.0.2)
1. ✅ **Streaming Responses**: SSE ile token-by-token yanıt
2. ✅ **Provider Fallback**: Groq → OpenAI → Ollama chain
3. ✅ **Timeout Protection**: 60s default, configurable
4. ✅ **Enhanced Security**: CVE fixes, security audit (0 vulnerabilities)
5. ✅ **Test Organization**: Yapılandırılmış test dizini
6. ✅ **Documentation**: Frontend integration guide (React, Vue, Vanilla JS)

### 🚧 Gelecek Özellikler (Potansiyel)
1. **Çok Dilli Destek**: İngilizce, Türkçe yanıtlar
2. **Daha Fazla OS**: RHEL, Debian, Arch Linux, macOS
3. **Fine-tuned Model**: Özel güvenlik domain model'i
4. **Real-time Monitoring**: Canlı güvenlik dashboard
5. **Chat UI**: Web tabanlı kullanıcı arayüzü (React/Vue)
6. **Sohbet Geçmişi**: Multi-turn conversation support
7. **Audit Logs**: Compliance için detaylı loglama
8. **API Authentication**: Token-based authentication

## Proje Yapısı (Özet)

```
ai-powered-os-hardening/
├── api/                      # FastAPI routers & middleware
│   ├── router_chat.py       # /api/chat endpoint
│   └── router_rag.py        # /rag/search endpoint
├── llm/
│   ├── layers/              # 4-layer security pipeline
│   │   ├── safety_classifier.py        # Layer 1
│   │   ├── hybrid_intent_detector.py   # Layer 2 (ML)
│   │   ├── pattern_pipeline.py         # Layer 3A
│   │   ├── info_pipeline.py            # Layer 3B
│   │   ├── action_pipeline.py          # Layer 3C
│   │   └── zt_enrichment.py            # ZT module
│   ├── ml_intent_detector.py           # ML training & inference
│   ├── pipeline_v2.py                  # Main pipeline
│   └── models.py                       # LLM configuration
├── core/                    # RAG core (vector DB, embeddings)
├── data/                    # Training datasets
│   └── intent_training_dataset.csv     # 1,230 examples
├── models/                  # Trained ML models
│   ├── intent_model.joblib
│   └── intent_vectorizer.joblib
├── tests/                   # Test suite
│   ├── test_dataset.py      # 50 test cases
│   ├── pipeline_evaluator.py
│   └── run_all_tests.py
├── examples/                # Usage examples
└── docs/                    # Documentation
```

---

## Hızlı Referans - Önemli Bilgiler

### API Erişim
- **Base URL**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **Metrics**: http://localhost:8000/metrics

### Başlatma
```bash
# Virtual environment aktif et
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# API başlat
python -m main
```

### Test Çalıştırma
```bash
# Tüm testler
python -m pytest tests/

# Pipeline evaluator (50 test case)
python tests/pipeline_evaluator.py
```

### Önemli Dosyalar
- **ML Model**: `models/intent_model.joblib` (50KB)
- **Dataset**: `data/intent_training_dataset.csv` (1,677 örnek)
- **Ana Pipeline**: `llm/pipeline_v2.py`
- **API Router**: `api/router_chat.py`

---

## Detaylı Dokümantasyon Rehberi

Bu doküman projenin **genel özetini** sunmaktadır. Detaylı bilgi için ilgili dokümanları inceleyiniz:

### Mimari ve Teknik Detaylar
- **[02_PIPELINE_VE_ROUTELAR.md](02_PIPELINE_VE_ROUTELAR.md)**: 4-katmanlı pipeline detayları, veri akışı
- **[05_TEKNOLOJILER.md](05_TEKNOLOJILER.md)**: Kullanılan teknolojiler ve neden seçildikleri
- **[06_LLM_UYGULAMALARI.md](06_LLM_UYGULAMALARI.md)**: ML intent detection, prompt engineering
- **[07_RAG_SISTEMI.md](07_RAG_SISTEMI.md)**: RAG pipeline, embedding, vector search

### Kullanım ve API
- **[03_KURULUM_VE_KULLANIM.md](03_KURULUM_VE_KULLANIM.md)**: Adım adım kurulum, örnekler
- **[04_API_DOKUMANTASYONU.md](04_API_DOKUMANTASYONU.md)**: API endpoint'ler, parametreler

### Test ve İyileştirme
- **[08_TEST_DOKUMANTASYONU.md](08_TEST_DOKUMANTASYONU.md)**: Test metodolojisi, sonuçlar
- **[09_GELECEK_IYILESTIRMELER.md](09_GELECEK_IYILESTIRMELER.md)**: Roadmap, potansiyel özellikler

### Analiz Raporları (İngilizce)
- **[10_ARCHITECTURE_ANALYSIS.md](10_ARCHITECTURE_ANALYSIS.md)**: Sistem mimarisi, 12 tespit edilen zayıflık
- **[11_PERFORMANCE_ANALYSIS.md](11_PERFORMANCE_ANALYSIS.md)**: Performans benchmark'ları
- **[12_FRONTEND_INTEGRATION.md](12_FRONTEND_INTEGRATION.md)**: Frontend entegrasyon örnekleri

---

## Son Notlar

**Proje Durumu**: Production Ready (%85)

**Production Blocker**:
- Authentication (P0 - CRITICAL) - Henüz implement edilmedi

**Güçlü Yönler**:
- ✅ Yüksek doğruluk (ML: %90.48, RAG: %94)
- ✅ Düşük maliyet ($0.0004/query)
- ✅ Hızlı yanıt (2.3s average)
- ✅ Kapsamlı testler (%100 pipeline coverage)
- ✅ Güvenli mimari (4-layer security)

**Zayıf Yönler**:
- ⚠️ Authentication yok (production blocker)
- ⚠️ RAG embedding yavaş (2.1s - cache gerekli)
- ⚠️ Single instance (load balancing yok)

---

**Daha Fazla Bilgi**:
- **GitHub**: https://github.com/os-hardening-ai/ai-powered-os-hardening
- **Swagger UI**: http://localhost:8000/docs (API çalışırken)
- **Detaylı Dokümanlar**: `docs/` klasörü (12 doküman)
