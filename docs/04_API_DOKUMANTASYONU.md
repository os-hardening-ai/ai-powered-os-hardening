# API Dokümantasyonu

## Genel Bilgiler

**Base URL**: `http://localhost:8000`
**API Version**: v1
**Protocol**: HTTP/HTTPS
**Format**: JSON

**Swagger UI**: http://localhost:8000/docs
**ReDoc**: http://localhost:8000/redoc

---

## Authentication

Şu anda authentication **yoktur**. Production deployment için API key authentication eklenmesi önerilir.

---

## Endpoints Listesi

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| POST | `/api/chat` | Ana chat endpoint (RAG + LLM) |
| POST | `/rag/search` | Sadece RAG araması |
| GET | `/health` | Health check |
| GET | `/metrics` | Performans metrikleri |

---

## 1. Chat API

### `POST /api/chat`

RAG + LLM entegre sohbet. 4-katmanlı güvenlik pipeline'ı ile sorguları işler.

#### Request

**Headers:**
```
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "question": "Ubuntu 22.04 için SSH hardening scripti oluştur",
  "os": "ubuntu_22_04",
  "role": "admin",
  "security_level": "balanced",
  "zt_maturity": "medium",
  "use_rag": true,
  "rag_top_k": 5,
  "rag_min_score": 0.7
}
```

#### Parametreler

| Parametre | Tip | Zorunlu | Açıklama | Varsayılan |
|-----------|-----|---------|----------|------------|
| `question` | string | ✅ Evet | Kullanıcı sorusu (1-5000 karakter) | - |
| `os` | string | ❌ Hayır | İşletim sistemi | `null` |
| `role` | string | ❌ Hayır | Kullanıcı rolü | `null` |
| `security_level` | string | ❌ Hayır | Güvenlik seviyesi | `balanced` |
| `zt_maturity` | string | ❌ Hayır | Zero Trust maturity | `medium` |
| `use_rag` | boolean | ❌ Hayır | RAG kullan | `true` |
| `rag_top_k` | integer | ❌ Hayır | RAG chunk sayısı (1-20) | `5` |
| `rag_min_score` | float | ❌ Hayır | Min relevance score (0.0-1.0) | `0.7` |

#### Parametre Detayları

**`os` (İşletim Sistemi):**
- `ubuntu_22_04` - Ubuntu 22.04 LTS
- `ubuntu_24_04` - Ubuntu 24.04 LTS
- `centos_9` - CentOS Stream 9
- `windows_server_2022` - Windows Server 2022
- `debian_12` - Debian 12 (Bookworm)

**Not**: Action request'lerde (script oluşturma) `os` parametresi **gereklidir**.

**`role` (Kullanıcı Rolü):**
- `admin` - Sistem yöneticisi
- `sysadmin` - Sistem yöneticisi (genel)
- `soc` - SOC analisti
- `developer` - Yazılım geliştirici
- `devops` - DevOps mühendisi

**Not**: Action request'lerde `role` parametresi **gereklidir**.

**`security_level` (Güvenlik Seviyesi):**
- `minimal` - Minimum güvenlik (development ortamları)
- `balanced` - Dengeli güvenlik (çoğu production ortamı)
- `strict` - Maksimum güvenlik (yüksek riskli ortamlar)

**`zt_maturity` (Zero Trust Maturity):**
- `low` - Temel ZT prensipleri (least privilege, logging)
- `medium` - Orta seviye ZT (+ MFA, network segmentation)
- `high` - İleri seviye ZT (+ continuous validation, micro-segmentation)

#### Response

**Status Code**: `200 OK`

**Body (JSON):**
```json
{
  "answer": "Ubuntu 22.04 için SSH hardening scripti:\n\n#!/bin/bash\n# SSH Hardening Script\n...",
  "intent": {
    "type": "action_request",
    "subtype": null,
    "confidence": 0.92,
    "method": "ml",
    "ml_probabilities": {
      "action_request": 0.92,
      "info_request": 0.06,
      "help": 0.01,
      "greeting": 0.01
    }
  },
  "safety_category": "safe_defensive",
  "layer_path": "1->2->3C->4",
  "rag_sources": [
    {
      "id": "chunk_ubuntu_22_04_ssh_001",
      "score": 0.89,
      "source": "CIS_Ubuntu_22.04_Benchmark_v2.0.0",
      "section": "5.2.3 Ensure SSH access is limited",
      "content": "SSH configuration best practices include..."
    },
    {
      "id": "chunk_ubuntu_22_04_ssh_002",
      "score": 0.85,
      "source": "CIS_Ubuntu_22.04_Benchmark_v2.0.0",
      "section": "5.2.4 Ensure SSH root login is disabled",
      "content": "PermitRootLogin no should be set..."
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
  "request_id": "req_1701234567890_abc123",
  "estimated_cost": 0.0018
}
```

#### Response Alanları

| Alan | Tip | Açıklama |
|------|-----|----------|
| `answer` | string | LLM'den gelen yanıt |
| `intent` | object | Intent detection sonucu |
| `intent.type` | string | Intent tipi (smalltalk, info_request, action_request, out_of_scope) |
| `intent.subtype` | string | Alt tip (greeting, farewell, thanks, help - sadece smalltalk için) |
| `intent.confidence` | float | Güven skoru (0.0-1.0) |
| `intent.method` | string | Detection metodu (pattern, ml, hybrid) |
| `intent.ml_probabilities` | object | ML model olasılıkları (sadece ML kullanıldığında) |
| `safety_category` | string | Güvenlik kategorisi (safe_defensive, safe_educational, etc.) |
| `layer_path` | string | Pipeline path (1→2→3A, 1→2→3B→4, etc.) |
| `rag_sources` | array | RAG'den gelen kaynaklar (varsa) |
| `stats` | object | Performans istatistikleri |
| `stats.total_time_s` | float | Toplam süre (saniye) |
| `stats.layer_*_time_s` | float | Katman bazlı süreler |
| `request_id` | string | Unique request ID (loglama için) |
| `estimated_cost` | float | Tahmini maliyet (USD) |

#### Layer Paths

| Path | Açıklama | Örnek Soru |
|------|----------|------------|
| `1->REJECT` | Unsafe query rejected | "SQL injection nasıl yapılır?" |
| `1->2->3A` | Smalltalk (pattern response) | "Merhaba", "Teşekkürler" |
| `1->2->OUT_OF_SCOPE` | Out-of-scope rejected | "Hava durumu nedir?" |
| `1->2->3B->4` | Info request (RAG + LLM) | "SSH nedir?" |
| `1->2->3C->4` | Action request (RAG + LLM + ZT) | "SSH scripti oluştur" |

#### Error Responses

**400 Bad Request** - Geçersiz parametre:
```json
{
  "detail": [
    {
      "loc": ["body", "question"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**422 Unprocessable Entity** - Validation hatası:
```json
{
  "detail": "question must be between 1 and 5000 characters"
}
```

**429 Too Many Requests** - Rate limit aşıldı:
```json
{
  "detail": "Rate limit exceeded: 100 requests per minute"
}
```

**500 Internal Server Error** - Sunucu hatası:
```json
{
  "detail": "Internal server error",
  "request_id": "req_1701234567890"
}
```

#### Örnek Kullanımlar

##### Örnek 1: Basit Bilgi Sorusu

**Request:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "SSH nedir ve nasıl çalışır?"
  }'
```

**Response:**
```json
{
  "answer": "SSH (Secure Shell), ağ üzerinden güvenli bir şekilde uzak bilgisayarlara erişmek için kullanılan bir şifreleme protokolüdür...",
  "intent": {
    "type": "info_request",
    "confidence": 0.89,
    "method": "ml"
  },
  "safety_category": "safe_educational",
  "layer_path": "1->2->3B->4",
  "rag_sources": [...],
  "stats": {
    "total_time_s": 2.1
  },
  "estimated_cost": 0.0012
}
```

##### Örnek 2: Script Oluşturma (Tüm Parametreler)

**Request:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Ubuntu 24.04 için SSH hardening scripti oluştur",
    "os": "ubuntu_24_04",
    "role": "admin",
    "security_level": "strict",
    "zt_maturity": "high",
    "use_rag": true,
    "rag_top_k": 7,
    "rag_min_score": 0.75
  }'
```

**Response:**
```json
{
  "answer": "#!/bin/bash\n# SSH Hardening Script for Ubuntu 24.04\n# Security Level: STRICT\n# Zero Trust Maturity: HIGH\n\nset -euo pipefail\n\n...",
  "intent": {
    "type": "action_request",
    "confidence": 0.94,
    "method": "ml"
  },
  "safety_category": "safe_defensive",
  "layer_path": "1->2->3C->4",
  "rag_sources": [
    {
      "score": 0.91,
      "source": "CIS_Ubuntu_24.04_Benchmark_v1.0.0",
      "section": "5.2 SSH Server Configuration"
    }
  ],
  "stats": {
    "total_time_s": 3.8,
    "layer_1_time_s": 0.72,
    "layer_2_time_s": 0.009,
    "layer_3_time_s": 3.01,
    "layer_4_time_s": 0.061
  },
  "estimated_cost": 0.0021
}
```

##### Örnek 3: RAG Kapalı (Genel Soru)

**Request:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Zero Trust nedir?",
    "use_rag": false
  }'
```

**Response:**
```json
{
  "answer": "Zero Trust, \"asla güvenme, her zaman doğrula\" prensibiyle çalışan bir güvenlik modelidir...",
  "intent": {
    "type": "info_request",
    "confidence": 0.87,
    "method": "ml"
  },
  "safety_category": "safe_educational",
  "layer_path": "1->2->3B",
  "rag_sources": [],
  "stats": {
    "total_time_s": 1.4
  },
  "estimated_cost": 0.0008
}
```

##### Örnek 4: Greeting (Smalltalk)

**Request:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Merhaba"
  }'
```

**Response:**
```json
{
  "answer": "Merhaba! Siber güvenlik konusunda size nasıl yardımcı olabilirim?",
  "intent": {
    "type": "smalltalk",
    "subtype": "greeting",
    "confidence": 1.0,
    "method": "pattern"
  },
  "safety_category": "safe_defensive",
  "layer_path": "1->2->3A",
  "rag_sources": [],
  "stats": {
    "total_time_s": 0.61
  },
  "estimated_cost": 0.0
}
```

##### Örnek 5: Out-of-Scope

**Request:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Bugün hava nasıl?"
  }'
```

**Response:**
```json
{
  "answer": "Üzgünüm, sadece siber güvenlik ve OS hardening konularında yardımcı olabilirim. Güvenlik sorunuz var mı?",
  "intent": {
    "type": "out_of_scope",
    "confidence": 0.95,
    "method": "pattern"
  },
  "safety_category": "safe_defensive",
  "layer_path": "1->2->OUT_OF_SCOPE",
  "rag_sources": [],
  "stats": {
    "total_time_s": 0.59
  },
  "estimated_cost": 0.0
}
```

##### Örnek 6: Unsafe Query (Rejected)

**Request:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "SQL injection nasıl yapılır?"
  }'
```

**Response:**
```json
{
  "answer": "Üzgünüm, bu tür saldırı tekniklerine yardımcı olamam. Sadece savunma ve güvenlik sıkılaştırma konularında destek verebilirim.",
  "intent": {
    "type": "action_request",
    "confidence": 0.23,
    "method": "pattern"
  },
  "safety_category": "unsafe_offensive",
  "layer_path": "1->REJECT",
  "rag_sources": [],
  "stats": {
    "total_time_s": 0.71
  },
  "estimated_cost": 0.0
}
```

---

## 2. RAG Search API

### `POST /rag/search`

Sadece RAG araması yapar, LLM generation yapmaz. Doküman araması için kullanılır.

#### Request

```json
{
  "query": "SSH configuration best practices",
  "top_k": 5,
  "min_score": 0.7
}
```

#### Parametreler

| Parametre | Tip | Zorunlu | Açıklama | Varsayılan |
|-----------|-----|---------|----------|------------|
| `query` | string | ✅ Evet | Arama sorgusu | - |
| `top_k` | integer | ❌ Hayır | Sonuç sayısı (1-20) | `5` |
| `min_score` | float | ❌ Hayır | Min similarity score (0.0-1.0) | `0.7` |

#### Response

```json
{
  "results": [
    {
      "id": "chunk_ubuntu_22_04_ssh_001",
      "score": 0.91,
      "source": "CIS_Ubuntu_22.04_Benchmark_v2.0.0",
      "section": "5.2.3 Ensure SSH access is limited",
      "content": "SSH should be configured to limit access..."
    },
    {
      "id": "chunk_ubuntu_22_04_ssh_002",
      "score": 0.87,
      "source": "CIS_Ubuntu_22.04_Benchmark_v2.0.0",
      "section": "5.2.4 Ensure SSH root login is disabled",
      "content": "PermitRootLogin should be set to no..."
    }
  ],
  "count": 2,
  "query": "SSH configuration best practices"
}
```

#### Örnek Kullanım

```bash
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "cramfs filesystem disable",
    "top_k": 3
  }'
```

---

## 3. Health Check

### `GET /health`

Sistem sağlık kontrolü.

#### Request

```bash
curl http://localhost:8000/health
```

#### Response

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "llm": "operational",
    "rag": "operational",
    "ml_model": "loaded"
  },
  "timestamp": "2025-01-08T12:34:56Z"
}
```

---

## 4. Metrics

### `GET /metrics`

Performans metrikleri ve istatistikler.

#### Request

```bash
curl http://localhost:8000/metrics
```

#### Response

```json
{
  "total_requests": 1523,
  "avg_response_time_s": 2.1,
  "layer_distribution": {
    "1->2->3A": 342,
    "1->2->3B->4": 789,
    "1->2->3C->4": 312,
    "1->2->OUT_OF_SCOPE": 56,
    "1->REJECT": 24
  },
  "intent_distribution": {
    "smalltalk": 342,
    "info_request": 789,
    "action_request": 312,
    "out_of_scope": 80
  },
  "avg_cost_per_request": 0.0009,
  "total_cost": 1.37,
  "uptime_seconds": 86400
}
```

---

## Rate Limiting

**Limit**: 100 requests / minute per IP
**Ban Duration**: 5 minutes

**Response (429 Too Many Requests):**
```json
{
  "detail": "Rate limit exceeded: 100 requests per minute. Try again in 45 seconds."
}
```

---

## CORS

CORS varsayılan olarak etkindir:

**Allowed Origins**: `*` (tüm originler)
**Allowed Methods**: `GET, POST, PUT, DELETE, OPTIONS`
**Allowed Headers**: `*`

Production'da `allowed_origins`'i kısıtlayın:
```python
# api/middleware.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Sadece bu domain
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

---

## Security Headers

Otomatik eklenen güvenlik header'ları:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Content-Security-Policy: default-src 'self'
```

---

## Swagger UI Kullanımı

1. **Tarayıcıda açın**: http://localhost:8000/docs
2. **Endpoint seçin**: `/api/chat`
3. **"Try it out"** butonuna tıklayın
4. **Request body düzenleyin**
5. **"Execute"** butonuna tıklayın
6. **Response'u görün**

---

## Postman Collection

API'yi Postman ile test etmek için:

1. Postman'i açın
2. Import → Raw Text
3. Aşağıdaki JSON'u yapıştırın:

```json
{
  "info": {
    "name": "AI-Powered OS Hardening API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Chat - Info Request",
      "request": {
        "method": "POST",
        "header": [{"key": "Content-Type", "value": "application/json"}],
        "body": {
          "mode": "raw",
          "raw": "{\"question\": \"SSH nedir?\"}"
        },
        "url": {
          "raw": "http://localhost:8000/api/chat",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8000",
          "path": ["api", "chat"]
        }
      }
    },
    {
      "name": "Chat - Action Request",
      "request": {
        "method": "POST",
        "header": [{"key": "Content-Type", "value": "application/json"}],
        "body": {
          "mode": "raw",
          "raw": "{\"question\": \"Ubuntu 22.04 için SSH scripti oluştur\", \"os\": \"ubuntu_22_04\", \"role\": \"admin\"}"
        },
        "url": {
          "raw": "http://localhost:8000/api/chat",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8000",
          "path": ["api", "chat"]
        }
      }
    }
  ]
}
```

---

## Python SDK Örneği

```python
import requests

class OSHardeningClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url

    def chat(self, question, **kwargs):
        """
        Chat API wrapper

        Args:
            question (str): User question
            **kwargs: Optional parameters (os, role, security_level, etc.)

        Returns:
            dict: API response
        """
        payload = {"question": question, **kwargs}
        response = requests.post(f"{self.base_url}/api/chat", json=payload)
        response.raise_for_status()
        return response.json()

    def search(self, query, top_k=5):
        """RAG search wrapper"""
        payload = {"query": query, "top_k": top_k}
        response = requests.post(f"{self.base_url}/rag/search", json=payload)
        response.raise_for_status()
        return response.json()

# Kullanım
client = OSHardeningClient()

# Bilgi sorusu
result = client.chat("SSH nedir?")
print(result["answer"])

# Script oluşturma
result = client.chat(
    "Ubuntu 24.04 için SSH hardening scripti",
    os="ubuntu_24_04",
    role="admin",
    security_level="strict"
)
print(result["answer"])
```

---

## Best Practices

### 1. Error Handling
```python
try:
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    result = response.json()
except requests.exceptions.Timeout:
    print("Request timed out")
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 429:
        print("Rate limit exceeded, wait 1 minute")
    else:
        print(f"HTTP error: {e}")
except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
```

### 2. Retry Logic
```python
import time

def chat_with_retry(question, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json={"question": question})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                wait_time = 60  # Rate limit
                time.sleep(wait_time)
            elif attempt == max_retries - 1:
                raise
            else:
                time.sleep(2 ** attempt)  # Exponential backoff
```

### 3. Batch Processing
```python
questions = [
    "SSH nedir?",
    "Firewall nasıl yapılandırılır?",
    "CIS Benchmark nedir?"
]

results = []
for q in questions:
    result = client.chat(q)
    results.append(result)
    time.sleep(0.6)  # Rate limit: 100/min = 1 request per 0.6s
```

---

## Sonraki Adımlar

- 📖 [Teknolojiler](05_TEKNOLOJILER.md) - Kullanılan teknolojiler
- 📖 [LLM Uygulamaları](06_LLM_UYGULAMALARI.md) - ML ve LLM detayları
