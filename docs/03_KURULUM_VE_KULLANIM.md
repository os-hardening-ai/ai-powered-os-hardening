# Kurulum ve Kullanım

## Sistem Gereksinimleri

### Donanım
- **CPU**: 2+ core (önerilen: 4 core)
- **RAM**: Minimum 8GB (önerilen: 16GB)
- **Disk**: 20GB boş alan (RAG index için)

### Yazılım
- **Python**: 3.12 veya üzeri
- **İşletim Sistemi**: Windows 10/11, Linux, macOS
- **İsteğe Bağlı**: Docker (Qdrant için)

---

## Adım 1: Repository Clone

```bash
git clone https://github.com/yourusername/ai-powered-os-hardening.git
cd ai-powered-os-hardening
```

---

## Adım 2: Virtual Environment Oluşturma (Önerilen)

### Linux / macOS:
```bash
python -m venv venv
source venv/bin/activate
```

### Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

Virtual environment aktif olduğunda terminal'inizde `(venv)` ön eki görünecektir.

---

## Adım 3: Dependencies Kurulumu

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Gerekli Ana Paketler:
- **fastapi** (v0.109+): Web framework
- **uvicorn** (v0.27+): ASGI server
- **pydantic** (v2.6+): Data validation
- **scikit-learn** (v1.4+): ML models
- **langchain** (v0.1+): LLM orchestration
- **qdrant-client** veya **faiss-cpu**: Vector store
- **cohere**: Embeddings
- **groq**: LLM API (ücretsiz)

---

## Adım 4: Environment Variables Ayarları

Proje kök dizininde `.env` dosyası oluşturun:

```bash
# .env dosyası
# =============

# LLM Provider (groq, openai, ollama)
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_groq_api_key_here

# Embedding Provider
EMBEDDING_PROVIDER=cohere
COHERE_API_KEY=your_cohere_api_key_here

# Vector Store (qdrant veya faiss)
VECTOR_STORE_PROVIDER=qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=cis_benchmarks

# Optional: OpenAI
# OPENAI_API_KEY=sk-your-openai-key

# Optional: Ollama (local)
# OLLAMA_BASE_URL=http://localhost:11434
```

### API Key Alma Rehberi

#### Groq API Key (ÜCRETSİZ)
1. https://console.groq.com/keys adresine gidin
2. Google hesabınızla giriş yapın
3. "Create API Key" butonuna tıklayın
4. Key'i kopyalayın ve `.env` dosyasına ekleyin

**Not**: Groq tamamen ücretsizdir ve çok hızlıdır (500+ token/s).

#### Cohere API Key (ÜCRETSİZ Trial)
1. https://dashboard.cohere.com/api-keys adresine gidin
2. Hesap oluşturun
3. API key'i kopyalayın
4. `.env` dosyasına ekleyin

**Not**: Free tier ayda 100 istek sınırı vardır. Prototip için yeterlidir.

---

## Adım 5: ML Model Eğitimi

Intent detection modeli henüz eğitilmemişse:

```bash
python llm/ml_intent_detector.py
```

**Çıktı:**
```
Training ML Intent Detector...
Dataset loaded: 1230 samples
Features extracted: 544 TF-IDF features
Training Logistic Regression...
Cross-validation: 85.37% ± 2.72%
Test accuracy: 82.52%
Model saved: models/intent_model.joblib
Vectorizer saved: models/intent_vectorizer.joblib
✓ Training complete!
```

**Not**: Eğitimli modeller (`models/` klasöründe) zaten repo'da mevcutsa bu adımı atlayabilirsiniz.

---

## Adım 6: Qdrant Vektör Veritabanı (RAG için)

### Seçenek A: Docker ile (Önerilen)

```bash
docker run -d -p 6333:6333 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant
```

### Seçenek B: FAISS (Docker'sız)

`.env` dosyasında:
```bash
VECTOR_STORE_PROVIDER=faiss
```

**Not**: FAISS yerel dosya tabanlı, daha basit ama Qdrant kadar ölçeklenebilir değil.

---

## Adım 7: RAG Index Oluşturma

CIS Benchmark dokümanlarını vektör veritabanına yükleyin:

```bash
python scripts/build_index_ubuntu.py
```

**Çıktı:**
```
Loading CIS Ubuntu 24.04 Benchmark...
Splitting into chunks...
Generating embeddings (Cohere)...
Uploading to Qdrant...
✓ Index created: 1,245 chunks
✓ Collection: cis_benchmarks
```

### Diğer OS'ler için:
```bash
python scripts/build_index_centos.py    # CentOS 9
python scripts/build_index_windows.py   # Windows Server 2022
```

**Not**: Her OS için ayrı script çalıştırmanız gerekmez. İhtiyacınız olan OS'ler için index oluşturun.

---

## Adım 8: API'yi Başlatma

```bash
python -m main
```

**Çıktı:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Loading ML intent detector...
INFO:     Models loaded: intent_model.joblib, intent_vectorizer.joblib
INFO:     RAG system initialized (Qdrant)
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

API artık çalışıyor! Şu adreslere erişebilirsiniz:

- **API Base**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **Metrics**: http://localhost:8000/metrics
- **Health Check**: http://localhost:8000/health

---

## Kullanım Örnekleri

### 1. Swagger UI ile Test (En Kolay)

1. Tarayıcınızda http://localhost:8000/docs açın
2. `/api/chat` endpoint'ini bulun
3. "Try it out" butonuna tıklayın
4. Request body'yi düzenleyin:
```json
{
  "question": "Ubuntu 22.04 için SSH hardening scripti oluştur",
  "os": "ubuntu_22_04",
  "role": "admin",
  "security_level": "balanced",
  "use_rag": true
}
```
5. "Execute" butonuna tıklayın
6. Response'u görün!

### 2. cURL ile API Kullanımı

#### Basit Bilgi Sorusu:
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "SSH nedir ve nasıl çalışır?"
  }'
```

#### Script Oluşturma:
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Ubuntu 22.04 için SSH hardening scripti oluştur",
    "os": "ubuntu_22_04",
    "role": "admin",
    "security_level": "strict",
    "zt_maturity": "high",
    "use_rag": true
  }'
```

#### RAG Kapalı (Genel Sorular):
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Zero Trust nedir?",
    "use_rag": false
  }'
```

### 3. Python ile Kullanım

#### Basit Örnek:
```python
import requests

url = "http://localhost:8000/api/chat"
payload = {
    "question": "CentOS 9 için firewall yapılandırması oluştur",
    "os": "centos_9",
    "role": "sysadmin"
}

response = requests.post(url, json=payload)
result = response.json()

print("Answer:", result["answer"])
print("Intent:", result["intent"])
print("Layer Path:", result["stats"]["layer_path"])
print("Time:", result["stats"]["total_time_s"], "seconds")
```

#### Örnek Scriptleri Çalıştırma:
```bash
# Basit sohbet testi
python examples/simple_chat.py

# Script oluşturma örnekleri
python examples/script_generation.py

# Bilgi soruları
python examples/info_queries.py

# Farklı OS tipleri
python examples/different_os_types.py
```

### 4. Python ile Direct Pipeline Kullanımı (API olmadan)

```python
from llm.pipeline_v2 import create_pipeline_v2
from llm.models import RequestContext

# Pipeline oluştur
pipeline = create_pipeline_v2(use_ml=True, debug=True)

# Request context
ctx = RequestContext(
    user_question="Ubuntu 24.04 için SSH hardening scripti oluştur",
    os="ubuntu_24_04",
    role="admin",
    security_level="balanced",
    zt_maturity="medium"
)

# İşle
result = pipeline.process(ctx)

# Sonuç
print(result.answer)
print(f"Intent: {result.intent.type}")
print(f"Layer Path: {result.stats.layer_path}")
print(f"Time: {result.stats.total_time_s:.2f}s")
```

---

## Test Etme

### 1. Tek Soruluk Chat Testi
```bash
python tests/integration/test_single_turn_chat.py
```

### 2. Tüm 50 Test Case ile Değerlendirme
```bash
python tests/pipeline_evaluator.py
```

**Çıktı:**
```
Running 50 test cases...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 50/50 (100%)

Results:
✓ Passed: 48/50 (96%)
✗ Failed: 2/50 (4%)
Avg time: 2.1s
Total cost: $0.082
```

### 3. Tüm Unit ve Integration Testlerini Çalıştırma
```bash
python tests/run_all_tests.py
```

---

## API Parametreleri Detayları

### `/api/chat` Endpoint

**Required Parametreler:**
- `question` (string, 1-5000 karakter): Kullanıcı sorusu

**Optional Parametreler:**
- `os` (string): İşletim sistemi
  - Seçenekler: `ubuntu_22_04`, `ubuntu_24_04`, `centos_9`, `windows_server_2022`, `debian_12`
  - Varsayılan: `None` (action request'lerde gerekli)

- `role` (string): Kullanıcı rolü
  - Seçenekler: `admin`, `sysadmin`, `soc`, `developer`, `devops`
  - Varsayılan: `None` (action request'lerde gerekli)

- `security_level` (string): Güvenlik seviyesi
  - Seçenekler: `minimal`, `balanced`, `strict`
  - Varsayılan: `balanced`

- `zt_maturity` (string): Zero Trust maturity level
  - Seçenekler: `low`, `medium`, `high`
  - Varsayılan: `medium`

- `use_rag` (bool): RAG kullanılsın mı?
  - Varsayılan: `true`

- `rag_top_k` (int): RAG'den kaç chunk çekilsin?
  - Aralık: 1-20
  - Varsayılan: `5`

- `rag_min_score` (float): Minimum relevance score
  - Aralık: 0.0-1.0
  - Varsayılan: `0.7`

### Response Formatı

```json
{
  "answer": "SSH hardening için aşağıdaki script'i oluşturdum:\n\n#!/bin/bash\n...",
  "intent": {
    "type": "action_request",
    "subtype": null,
    "confidence": 0.92,
    "method": "ml"
  },
  "safety_category": "safe_defensive",
  "layer_path": "1->2->3C->4",
  "rag_sources": [
    {
      "id": "chunk_123",
      "score": 0.89,
      "source": "CIS_Ubuntu_24.04_Benchmark_v1.0.0",
      "section": "5.2.3 Ensure SSH access is limited"
    }
  ],
  "stats": {
    "total_time_s": 3.21,
    "layer_path": "1->2->3C->4",
    "layer_1_time_s": 0.65,
    "layer_2_time_s": 0.008,
    "layer_3_time_s": 2.48,
    "layer_4_time_s": 0.072
  },
  "request_id": "req_1234567890",
  "estimated_cost": 0.0018
}
```

---

## Yaygın Sorunlar ve Çözümleri

### Problem 1: ModuleNotFoundError
```
ModuleNotFoundError: No module named 'fastapi'
```

**Çözüm:**
```bash
pip install -r requirements.txt
```

---

### Problem 2: Qdrant Connection Error
```
ConnectionError: Could not connect to Qdrant at http://localhost:6333
```

**Çözüm 1 (Docker):**
```bash
docker run -d -p 6333:6333 qdrant/qdrant
```

**Çözüm 2 (FAISS):**
`.env` dosyasında:
```
VECTOR_STORE_PROVIDER=faiss
```

---

### Problem 3: API Key Hatası
```
AuthenticationError: Invalid API key
```

**Çözüm:**
1. `.env` dosyasını kontrol edin
2. API key'lerin doğru olduğundan emin olun
3. Groq: https://console.groq.com/keys
4. Cohere: https://dashboard.cohere.com/api-keys

---

### Problem 4: Unicode Encoding Error (Windows)
```
UnicodeEncodeError: 'charmap' codec can't encode character
```

**Çözüm:**
Bu hata Windows'ta Türkçe karakterlerle oluşabilir. Kod zaten UTF-8 desteği eklenmiş durumda, ama eğer hala görüyorsanız:

```bash
# PowerShell'de
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Veya CMD'de
chcp 65001
```

---

### Problem 5: ML Model Bulunamadı
```
FileNotFoundError: models/intent_model.joblib not found
```

**Çözüm:**
```bash
python llm/ml_intent_detector.py
```

Bu komut modelleri eğitip `models/` klasörüne kaydedecektir.

---

### Problem 6: Port Zaten Kullanımda
```
OSError: [Errno 98] Address already in use
```

**Çözüm:**
```bash
# Linux/macOS: 8000 portunu kullanan process'i bul ve kapat
lsof -ti:8000 | xargs kill -9

# Windows: 8000 portunu kullanan process'i bul
netstat -ano | findstr :8000
# PID'yi not alın, sonra:
taskkill /PID <pid> /F

# Veya farklı bir port kullanın:
uvicorn main:app --port 8001
```

---

## Performans İpuçları

### 1. RAG Optimizasyonu
- Basit sorular için `use_rag=false` kullanın (daha hızlı)
- `rag_top_k` değerini düşürün (default: 5 → 3)
- `rag_min_score` değerini artırın (default: 0.7 → 0.75) daha alakalı sonuçlar için

### 2. LLM Model Seçimi
```bash
# Hız için (8B model)
LLM_PROVIDER=groq
GROQ_MODEL=llama-3.1-8b-instant

# Kalite için (70B model)
LLM_PROVIDER=groq
GROQ_MODEL=llama-3.3-70b-versatile
```

### 3. Caching (Gelecek Özellik)
Aynı soruları cache'lemek için Redis kullanabilirsiniz.

---

## Güvenlik Notları

### Production Deployment için:
1. **Rate Limiting**: `.env`'de `RATE_LIMIT=100` (default)
2. **HTTPS**: Reverse proxy (nginx) kullanın
3. **API Key Authentication**: Eklenebilir (şu an yok)
4. **Input Validation**: Zaten mevcut (Pydantic)
5. **CORS**: `api/middleware.py`'de yapılandırın

### .env Dosyası Güvenliği:
- `.env` dosyasını **asla** Git'e commit etmeyin (`.gitignore`'da olmalı)
- Production'da environment variables kullanın
- API key'leri şifreleyin (vault, secrets manager)

---

## Sonraki Adımlar

1. ✅ Kurulum tamamlandı
2. ✅ API çalışıyor
3. ✅ Testler başarılı
4. 📖 [API Dokümantasyonu](04_API_DOKUMANTASYONU.md) okuyun
5. 📖 [LLM Uygulamaları](06_LLM_UYGULAMALARI.md) detaylarına bakın
6. 🚀 Kendi projelerinizde kullanın!

---

## Yardım ve Destek

- **Dokümantasyon**: [docs/](.)
- **Örnek Kodlar**: [examples/](../examples/)
- **Testler**: [tests/](../tests/)
- **Issues**: GitHub Issues

İyi çalışmalar! 🚀
