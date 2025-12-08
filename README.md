# AI-Powered OS Hardening

**RAG + LLM Tabanlı İşletim Sistemi Güvenlik Sıkılaştırma Asistanı**

*Bilgisayar Mühendisliği Bitirme Projesi*

---

## Proje Özeti

CIS Benchmark dokümanlarını kullanarak işletim sistemi güvenlik yapılandırmalarını analiz eden ve öneriler sunan AI asistanı. RAG ve LLM teknolojilerini birleştirerek güvenlik uzmanlarına hızlı ve doğru bilgi sağlar.

### Temel Özellikler

- **4-Layer Security Pipeline**: Safety Classification → Intent Detection → Routing → Generation
- **RAG Pipeline**: CIS Benchmark semantik arama ile güvenlik bilgisi erişimi
- **LLM Integration**: Groq (ücretsiz), OpenAI, Ollama desteği
- **Zero Trust Enrichment**: Otomatik ZT prensipleri, CIS/NIST/ISO standartları ve rollback stratejileri
- **Hybrid Validation**: Regex (hızlı, $0) + LLM (derin, $0.001) tehlikeli komut tespiti
- **Out-of-Scope Handling**: Güvenlik dışı konuları kibarca reddeder
- **Multi-Path Routing**: Pattern (3A), Info (3B), Action (3C), Out-of-Scope
- **Security**: Rate limiting, input validation, security headers
- **Monitoring**: Real-time metrics, latency tracking
- **API Documentation**: OpenAPI/Swagger UI

### Performans

| Metrik | Değer |
|--------|-------|
| Response Time | 1-3 saniye (ortalama <2s) |
| Throughput | 500+ token/s (Groq) |
| Cost Reduction | %81 (Groq ile) |
| Test Coverage | 50 test case, >95% accuracy |
| Intent Detection | 97% doğruluk |
| Routing Accuracy | 95% doğruluk |
| Safety Detection | 99% doğruluk |

---

## Hızlı Başlangıç

```bash
# 1. Clone repository
git clone https://github.com/os-hardening-ai/ai-powered-os-hardening.git
cd ai-powered-os-hardening

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure .env
echo "LLM_PROVIDER=groq" > .env
echo "GROQ_API_KEY=your_key_here" >> .env

# 4. Start API
python -m main
```

**API**: http://localhost:8000  
**Swagger UI**: http://localhost:8000/docs  
**Metrics**: http://localhost:8000/metrics

---

## Kullanım Örnekleri

### API ile Kullanım

```bash
# Info Request (Bilgi sorusu)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "SSH nedir ve nasıl çalışır?",
    "use_rag": true
  }'

# Action Request (Script oluşturma)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Ubuntu 22.04 için SSH hardening scripti oluştur",
    "os": "ubuntu_22_04",
    "role": "admin",
    "security_level": "high",
    "use_rag": true
  }'
```

### Python ile Kullanım

```bash
# Basit sohbet örneği
python llm/examples/simple_chat.py

# Script oluşturma örnekleri
python llm/examples/script_generation.py

# Bilgi soruları örnekleri
python llm/examples/info_queries.py

# Farklı OS tipleri
python llm/examples/different_os_types.py
```

### Test Etme

```bash
# Tek soruluk chat testi
python llm/tests/integration/test_single_turn_chat.py

# Tüm 50 test case ile değerlendirme
python llm/tests/pipeline_evaluator.py

# Tüm testleri çalıştır
python llm/tests/run_all_tests.py
```

---

## 📚 Dokümantasyon

Tüm dokümantasyon Türkçe olarak hazırlanmıştır. Adım adım kılavuzlar ve detaylı açıklamalar için aşağıdaki belgelere göz atın:

### Temel Dokümantasyon
1. **[Proje Özeti](docs/01_PROJE_OZETI.md)** - Neler yaptık, nasıl yaptık, sonuçlar
2. **[Pipeline ve Route'lar](docs/02_PIPELINE_VE_ROUTELAR.md)** - 4-katmanlı mimari detayları, akış şemaları
3. **[Kurulum ve Kullanım](docs/03_KURULUM_VE_KULLANIM.md)** - Adım adım kurulum, örnek kullanımlar
4. **[API Dokümantasyonu](docs/04_API_DOKUMANTASYONU.md)** - Endpoint'ler, parametreler, örnekler

### Teknik Dokümantasyon
5. **[Teknolojiler](docs/05_TEKNOLOJILER.md)** - Kullanılan teknolojiler ve nedenleri
6. **[LLM Uygulamaları](docs/06_LLM_UYGULAMALARI.md)** - ML intent detection, prompt engineering
7. **[RAG Sistemi](docs/07_RAG_SISTEMI.md)** - Retrieval-augmented generation detayları

### Hızlı Linkler
- 🚀 [Hızlı Başlangıç](docs/03_KURULUM_VE_KULLANIM.md#adım-1-repository-clone)
- 📖 [API Kullanımı](docs/04_API_DOKUMANTASYONU.md#1-chat-api)
- 🔍 [Test Sonuçları](docs/archive/VALIDATION_REPORT.md)
- 📊 [Performans Metrikleri](docs/01_PROJE_OZETI.md#sonuçlar-ve-başarılar)

---

## Proje Yapısı

```
ai-powered-os-hardening/
├── api/                   # FastAPI routers & middleware
│   ├── router_chat.py    # /api/chat endpoint
│   └── router_rag.py     # /rag/search endpoint
├── llm/
│   ├── layers/           # 4-layer security pipeline
│   │   ├── safety_classifier.py          # Layer 1: Safety
│   │   ├── hybrid_intent_detector.py     # Layer 2: ML Intent
│   │   ├── pattern_pipeline.py           # Layer 3A: Smalltalk
│   │   ├── info_pipeline.py              # Layer 3B: Info
│   │   ├── action_pipeline.py            # Layer 3C: Action
│   │   ├── zt_enrichment.py              # Zero Trust enrichment
│   │   └── output_validator.py           # Output validation
│   ├── examples/         # Usage examples
│   │   ├── simple_chat.py
│   │   ├── script_generation.py
│   │   ├── info_queries.py
│   │   └── different_os_types.py
│   ├── tests/            # Test suite
│   │   ├── integration/  # Integration tests
│   │   ├── unit/         # Unit tests
│   │   ├── test_dataset.py       # 50 test cases
│   │   ├── pipeline_evaluator.py # Automated evaluation
│   │   └── run_all_tests.py      # Test runner
│   ├── ml_intent_detector.py     # ML training & inference
│   ├── pipeline_v2.py    # Main 4-layer pipeline
│   └── models.py         # LLM model configuration
├── core/                  # RAG core (vector DB, embeddings)
│   └── rag/              # RAG components
├── data/                  # Training datasets
│   ├── intent_training_dataset.csv       # 1,230 examples
│   └── cis_benchmarks/   # CIS PDFs
├── models/                # Trained ML models
│   ├── intent_model.joblib               # Logistic Regression
│   └── intent_vectorizer.joblib          # TF-IDF
├── docs/                 # Türkçe dokümantasyon
│   ├── 01_PROJE_OZETI.md
│   ├── 02_PIPELINE_VE_ROUTELAR.md
│   ├── 03_KURULUM_VE_KULLANIM.md
│   ├── 04_API_DOKUMANTASYONU.md
│   ├── 05_TEKNOLOJILER.md
│   ├── 06_LLM_UYGULAMALARI.md
│   ├── 07_RAG_SISTEMI.md
│   └── archive/          # Eski dokümantasyon
└── main.py              # API entry point
```

---

## Teknolojiler

**Backend**: FastAPI, Pydantic, Uvicorn
**LLM**: Groq (llama-3.3-70b, llama-3.1-8b), OpenAI, Ollama
**RAG**: Cohere Embeddings, Qdrant/FAISS Vector DB
**Security**: 4-layer pipeline, hybrid validation, rate limiting, input validation, HSTS, CSP
**Testing**: 50 test cases, automated evaluation, >95% accuracy
**Architecture**: Zero Trust principles, CIS/NIST/ISO standards integration

---

## Lisans

MIT License - Detaylar için [LICENSE](LICENSE)

---

**Built with ❤️ for Computer Engineering Graduation Project**
