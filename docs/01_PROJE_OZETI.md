# Proje Özeti

## Proje Adı
**AI-Powered OS Hardening - RAG + LLM Tabanlı İşletim Sistemi Güvenlik Sıkılaştırma Asistanı**

*Bilgisayar Mühendisliği Bitirme Projesi*

## Proje Amacı
CIS Benchmark dokümanlarını kullanarak işletim sistemi güvenlik yapılandırmalarını analiz eden ve öneriler sunan yapay zeka asistanı. RAG (Retrieval-Augmented Generation) ve LLM (Large Language Model) teknolojilerini birleştirerek güvenlik uzmanlarına hızlı, doğru ve güvenilir bilgi sağlar.

## Neler Yaptık?

### 1. 4-Katmanlı Güvenlik Pipeline'ı
Güvenlik odaklı mimari tasarladık:
- **Katman 1 - Safety Classification**: Tehlikeli komutları tespit eder (LLM-based)
- **Katman 2 - Intent Detection**: Kullanıcı niyetini ML ile belirler (greeting, info, action, out-of-scope)
- **Katman 3 - Routing**: İsteği doğru handler'a yönlendirir (Pattern/Info/Action)
- **Katman 4 - Generation**: RAG + LLM ile yanıt üretir

### 2. Makine Öğrenmesi Tabanlı Intent Detection
- **Dataset**: 1,230 etiketli örnek (7 intent kategorisi)
- **Model**: Logistic Regression + LinearSVM kombinasyonu
- **TF-IDF Vektörizasyon**: 544 özellik, n-gram (1-3)
- **Performans**: %85.37 CV doğruluğu, %82.52 test doğruluğu
- **Hybrid Approach**: Pattern matching (hız) + ML (doğruluk) kombinasyonu

Intent Kategorileri:
- `greeting`: Selamlaşma (200 örnek)
- `farewell`: Veda (150 örnek)
- `thanks`: Teşekkür (100 örnek)
- `help`: Yardım istekleri (92 örnek)
- `info_request`: Bilgi soruları (325 örnek)
- `action_request`: Script/yapılandırma istekleri (231 örnek)
- `out_of_scope`: Güvenlik dışı konular (132 örnek)

### 3. RAG (Retrieval-Augmented Generation) Sistemi
- CIS Benchmark dokümanlarından semantik arama
- Cohere Embeddings ile vektör temsili
- Qdrant/FAISS vektör veritabanı
- Top-K retrieval (varsayılan: 5 chunk, min score: 0.7)
- Alakalı güvenlik dokümanlarını otomatik bulma

### 4. Multi-LLM Desteği
- **Groq** (ücretsiz, hızlı): llama-3.3-70b-versatile, llama-3.1-8b-instant
- **OpenAI**: GPT-4, GPT-3.5-turbo
- **Ollama**: Yerel model desteği (llama2, mistral, etc.)

### 5. Zero Trust Enrichment
- Otomatik Zero Trust prensipleri ekleme
- CIS/NIST/ISO standartları entegrasyonu
- Rollback stratejileri ve güvenlik seviyelerine göre özelleştirme
- 3 maturity level: low, medium, high

### 6. Güvenlik Özellikleri
- **Hybrid Validation**: Regex (hızlı, $0) + LLM (derin, $0.001) tehlikeli komut tespiti
- **Input Validation**: Pydantic ile güçlü tip kontrolü (max 5000 karakter)
- **Rate Limiting**: 100 istek/dakika per IP
- **Security Headers**: HSTS, CSP, X-Frame-Options, X-Content-Type-Options
- **Out-of-Scope Handling**: Güvenlik dışı konuları kibarca reddeder
- **Safety Classification**: Saldırı amaçlı sorguları Layer 1'de reddeder

### 7. Kapsamlı Test ve Doğrulama
- 50 test case ile pipeline değerlendirmesi
- Unit testler (core, llm, api modülleri)
- Integration testler (end-to-end)
- %95+ doğruluk oranı
- Otomatik performans raporlama

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

## Sonuçlar ve Başarılar

### Performans Metrikleri
| Metrik | Değer |
|--------|-------|
| Ortalama Yanıt Süresi | 1-3 saniye |
| ML Intent Accuracy | %85.37 (5-fold CV) |
| Pipeline Doğruluğu | %95+ (50 test) |
| Safety Detection | %99 |
| Test Coverage | 50 test case |
| Maliyet Azaltma | %81 (Groq ile) |
| Pattern Response | <1ms (LLM-free) |

### ML Model Performansı Detayları
| Metrik | Değer |
|--------|-------|
| Training Accuracy | %91.16 |
| Test Accuracy | %82.52 |
| Cross-validation Mean | %85.37 ± 2.72 |
| TF-IDF Features | 544 |
| Inference Time | <10ms |
| Model Size | ~50KB (joblib) |

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

## Gelecek Geliştirmeler (Potansiyel)

1. **Çok Dilli Destek**: İngilizce, Türkçe yanıtlar
2. **Daha Fazla OS**: RHEL, Debian, Arch Linux, macOS
3. **Fine-tuned Model**: Özel güvenlik domain model'i
4. **Real-time Monitoring**: Canlı güvenlik dashboard
5. **Chat UI**: Web tabanlı kullanıcı arayüzü (React/Vue)
6. **Sohbet Geçmişi**: Multi-turn conversation support
7. **Audit Logs**: Compliance için detaylı loglama

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
