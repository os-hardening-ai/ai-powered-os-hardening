# AI-Powered OS Hardening

**RAG + LLM Tabanlı İşletim Sistemi Güvenlik Sıkılaştırma Asistanı**

*Bilgisayar Mühendisliği Bitirme Projesi*

---

## Proje Özeti

CIS Benchmark dokümanlarını kullanarak işletim sistemi güvenlik yapılandırmalarını analiz eden ve öneriler sunan AI asistanı. RAG ve LLM teknolojilerini birleştirerek güvenlik uzmanlarına hızlı ve doğru bilgi sağlar.

### Temel Özellikler

- **RAG Pipeline**: CIS Benchmark semantik arama
- **LLM Integration**: Groq (ücretsiz), OpenAI, Ollama
- **Adaptive Routing**: Görev karmaşıklığına göre otomatik model seçimi
- **Security**: Rate limiting, input validation, security headers
- **Monitoring**: Real-time metrics, latency tracking
- **API Documentation**: OpenAPI/Swagger UI

### Performans

| Metrik | Değer |
|--------|-------|
| Response Time | 2-4 saniye |
| Throughput | 500+ token/s (Groq) |
| Cost Reduction | %81 |
| Test Coverage | 93% |

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

## Kullanım Örneği

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Ubuntu 24.04 SSH hardening",
    "security_level": "balanced"
  }'
```

---

## Dokümantasyon

| Dosya | İçerik |
|-------|---------|
| [SETUP.md](docs/SETUP.md) | Detaylı kurulum ve konfigürasyon |
| [API.md](docs/API.md) | API endpoints ve kullanım |
| [SECURITY.md](docs/SECURITY.md) | Güvenlik özellikleri |
| [QUICKSTART.md](docs/QUICKSTART.md) | Hızlı başlangıç kılavuzu |
| **LLM Dokümantasyonu** | |
| [LLM_ARCHITECTURE.md](docs/LLM_ARCHITECTURE.md) | LLM pipeline, CoT, routing detayları |
| [PIPELINE_ANALYSIS.md](docs/PIPELINE_ANALYSIS.md) | 5 route detaylı analizi |
| [PARAMETER_USAGE.md](docs/PARAMETER_USAGE.md) | Parametre kullanım kılavuzu |
| [PARAMETER_AND_RAG_STRATEGY.md](docs/PARAMETER_AND_RAG_STRATEGY.md) | Parametre ve RAG stratejisi |
| [PATH_EVALUATION_AND_IMPROVEMENTS.md](docs/PATH_EVALUATION_AND_IMPROVEMENTS.md) | Path değerlendirme ve iyileştirmeler |
| **RAG Dokümantasyonu** | |
| [RAG_LLM_INTEGRATION.md](docs/RAG_LLM_INTEGRATION.md) | RAG + LLM entegrasyonu |
| [RAG_SETUP_GUIDE.md](docs/RAG_SETUP_GUIDE.md) | RAG kurulum ve konfigürasyon |
| **Test ve Güvenlik** | |
| [TESTS.md](docs/TESTS.md) | Test dokümantasyonu |

---

## Proje Yapısı

```
ai-powered-os-hardening/
├── api/                   # FastAPI routers & middleware
├── llm/                   # LLM pipeline
├── core/                  # RAG core
├── tests/                 # Test suite (93% coverage)
├── docs/                  # Detaylı dokümantasyon
└── main.py               # API entry point
```

---

## Teknolojiler

**Backend**: FastAPI, Pydantic, Uvicorn  
**LLM**: Groq, OpenAI, Ollama  
**RAG**: Cohere, Qdrant, FAISS  
**Security**: Rate limiting, input validation, HSTS, CSP  
**Testing**: Pytest (53/57 tests passed)

---

## Lisans

MIT License - Detaylar için [LICENSE](LICENSE)

---

**Built with ❤️ for Computer Engineering Graduation Project**
