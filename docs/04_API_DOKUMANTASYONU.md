# API Dokümantasyonu

## Genel Bilgiler

**Base URL**: `http://localhost:8000`
**API Version**: v1
**Protocol**: HTTP/HTTPS
**Format**: JSON

**Swagger UI**: http://localhost:8000/docs
**ReDoc**: http://localhost:8000/redoc

---

## Authentication (Kimlik Doğrulama)

### Mevcut Durum: Authentication YOK ⚠️

Şu anda sistem **authentication gerektirmez**. Bu bir **prototip/development** özelliğidir.

### Ne İşe Yarar?

API Authentication (Kimlik Doğrulama):
1. ✅ **Kimlik Tespiti**: Kim API'yi kullanıyor?
2. ✅ **Yetkilendirme**: Bu kullanıcının bu işlemi yapma yetkisi var mı?
3. ✅ **Güvenlik**: Yetkisiz erişimi engeller
4. ✅ **Rate Limiting**: Kullanıcı bazlı kota kontrolü
5. ✅ **Audit/Logging**: Kim ne zaman ne yaptı?
6. ✅ **Maliyet Kontrolü**: Kullanıcı başına LLM API cost tracking

### Kim Kullanır?

**Kimlik doğrulama OLMADAN (şu anki durum):**
- ❌ Herhangi biri API'yi kullanabilir (public access)
- ❌ Kullanıcı takibi yapılamaz
- ❌ Rate limit sadece IP bazlı (kolayca bypass edilir)
- ❌ Abuse riski yüksek

**Kimlik doğrulama ile (production):**
- ✅ Sadece API key sahibi kullanıcılar erişebilir
- ✅ Kullanıcı bazlı tracking
- ✅ Kullanıcı başına rate limit
- ✅ Abuse önlenir

### Nasıl Kullanılır? (Production - Gelecek Özellik)

**Örnek Implementation (FastAPI):**

```python
# api/auth.py
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    API key doğrulama

    Headers'dan: Authorization: Bearer YOUR_API_KEY
    """
    api_key = credentials.credentials

    # Database check (örnek)
    user = db.get_user_by_api_key(api_key)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Rate limit check (user-based)
    if user.requests_today > user.quota:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quota exceeded"
        )

    return user

# Usage in endpoint
@router.post("/chat")
async def chat(
    payload: ChatRequest,
    user: User = Depends(verify_api_key)  # Auth required!
):
    # user.id, user.email, user.quota available
    ...
```

**Frontend Kullanımı (React Example):**

```typescript
// WITH Authentication (production)
const API_KEY = process.env.REACT_APP_API_KEY; // .env dosyasından

const response = await axios.post(
  'https://api.example.com/api/chat',
  {
    question: "Ubuntu SSH hardening",
    os: "ubuntu_24_04"
  },
  {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${API_KEY}`  // API key header
    }
  }
);
```

**cURL Kullanımı (Terminal):**

```bash
# WITH Authentication
curl -X POST https://api.example.com/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "question": "SSH nedir?"
  }'
```

### Kullanmazsa Ne Olur?

**Production'da Authentication OLMADAN:**
1. ❌ **Güvenlik Açığı**: Herkes sınırsız API kullanabilir
2. ❌ **Maliyet Sorunu**: Groq ücretsiz ama OpenAI fallback maliyetli olabilir
3. ❌ **Abuse**: Botlar sistemi spam'leyebilir
4. ❌ **DoS Riski**: Rate limit sadece IP bazlı (VPN ile bypass)
5. ❌ **Compliance**: GDPR/SOC2 için user tracking gerekli

**Prototype/Development'da (şu anki durum):**
- ✅ Hızlı test edilebilir
- ✅ Frontend integration kolay
- ✅ Demo/PoC için yeterli
- ⚠️ **Production'a geçerken mutlaka eklenmelidir!**

### Kullanıcı Nasıl Etkilenir?

| Senaryo | Auth YOK (şimdi) | Auth VAR (production) |
|---------|------------------|----------------------|
| **İlk Kullanım** | Hemen başlayabilir | API key alması gerekir (signup) |
| **API Call** | Direkt POST | Header'da Bearer token gerekir |
| **Rate Limit** | IP bazlı (100/min) | Kullanıcı bazlı (1000/day gibi) |
| **Hata Durumu** | Generic error | "Invalid API key" veya "Quota exceeded" |
| **Maliyet** | Yok (free tier) | Kullanıcı bazlı pricing olabilir |

### Frontend Yazarken Ara Bağlantı Nasıl Etkilenir?

**ŞU ANKİ DURUM (Auth yok):**
```typescript
// React component - Basit
const sendMessage = async () => {
  const response = await axios.post('/api/chat', {
    question: userInput
  });
  // Başarılı!
};
```

**PRODUCTION (Auth var):**
```typescript
// React component - API key management gerekli
const API_KEY = process.env.REACT_APP_API_KEY;

// 1. API key validation on app load
useEffect(() => {
  if (!API_KEY) {
    setError('API key not configured!');
  }
}, []);

// 2. API call with auth header
const sendMessage = async () => {
  try {
    const response = await axios.post('/api/chat',
      { question: userInput },
      {
        headers: {
          'Authorization': `Bearer ${API_KEY}`
        }
      }
    );
  } catch (error) {
    if (error.response?.status === 401) {
      setError('Invalid API key. Please check your credentials.');
    } else if (error.response?.status === 429) {
      setError('Quota exceeded. Please upgrade your plan.');
    }
  }
};

// 3. API key input (user-facing)
// Kullanıcıdan API key isteme:
<input
  type="password"
  placeholder="Enter your API key"
  onChange={(e) => setApiKey(e.target.value)}
/>
```

### Production Deployment İçin Öneriler

1. **JWT-based Authentication**: Token expiry, refresh tokens
2. **OAuth2/OpenID Connect**: Google, GitHub login
3. **API Key Tiers**: Free (1000/day), Pro (unlimited)
4. **Rate Limiting**: User-based quotas
5. **Audit Logging**: User activity tracking
6. **IP Whitelisting**: Ek güvenlik katmanı

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
| `use_rag` | boolean | ❌ Hayır | RAG kullan (akıllı RAG için `true`) | `true` |
| `rag_top_k` | integer | ❌ Hayır | RAG chunk sayısı (1-20) | `5` |
| `rag_min_score` | float | ❌ Hayır | Min relevance score (0.0-1.0) | `0.5` |
| `timeout` | integer | ❌ Hayır | Request timeout (1-300 saniye) | `60` |

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

---

### RAG Kullanımı ve Akıllı Tetikleme

#### `use_rag` Parametresi Nasıl Çalışır?

Sistem **kullanıcı fark etmeden** soruyu analiz edip RAG'in gerekli olup olmadığına otomatik karar verir.

**Kullanıcı Kontrolü:**
```json
{
  "question": "SSH nedir?",
  "use_rag": true   // Kullanıcı RAG istiyor
}
```

**Sistem Kararı (Otomatik):**
```python
# Backend: llm/pipelines/layers/info_pipeline.py:199
def _should_use_rag(question, complexity):
    """
    Akıllı RAG tetikleme kararı
    """
    # Adım 1: Generic pattern kontrolü
    if "nedir" in question or "what is" in question:
        # Generic definition sorusu → RAG SKIP
        return False

    # Adım 2: Specific indicator kontrolü
    if "ubuntu" in question or "22.04" in question or "cis" in question:
        # OS/Version-specific → RAG USE
        return True

    # Adım 3: Complexity check
    if complexity == "complex":
        return True  # Complex queries benefit from RAG

    # Default: Simple generic queries skip RAG
    return False
```

#### Hangi Adımlar Bu Parametreleri Güncelliyor?

**Pipeline Akışı:**

**1. API Layer (router_chat.py:66)**
```python
# Kullanıcıdan gelen parametre
use_rag: bool = Field(True, description="RAG kullanılsın mı")
# Default: True (kullanıcı istiyor)
```

**2. Info Pipeline - Question Analysis (info_pipeline.py:120)**
```python
# Complexity analizi
complexity = analyze_complexity(ctx.user_question)
# Returns: "simple" | "medium" | "complex"

# Örnek:
# "SSH nedir?" → "simple"
# "Ubuntu 22.04 SSH ayarları" → "medium"
# "CIS Benchmark section 5.2.3 detaylı açıkla" → "complex"
```

**3. Info Pipeline - Smart RAG Decision (info_pipeline.py:124)**
```python
# FINAL DECISION: Sistem kararı (kullanıcı isteği override edilebilir)
use_rag_final = self._should_use_rag(ctx.user_question, complexity)

# Örnekler:
# User: use_rag=true, Question: "SSH nedir?"
#   → Final: False (generic, RAG gereksiz)
#
# User: use_rag=true, Question: "Ubuntu 22.04 SSH hardening"
#   → Final: True (specific, RAG gerekli)
#
# User: use_rag=false
#   → Final: False (kullanıcı istememiş, respect user choice)
```

**4. RAG Retrieval (info_pipeline.py:132)**
```python
if use_rag_final and self.rag_builder:
    # RAG retrieval yap
    rag_results = self.rag_builder.search(
        query=ctx.user_question,
        top_k=ctx.rag_top_k,  # Default: 5
        min_score=ctx.rag_min_score  # Default: 0.7
    )
    # Returns: [chunk1, chunk2, ...] with scores
```

#### Hangi Parametreler Var?

| Parametre | Nereden Gelir | Kim Günceller | Varsayılan | Amaç |
|-----------|---------------|---------------|------------|------|
| `use_rag` | User API request | API Layer | `true` | Kullanıcı RAG tercihi |
| `rag_top_k` | User API request | API Layer | `5` | Kaç chunk çekilsin |
| `rag_min_score` | User API request | API Layer | `0.7` | Min similarity threshold |
| `complexity` | System | Info Pipeline | auto | Soru karmaşıklığı |
| `use_rag_final` | System | Info Pipeline | auto | Final RAG kararı |
| `rag_chunks_retrieved` | System | RAG Builder | auto | Gerçekte kaç chunk bulundu |

#### Örnek Senaryolar

**Senaryo 1: Generic Definition (RAG Skip)**
```json
// REQUEST
{
  "question": "SSH nedir ve nasıl çalışır?",
  "use_rag": true  // User wants RAG
}

// INTERNAL PROCESSING
{
  "complexity": "simple",
  "has_generic_pattern": true,  // "nedir" detected
  "has_specific_indicator": false,  // No OS/version mentioned
  "use_rag_final": false  // ❌ RAG SKIPPED (smart decision)
}

// RESPONSE
{
  "answer": "SSH (Secure Shell) güvenli bir ağ protokolüdür...",
  "rag_sources": [],  // Empty - RAG not used
  "stats": {
    "total_time_s": 0.85,  // FAST (no RAG retrieval)
    "layer_path": "1->2->3B"
  }
}
```

**Senaryo 2: Specific Query (RAG Used)**
```json
// REQUEST
{
  "question": "Ubuntu 22.04 için SSH hardening CIS benchmark önerileri",
  "use_rag": true
}

// INTERNAL PROCESSING
{
  "complexity": "medium",
  "has_generic_pattern": false,
  "has_specific_indicator": true,  // "ubuntu 22.04", "cis benchmark"
  "use_rag_final": true  // ✅ RAG USED
}

// RESPONSE
{
  "answer": "CIS Ubuntu 22.04 Benchmark'e göre SSH hardening:\n...",
  "rag_sources": [
    {
      "score": 0.91,
      "section": "5.2.3 Ensure SSH access is limited",
      "source": "CIS_Ubuntu_22.04_Benchmark_v2.0.0"
    }
  ],
  "stats": {
    "total_time_s": 2.31,  // Slower (RAG retrieval included)
    "layer_path": "1->2->3B->4"
  }
}
```

**Senaryo 3: User Explicitly Disables RAG**
```json
// REQUEST
{
  "question": "Ubuntu 22.04 SSH hardening",  // Specific query
  "use_rag": false  // User explicitly disables
}

// INTERNAL PROCESSING
{
  "use_rag_final": false  // ❌ User choice respected
}

// RESPONSE
{
  "answer": "SSH hardening için genel öneriler:\n...",  // Generic answer
  "rag_sources": [],  // No CIS Benchmark data
  "stats": {
    "total_time_s": 1.02  // Fast but less accurate
  }
}
```

#### Performans Karşılaştırması

| Soru Tipi | User: use_rag | Final RAG | Süre | Doğruluk | Maliyet |
|-----------|---------------|-----------|------|----------|---------|
| "SSH nedir?" | `true` | `false` | 0.9s | %94 | $0.0008 |
| "SSH nedir?" | `false` | `false` | 0.9s | %94 | $0.0008 |
| "Ubuntu 22.04 SSH" | `true` | `true` | 2.3s | %96 | $0.0012 |
| "Ubuntu 22.04 SSH" | `false` | `false` | 1.1s | %89 | $0.0008 |

**Sonuç**: Akıllı RAG %55 sorgu için RAG'i skip eder → %56 hız artışı, %1 doğruluk kaybı

#### Response

**Status Code**: `200 OK`

**Body (JSON):**
```json
{
  "answer": "Ubuntu 24.04 için SSH hardening scripti:\n\n#!/bin/bash\n# SSH Hardening Script\n...",
  "intent": "action_request",
  "safety_category": "safe_defensive",
  "layer_path": "1→2→3C",
  "rag_sources": [
    {
      "id": "source_1",
      "score": 0.89,
      "source": "CIS Ubuntu Linux 24.04 LTS Benchmark",
      "section": "5.2.3 Ensure SSH access is limited",
      "text": "SSH configuration best practices include..."
    },
    {
      "id": "source_2",
      "score": 0.85,
      "source": "CIS Ubuntu Linux 24.04 LTS Benchmark",
      "section": "5.2.4 Ensure SSH root login is disabled",
      "text": "PermitRootLogin no should be set..."
    }
  ],
  "stats": {
    "total_time_s": 3.21,
    "layer_path": "1→2→3C",
    "rag_used": true,
    "rag_chunks": 6,
    "model": "llama-3.3-70b-versatile",
    "complexity": "complex"
  },
  "request_id": "req_1701234567890_abc123",
  "estimated_cost": 0.0018,
  "verification_confidence": 0.91
}
```

#### Response Alanları

| Alan | Tip | Açıklama |
|------|-----|----------|
| `answer` | string | LLM'den gelen yanıt |
| `intent` | string \| null | Intent tipi: `smalltalk_greeting`, `smalltalk_farewell`, `smalltalk_other`, `os_hardening`, `script_or_config`, `conceptual_explanation`, `incident_analysis`, `generic_qna` |
| `safety_category` | string \| null | Güvenlik kategorisi (safe_defensive, safe_educational, ambiguous, unsafe_offensive) |
| `layer_path` | string \| null | Pipeline path (1→2→3A, 1→2→3B, 1→2→3C, 1→REJECT, vb.) |
| `rag_sources` | array | RAG'den gelen kaynaklar — her eleman: `id`, `score`, `source`, `section`, `text` |
| `stats` | object | Performans istatistikleri |
| `stats.total_time_s` | float | Toplam süre (saniye) |
| `stats.rag_used` | bool | RAG kullanıldı mı |
| `stats.rag_chunks` | int | Kullanılan chunk sayısı |
| `stats.model` | string \| null | Kullanılan LLM modeli |
| `stats.complexity` | string \| null | Soru karmaşıklığı (simple / medium / complex) |
| `request_id` | string \| null | Unique request ID (loglama için) |
| `estimated_cost` | float \| null | Tahmini maliyet (USD) |
| `verification_confidence` | float \| null | Claim verification güven skoru (0-1). Enhanced RAG etkinse dolar. |

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
  "intent": "conceptual_explanation",
  "safety_category": "safe_educational",
  "layer_path": "1→2→3B",
  "rag_sources": [],
  "stats": {
    "total_time_s": 2.1,
    "rag_used": false,
    "rag_chunks": 0,
    "model": "llama-3.1-8b-instant",
    "complexity": "simple"
  },
  "estimated_cost": 0.0012,
  "verification_confidence": null
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
  "intent": "script_or_config",
  "safety_category": "safe_defensive",
  "layer_path": "1→2→3C",
  "rag_sources": [
    {
      "id": "source_1",
      "score": 0.91,
      "source": "CIS Ubuntu Linux 24.04 LTS Benchmark",
      "section": "5.2 SSH Server Configuration",
      "text": "..."
    }
  ],
  "stats": {
    "total_time_s": 3.8,
    "rag_used": true,
    "rag_chunks": 6,
    "model": "llama-3.3-70b-versatile",
    "complexity": "complex"
  },
  "estimated_cost": 0.0021,
  "verification_confidence": 0.88
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
