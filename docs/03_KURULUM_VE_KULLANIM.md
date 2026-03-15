# Kurulum ve Kullanım

## Sistem Gereksinimleri

### Donanım
- **CPU**: 2+ core (önerilen: 4 core)
- **RAM**: Minimum 8GB (önerilen: 16GB)
  - ML model loading: ~100MB RAM
  - RAG index: ~500MB-1GB RAM
  - LLM API calls: Minimal RAM (cloud-based)
- **Disk**: 20GB boş alan
  - Dependencies: ~2GB
  - RAG index: ~500MB-2GB (OS'e göre)
  - Model files: ~50MB (intent detection)

### Yazılım
- **Python**: **3.12 veya üzeri** (ZORUNLU)
  - ⚠️ **Önemli**: Python 3.11 ve altı desteklenmez (sklearn 1.8 uyumsuzluğu)
  - ✅ Test edildi: Python 3.12.10 (Windows/Linux)
- **İşletim Sistemi**: Windows 10/11, Linux (Ubuntu 20.04+), macOS
- **İsteğe Bağlı**: Docker (Qdrant için, yoksa FAISS kullanılabilir)
- **İnternet Bağlantısı**: API key alma ve dependency kurulumu için gerekli

---

## Kurulum Yöntemi Seçimi

İki kurulum yöntemi mevcuttur:

| Yöntem | Avantaj | Dezavantaj |
|--------|---------|------------|
| **Docker** (Önerilen) | Tek komutla çalışır, ortam izolasyonu | Image büyük (~3-4 GB, torch dahil) |
| **Manuel (venv)** | Daha hafif, geliştirme için uygun | Bağımlılık yönetimi gerektirir |

---

## Seçenek A: Docker ile Çalıştırma (Önerilen)

### Gereksinimler
- Docker Desktop (Windows/macOS) veya Docker Engine (Linux)
- `.env` dosyası (API key'ler)

### 1. Repository'yi klonla

```bash
git clone https://github.com/yourusername/ai-powered-os-hardening.git
cd ai-powered-os-hardening
```

### 2. `.env` dosyasını oluştur

```bash
cp .env.example .env
```

Zorunlu key'leri doldur:

```env
LLM_PROVIDER=novita
NOVITA_API_KEY=your-novita-api-key
QDRANT_API_KEY=your-qdrant-api-key
GROQ_API_KEY=your-groq-api-key        # opsiyonel, fallback için
```

### 3. Image'ı build et ve başlat

```bash
docker compose up --build
```

İlk build `torch` ve diğer büyük paketler nedeniyle **10-20 dakika** sürebilir.
Sonraki başlatmalarda cache'den çok daha hızlı olur:

```bash
docker compose up          # cache'den başlat
docker compose up -d       # arka planda başlat
docker compose logs -f     # logları izle
docker compose down        # durdur
```

### 4. Erişim

- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health
- **Metrics**: http://localhost:8000/metrics

### Docker Notları

- `logs/` dizini volume olarak mount edilmiştir — container yeniden başlasa da loglar korunur
- `--workers 1` ile çalışır: `session_store` ve `metrics_collector` in-memory singleton olduğundan multi-worker kullanılamaz
- Qdrant **cloud** üzerinde çalışmaktadır, container içinde local Qdrant gerekmez

### Yaygın Docker Sorunları

| Sorun | Çözüm |
|-------|-------|
| `libgomp1` hatası | Base image `python:3.11-slim` kullanıldığından zaten dahil |
| `PyMuPDF` import hatası | `libgl1`, `libglib2.0-0` Dockerfile'da kurulu |
| Port 8000 kullanımda | `docker compose down` veya `lsof -ti:8000 \| xargs kill` |
| `.env` bulunamadı | `cp .env.example .env` çalıştır ve key'leri doldur |

---

## Seçenek B: Manuel Kurulum (venv)

### Adım 1: Repository Clone

```bash
git clone https://github.com/yourusername/ai-powered-os-hardening.git
cd ai-powered-os-hardening
```

---

## Adım 2: Virtual Environment Oluşturma (ÖNERİLEN - ÖNEMLİ!)

Virtual environment kullanmak **kritik öneme sahiptir**. Global Python'a paket yüklemek sistem kararlılığını bozabilir.

### Neden Virtual Environment?
1. ✅ Dependency çakışmalarını önler
2. ✅ Proje izolasyonu sağlar
3. ✅ Farklı Python versiyonları test edilebilir
4. ✅ Temiz uninstall mümkün (sadece klasörü sil)

### Linux / macOS:
```bash
# Virtual environment oluştur
python3 -m venv venv

# Aktif et
source venv/bin/activate

# Doğrula (venv) prefix görünmeli
which python
# Çıktı: /path/to/project/venv/bin/python
```

### Windows (PowerShell):
```powershell
# Virtual environment oluştur
python -m venv venv

# Aktif et
.\venv\Scripts\Activate.ps1

# Execution policy hatası alırsanız:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Doğrula
(Get-Command python).Source
# Çıktı: C:\path\to\project\venv\Scripts\python.exe
```

### Windows (CMD):
```cmd
# Virtual environment oluştur
python -m venv venv

# Aktif et
venv\Scripts\activate.bat

# Doğrula
where python
# Çıktı: C:\path\to\project\venv\Scripts\python.exe
```

**Başarı Göstergesi:**
- Terminal'de `(venv)` prefix görünmeli
- `python --version` komutu 3.12+ göstermeli
- `which python` (Linux/macOS) veya `where python` (Windows) venv path göstermeli

---

## Adım 3: Dependencies Kurulumu (Kritik Adım!)

### 3.1: pip Güncellemesi (ZORUNLU)
```bash
# pip'i en son versiyona güncelle
python -m pip install --upgrade pip

# Doğrula (pip 24.0+ olmalı)
pip --version
# Çıktı: pip 24.3.1 from /path/to/venv/lib/python3.12/site-packages/pip (python 3.12)
```

### 3.2: Dependencies Kurulumu
```bash
# requirements.txt'deki tüm paketleri kur
pip install -r requirements.txt
```

**İşlem Süresi**: ~3-5 dakika (internet hızına göre)
**Toplam Paket Sayısı**: ~86 direct + transitive dependencies

### 3.3: Kurulum Sonrası Doğrulama

Kritik paketlerin yüklendiğini kontrol edin:

```bash
# Critical packages check
python -c "import fastapi; print(f'FastAPI: {fastapi.__version__}')"
python -c "import sklearn; print(f'scikit-learn: {sklearn.__version__}')"
python -c "import torch; print(f'PyTorch: {torch.__version__}')"
python -c "import qdrant_client; print('Qdrant: OK')"

# Expected output:
# FastAPI: 0.109.x
# scikit-learn: 1.8.x (NOT 1.4 - updated for Python 3.12)
# PyTorch: 2.x.x
# Qdrant: OK
```

### Gerekli Ana Paketler (Güncel Versiyonlar):

| Paket | Versiyon | Amaç | Kritiklik |
|-------|----------|------|-----------|
| **fastapi** | 0.109+ | Web API framework | 🔴 Kritik |
| **uvicorn** | 0.27+ | ASGI server | 🔴 Kritik |
| **pydantic** | 2.6+ | Data validation | 🔴 Kritik |
| **scikit-learn** | 1.8+ | ML intent detection | 🔴 Kritik |
| **torch** | 2.x | Embeddings (transformers) | 🟡 Yüksek |
| **transformers** | 4.x | NLP models | 🟡 Yüksek |
| **langchain** | 0.1+ | LLM orchestration | 🟡 Yüksek |
| **qdrant-client** | 1.7+ | Vector DB (or faiss-cpu) | 🟡 Yüksek |
| **cohere** | 5.x | Embeddings API | 🟢 Orta |
| **groq** | 0.4+ | LLM API (ücretsiz) | 🟢 Orta |
| **slowapi** | 0.1.9+ | Rate limiting | 🟢 Orta |

### Yaygın Kurulum Sorunları ve Çözümleri

#### Sorun 1: PyTorch Kurulumu Uzun Sürüyor
**Sebep**: PyTorch büyük bir paket (~2GB)
**Çözüm**: Sabırlı olun, kurulum 5-10 dakika sürebilir
```bash
# İlerlemeyi görmek için verbose mode:
pip install -r requirements.txt -v
```

#### Sorun 2: Microsoft Visual C++ 14.0 hatası (Windows)
**Sebep**: Bazı paketler C++ compiler gerektiriyor
**Çözüm**:
```powershell
# Visual C++ Build Tools indir ve kur:
# https://visualstudio.microsoft.com/visual-cpp-build-tools/
# Veya conda kullan:
conda install pytorch -c pytorch
```

#### Sorun 3: Permission Denied (Linux/macOS)
**Sebep**: Global Python'a yazmaya çalışıyor
**Çözüm**: Virtual environment kullandığınızdan emin olun
```bash
# (venv) prefix görünmeli!
source venv/bin/activate
pip install -r requirements.txt
```

### Fresh Install Test Sonuçları (Doğrulanmış)

✅ **Test Ortamı**: /tmp/test_ai_hardening (clean install)
✅ **Python Version**: 3.12.10
✅ **Total Packages**: 86 installed
✅ **Installation Time**: 4 minutes 32 seconds
✅ **Disk Usage**: 2.1GB (venv dahil)
✅ **Test Result**: All dependencies successfully installed ✓

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
