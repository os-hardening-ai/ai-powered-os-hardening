# AI-Powered OS Hardening - Dokümantasyon

## 📚 Dokümantasyon Rehberi

### Hızlı Başlangıç
- **[QUICKSTART.md](QUICKSTART.md)** - Projeyi 5 dakikada çalıştırın
- **[SETUP.md](SETUP.md)** - Detaylı kurulum talimatları
- **[API.md](API.md)** - API endpoints ve kullanım örnekleri

### LLM Pipeline Mimarisi
- **[REVISED_ROUTE_ARCHITECTURE.md](REVISED_ROUTE_ARCHITECTURE.md)** ⭐ **BAŞLANGIÇ NOKTASI**
  - 4-Layer güvenlik odaklı mimari (2025 best practices)
  - Layer 1: Safety Classification
  - Layer 2: Intent Detection
  - Layer 3A: Smalltalk Handler
  - Layer 3B: Info Pipeline (RAG + LLM)
  - Layer 3C: Action Pipeline (Script generation)

- **[LLM_ARCHITECTURE.md](LLM_ARCHITECTURE.md)** - Detaylı LLM pipeline dokümantasyonu
  - CoT prompting stratejileri
  - Model seçimi ve optimizasyonları
  - Performans metrikleri

### RAG Sistemi
- **[RAG_SETUP_GUIDE.md](RAG_SETUP_GUIDE.md)** - RAG kurulum ve konfigürasyon
- **[RAG_LLM_INTEGRATION.md](RAG_LLM_INTEGRATION.md)** - RAG + LLM entegrasyonu

### Güvenlik ve Test
- **[SECURITY.md](SECURITY.md)** - Güvenlik özellikleri
- **[TESTS.md](TESTS.md)** - Test dokümantasyonu (93% coverage)
- **[../SECURITY_FIXES.md](../SECURITY_FIXES.md)** - Son güvenlik güncellemeleri

### Geliştirme Notları (Arşiv)
Bu dokümantlar geliştirme sürecinde oluşturulmuştur. Güncel mimari için [REVISED_ROUTE_ARCHITECTURE.md](REVISED_ROUTE_ARCHITECTURE.md) dosyasına bakın:

- ~~PIPELINE_ANALYSIS.md~~ → REVISED_ROUTE_ARCHITECTURE.md kullanın
- ~~PATH_EVALUATION_AND_IMPROVEMENTS.md~~ → REVISED_ROUTE_ARCHITECTURE.md kullanın
- ~~PARAMETER_AND_RAG_STRATEGY.md~~ → REVISED_ROUTE_ARCHITECTURE.md kullanın
- ~~PARAMETER_USAGE.md~~ → REVISED_ROUTE_ARCHITECTURE.md kullanın

## 🎯 Hangi Dokümandan Başlamalıyım?

### Projeyi kullanmak istiyorum
1. [QUICKSTART.md](QUICKSTART.md)
2. [API.md](API.md)

### Mimariyi anlamak istiyorum
1. [REVISED_ROUTE_ARCHITECTURE.md](REVISED_ROUTE_ARCHITECTURE.md) ⭐
2. [LLM_ARCHITECTURE.md](LLM_ARCHITECTURE.md)

### Projeye katkıda bulunmak istiyorum
1. [REVISED_ROUTE_ARCHITECTURE.md](REVISED_ROUTE_ARCHITECTURE.md)
2. [TESTS.md](TESTS.md)
3. [RAG_LLM_INTEGRATION.md](RAG_LLM_INTEGRATION.md)

### Güvenlik analizi yapıyorum
1. [SECURITY.md](SECURITY.md)
2. [../SECURITY_FIXES.md](../SECURITY_FIXES.md)
3. [REVISED_ROUTE_ARCHITECTURE.md](REVISED_ROUTE_ARCHITECTURE.md) - Layer 1: Safety Classification

## 📊 Proje İstatistikleri

- **Test Coverage**: 93%
- **Response Time**: 2-4 saniye
- **Cost Reduction**: %81 (CoT optimizasyonu ile)
- **LLM-free Queries**: ~35% (Local + Pattern responses)
- **Supported LLMs**: Groq (ücretsiz), OpenAI, Ollama
