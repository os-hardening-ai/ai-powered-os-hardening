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
python examples/simple_chat.py

# Script oluşturma örnekleri
python examples/script_generation.py

# Bilgi soruları örnekleri
python examples/info_queries.py

# Farklı OS tipleri
python examples/different_os_types.py
```

### Test Etme

```bash
# Tek soruluk chat testi
python tests/integration/test_single_turn_chat.py

# Tüm 50 test case ile değerlendirme
python tests/pipeline_evaluator.py

# Tüm testleri çalıştır
python tests/run_all_tests.py
```

---

## Dokümantasyon

📖 **[Detaylı Dokümantasyon Rehberi](docs/README.md)**

### Hızlı Başlangıç
- [QUICKSTART_BASIT.md](docs/guides/QUICKSTART_BASIT.md) - Basit Türkçe rehber
- [QUICKSTART.md](docs/QUICKSTART.md) - 5 dakikada başlayın
- [SETUP.md](docs/SETUP.md) - Detaylı kurulum
- [API.md](docs/API.md) - API kullanımı

### Mimari ve LLM
- [REVISED_ROUTE_ARCHITECTURE.md](docs/REVISED_ROUTE_ARCHITECTURE.md) - 4-Layer güvenlik mimarisi (2025 best practices)
- [LLM_ARCHITECTURE.md](docs/LLM_ARCHITECTURE.md) - LLM pipeline detayları
- [LLM_IMPROVEMENTS_ANALYSIS.md](docs/LLM_IMPROVEMENTS_ANALYSIS.md) - Modern LLM teknikleri ve iyileştirmeler
- [STEPS_TO_LAYERS_MIGRATION.md](docs/STEPS_TO_LAYERS_MIGRATION.md) - Mimari geçiş rehberi

### RAG, Güvenlik ve Test
- [RAG_SETUP_GUIDE.md](docs/RAG_SETUP_GUIDE.md) - RAG kurulum
- [SECURITY.md](docs/SECURITY.md) - Güvenlik özellikleri
- [TESTING_GUIDE.md](docs/TESTING_GUIDE.md) - Test rehberi (50 test case)
- [tests/README.md](tests/README.md) - Test dokümantasyonu

---

## Proje Yapısı

```
ai-powered-os-hardening/
├── api/                   # FastAPI routers & middleware
├── llm/
│   ├── layers/           # 4-layer security pipeline
│   │   ├── safety_classifier.py      # Layer 1: Safety
│   │   ├── intent_detector.py        # Layer 2: Intent
│   │   ├── pattern_pipeline.py       # Layer 3A: Smalltalk
│   │   ├── info_pipeline.py          # Layer 3B: Info
│   │   ├── action_pipeline.py        # Layer 3C: Action
│   │   ├── zt_enrichment.py          # Zero Trust enrichment
│   │   └── output_validator.py       # Output validation
│   ├── pipeline_v2.py    # Main 4-layer pipeline
│   └── models.py         # LLM model configuration
├── core/                  # RAG core (vector DB, embeddings)
├── tests/
│   ├── integration/      # Integration tests
│   ├── unit/             # Unit tests
│   ├── test_dataset.py   # 50 test cases
│   ├── pipeline_evaluator.py  # Automated evaluation
│   └── run_all_tests.py  # Test runner
├── examples/             # Usage examples
│   ├── simple_chat.py
│   ├── script_generation.py
│   ├── info_queries.py
│   └── different_os_types.py
├── docs/                 # Comprehensive documentation
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
