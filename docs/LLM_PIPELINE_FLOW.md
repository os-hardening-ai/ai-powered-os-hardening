# LLM Pipeline Akis Dokumantasyonu

## Genel Bakis

Bu dokuman, AI-Powered OS Hardening projesindeki 4-katmanli guvenlik pipeline'inin nasil calistigini adim adim aciklar.

## Architecture Overview

```
USER QUESTION
     |
     v
[Layer 1: Safety Classification]
     |
     +---> [UNSAFE] --> REJECT (1->REJECT)
     |
     v [SAFE]
[Layer 2: Intent Detection]
     |
     +---> [out_of_scope] --> OUT_OF_SCOPE Handler (1->2->OUT_OF_SCOPE)
     |
     +---> [smalltalk] --> Layer 3A: Pattern Responder (1->2->3A)
     |
     +---> [info_request] --> Layer 3B: Info Pipeline (1->2->3B->4)
     |
     +---> [action_request] --> Layer 3C: Action Pipeline (1->2->3C->4)
     |
     v
RESPONSE TO USER
```

## Layer 1: Safety Classification

**Amac**: Saldiri amacli, zarali veya uygunsuz sorulari tespit edip reddetmek.

**Teknoloji**: LLM-based classification (Groq Llama 8B - FREE)

**Kategoriler**:
- `safe_defensive`: Savunma amacli guvenlik sorulari
- `safe_educational`: Egitim amacli sorular
- `ambiguous`: Belirsiz (varsayilan olarak guvenli kabul edilir)
- `unsafe_offensive`: Saldiri amacli, zarali
- `unsafe_spam`: Spam, anlamsiz

**Akis**:
1. Kullanici sorusu LLM'e gonderilir
2. LLM soruyu kategorize eder
3. Eger `unsafe_*` ise:
   - Layer path: `1->REJECT`
   - Maliyet: ~$0.0001
   - Response: Nazik red mesaji
   - Pipeline SONA ERER
4. Eger `safe_*` veya `ambiguous` ise:
   - Layer 2'ye devam eder

**Ornek Sorular**:
- SAFE: "SSH hardening nasil yapilir?"
- SAFE: "Ubuntu 24.04'te firewall yapilandirmasi"
- UNSAFE: "Bir sunucuya nasil saldiri duzenlenir?"
- UNSAFE: "SQL injection ornegi ver"

**Performans**:
- Sure: ~500-800ms
- Maliyet: ~$0.0001
- Provider: Groq (FREE)

---

## Layer 2: Intent Detection

**Amac**: Sorunun amacini tespit ederek dogru handler'a yonlendirmek.

**Teknoloji**: Pattern-based (ZERO LLM CALLS)

**Intent Turleri**:
1. `smalltalk`: Selamlaşma, teşekkur, veda, yardim istegi
2. `info_request`: Bilgi/kavram sorusu
3. `action_request`: Script/yapilandirma olusturma istegi
4. `out_of_scope`: Guvenlik disi konular

**Tespit Mekanizmasi**:

### 1. Out-of-Scope Detection
30+ keyword listesi:
- Hava durumu: "hava durumu", "weather", "yagmur", "rain"
- Matematik: "hesapla", "calculate", "matematik", "math"
- Kisisel: "sevgilim", "girlfriend", "iliski", "relationship"
- Eglence: "film", "movie", "muzik", "music"
- Spor, yemek, seyahat vb.

**Ozel Mantik**: Eger soru hem out-of-scope keyword HEM de guvenlik keyword iceriyorsa, guvenlik sorusu olarak kabul edilir (false positive onleme).

### 2. Smalltalk Detection
Patterns:
- Greeting: "merhaba", "selam", "hello", "hi"
- Farewell: "gorusuruz", "bye", "goodbye"
- Thanks: "tesekkur", "thank", "sagol"
- Help: "yardim", "help", "nasil kullanilir"

### 3. Action Request Detection
Keywords:
- "script", "config", "yapilandirma", "dosya olustur"
- "generate", "create", "build"
- OS keywords: "ubuntu", "centos", "windows"

### 4. Info Request (Default)
Eger yukaridaki hicbiri degilse, `info_request` olarak kabul edilir.

**Akis**:
1. Soru kucuk harfe cevrilir
2. Out-of-scope keywords kontrol edilir
   - Match varsa VE guvenlik keyword yoksa: `out_of_scope`
3. Smalltalk patterns kontrol edilir
   - Match varsa: `smalltalk`
4. Action keywords kontrol edilir
   - Match varsa: `action_request`
5. Default: `info_request`

**Performans**:
- Sure: <1ms (pattern matching)
- Maliyet: $0
- Provider: N/A (regex/keyword based)

---

## Layer 3A: Pattern Responder (Smalltalk Handler)

**Amac**: Basit selamlaşma/tesekkur gibi sorular icin aninda cevap vermek.

**Teknoloji**: Pattern matching (ZERO LLM CALLS)

**Kategoriler**:
- Greeting: "Merhaba! Size guvenlik ve OS hardening konularinda yardimci olabilirim."
- Farewell: "Gorusuruz! Guvenli kalmaya devam edin."
- Thanks: "Rica ederim! Basarili bir sistem sikilaştirmasi dilerim."
- Help: "Ben bir OS hardening asistaniyim. CIS Benchmarks, SSH/RDP hardening, Zero Trust gibi konularda yardimci olabilirim."

**Akis**:
1. Soru pattern matcher'a gonderilir
2. Eslesen pattern bulunursa:
   - Onceden tanimli response dondurulur
   - Layer path: `1->2->3A`
   - Maliyet: $0.0001 (sadece safety check)
3. Pattern eslemezse (fallback):
   - Layer 3B'ye (Info Pipeline) yonlendirilir

**Performans**:
- Sure: <5ms
- Maliyet: $0.0001
- Provider: N/A

**Ornek Sorular**:
- "Merhaba"
- "Tesekkur ederim"
- "Nasil kullanilir?"
- "Gorusuruz"

---

## Layer 3B: Info Pipeline (Bilgi Sorulari)

**Amac**: Guvenlik kavramlari ve best practice sorularina cevap vermek.

**Teknoloji**: Smart RAG + Complexity-based model selection

**Akis**:

### 1. Kompleksite Analizi
Soru karmasikligina gore 5 seviye:
- `LOCAL`: Cok basit (model gereksiz)
- `FAST`: Basit, kisa cevap
- `SIMPLE`: Orta basitlikte
- `MEDIUM`: Orta-zor, detayli
- `COMPLEX`: Cok zor, cok adimli reasoning

**Kompleksite Faktörleri**:
- Soru uzunlugu (token sayisi)
- Teknik keyword yogunlugu
- Multi-step reasoning gerektirme
- OS-spesifik detay gerektirme

### 2. RAG Trigger Karar
**Smart RAG Logic**:
- Generic sorular: RAG SKIP (ornek: "SSH nedir?", "CIS ne demek?")
- Spesifik sorular: RAG USE (ornek: "Ubuntu 24.04 SSH port degistirme", "CIS Benchmark 5.2.3 ne diyor?")

**RAG Kullanim Kriterleri**:
- OS versiyon iceriyor mu?
- Spesifik CIS Benchmark referansi var mi?
- Yapilandirma detayi soruluyor mu?

### 3. Model Secimi
Kompleksiteye gore:
- `LOCAL`: Pattern-based response (LLM yok)
- `FAST`: Groq Llama 8B (~$0.0001)
- `SIMPLE`: Groq Llama 8B (~$0.0002)
- `MEDIUM`: GPT-4o-mini (~$0.001)
- `COMPLEX`: GPT-4o (~$0.015) + Chain-of-Thought

### 4. Prompt Yapisi
```
ROLE: Siber guvenlik ve OS hardening uzmani

CONTEXT:
[RAG'den gelen CIS Benchmark chunks - eger varsa]

USER METADATA:
- OS: ubuntu_24_04
- Role: sysadmin
- Security Level: balanced
- ZT Maturity: medium

QUESTION: {user_question}

INSTRUCTIONS:
- Turkce cevap ver
- CIS Benchmarks'e atif yap
- Adim adim acikla
- Orneklerle destekle
```

**Performans**:
- Sure: 1-4 saniye (RAG + LLM)
- Maliyet: $0.0001 - $0.015
- Provider: Groq / OpenAI

**Ornek Sorular**:
- "SSH hardening best practices?" (SIMPLE, RAG YES)
- "Zero Trust nedir?" (FAST, RAG NO)
- "Ubuntu 24.04'te cramfs nasil devre disi birakilir?" (MEDIUM, RAG YES)
- "CIS Benchmark 1.1.1.1 ne diyor?" (FAST, RAG YES)

---

## Layer 3C: Action Pipeline (Script Olusturma)

**Amac**: Guvenlik yapilandirmalari ve scriptler olusturmak.

**Teknoloji**: Metadata validation + LLM + Strict output validation

**Akis**:

### 1. Parameter Inference
Kullanici sorusundan otomatik olarak cikarilir:
- `os`: "ubuntu 22.04", "centos 9", "windows server 2022"
- `role`: "sysadmin", "soc", "developer"
- `security_level`: "minimal", "balanced", "strict"

**Inference Ornekleri**:
- "Ubuntu 22.04 SSH hardening" → os=ubuntu_22_04
- "Windows Server firewall kuralları" → os=windows_server_2022
- "strict güvenlik seviyesi" → security_level=strict

### 2. Metadata Validation
**Required Parameters**:
- `os`: ZORUNLU (script OS-specific olmalidir)
- `security_level`: Optional (default: balanced)
- `role`: Optional (default: sysadmin)

**Validation Logic**:
```python
if os is None:
    return "Lutfen isletim sistemi belirtin (ornek: Ubuntu 22.04, CentOS 9)"
```

### 3. Script Generation
**LLM Model**: GPT-4o-mini (dengeli maliyet/kalite)

**Prompt Yapisi**:
```
ROLE: OS hardening script generator

TARGET SYSTEM:
- OS: {os}
- Role: {role}
- Security Level: {security_level}

TASK: {user_request}

REQUIREMENTS:
1. Executable script (bash/powershell)
2. CIS Benchmark aligned
3. Idempotent (calistirilabilir tekrar)
4. Hata kontrolu (error handling)
5. Rollback mekanizmasi
6. Commented (aciklamali)

OUTPUT FORMAT:
1. Script tanimi
2. Kod blogu (```bash veya ```powershell)
3. Kullanim talimatlari
4. Risk uyarilari
```

### 4. Output Validation
Script olusturulduktan sonra:
- Code block var mi? (```bash veya ```powershell)
- Minimum 10 satir mi?
- Tehlikeli komutlar var mi? (rm -rf /, format C:)
- Syntax hatalari var mi?

**Performans**:
- Sure: 2-5 saniye
- Maliyet: ~$0.002-0.005
- Provider: OpenAI GPT-4o-mini

**Ornek Sorular**:
- "Ubuntu 22.04 icin SSH hardening scripti olustur"
- "Windows Server 2022 firewall yapilandirmasi yap"
- "CentOS 9 user account hardening"

---

## OUT_OF_SCOPE Handler

**Amac**: Guvenlik disi konulari nazikce reddetmek.

**Teknoloji**: Pattern matching (ZERO LLM CALLS)

**Response Template**:
```
KAPSAMDISI SORU

Ben sadece siber guvenlik ve isletim sistemi sikilaştirma (OS hardening) konularinda yardimci olabiliyorum.

Size yardimci olabilecegim konular:
- SSH, RDP, Firewall hardening
- CIS Benchmarks ve NIST 800-207 uygulamalari
- Zero Trust Architecture
- Guvenlik yapilandirmalari ve scriptleri
- Vulnerability assessment ve risk azaltma

Lutfen guvenlik veya sistem sikilaştirma ile ilgili bir soru sorun.
```

**Performans**:
- Sure: <1ms
- Maliyet: $0.0001 (sadece safety check)
- Provider: N/A

**Ornek Sorular**:
- "Hava durumu nasil?"
- "En iyi pizza tarifi"
- "Matematik hesaplama yap"

---

## Complete Flow Examples

### Example 1: Basit Selamlaşma
```
USER: "Merhaba"
  |
  v
Layer 1: Safety Classification
  -> Category: safe_defensive
  -> Is Safe: YES
  |
  v
Layer 2: Intent Detection
  -> Pattern match: "merhaba" -> smalltalk
  -> Intent: smalltalk (greeting)
  |
  v
Layer 3A: Pattern Responder
  -> Match category: greeting
  -> Response: "Merhaba! Size guvenlik ve OS hardening konularinda yardimci olabilirim."
  |
  v
RESULT:
  - Layer Path: 1->2->3A
  - Time: ~800ms (safety) + 5ms (pattern)
  - Cost: $0.0001
  - Answer: Pre-defined greeting
```

### Example 2: Kapsam Disi Soru
```
USER: "Bugun hava nasil?"
  |
  v
Layer 1: Safety Classification
  -> Category: safe_educational
  -> Is Safe: YES
  |
  v
Layer 2: Intent Detection
  -> Out-of-scope keyword match: "hava"
  -> Security keyword check: NO security keywords
  -> Intent: out_of_scope
  |
  v
OUT_OF_SCOPE Handler
  -> Response: Polite rejection with examples
  |
  v
RESULT:
  - Layer Path: 1->2->OUT_OF_SCOPE
  - Time: ~800ms
  - Cost: $0.0001
  - Answer: Out-of-scope rejection
```

### Example 3: Basit Bilgi Sorusu (Generic)
```
USER: "SSH nedir?"
  |
  v
Layer 1: Safety Classification
  -> Category: safe_educational
  -> Is Safe: YES
  |
  v
Layer 2: Intent Detection
  -> No smalltalk/action/out-of-scope match
  -> Intent: info_request
  |
  v
Layer 3B: Info Pipeline
  |
  +-> Complexity Analysis
      -> Length: short
      -> Keywords: few
      -> Multi-step: NO
      -> Complexity: FAST
  |
  +-> RAG Decision
      -> Generic question: YES
      -> RAG needed: NO
  |
  +-> Model Selection
      -> Complexity: FAST
      -> Model: Groq Llama 8B
  |
  +-> Generation
      -> Prompt: Basic SSH definition
      -> LLM call: Groq Llama 8B
  |
  v
RESULT:
  - Layer Path: 1->2->3B
  - Time: ~1.5s
  - Cost: $0.0002
  - Answer: SSH definition
```

### Example 4: Detayli OS-Spesifik Soru (RAG Gerekli)
```
USER: "Ubuntu 24.04'te SSH port nasil degistirilir?"
  |
  v
Layer 1: Safety Classification
  -> Category: safe_defensive
  -> Is Safe: YES
  |
  v
Layer 2: Intent Detection
  -> No smalltalk/action/out-of-scope match
  -> Intent: info_request
  |
  v
Layer 3B: Info Pipeline
  |
  +-> Complexity Analysis
      -> Length: medium
      -> Keywords: "ubuntu 24.04", "SSH", "port"
      -> OS-specific: YES
      -> Complexity: MEDIUM
  |
  +-> RAG Decision
      -> OS version: ubuntu_24_04
      -> Specific config: port change
      -> RAG needed: YES
  |
  +-> RAG Retrieval
      -> Query: "SSH port configuration Ubuntu 24.04"
      -> Top-K: 5 chunks
      -> Min Score: 0.7
      -> Sources: CIS_Ubuntu_24.04_Benchmark
  |
  +-> Model Selection
      -> Complexity: MEDIUM
      -> Model: GPT-4o-mini
  |
  +-> Generation
      -> Prompt: RAG context + user question
      -> LLM call: GPT-4o-mini
  |
  v
RESULT:
  - Layer Path: 1->2->3B->4
  - Time: ~3s (RAG: 500ms, LLM: 2.5s)
  - Cost: $0.0015
  - Answer: Detailed SSH port change guide with CIS references
  - RAG Sources: [CIS_Ubuntu_24.04 Section 5.2.x]
```

### Example 5: Script Olusturma (Eksik Parametre)
```
USER: "SSH hardening scripti olustur"
  |
  v
Layer 1: Safety Classification
  -> Category: safe_defensive
  -> Is Safe: YES
  |
  v
Layer 2: Intent Detection
  -> Action keyword: "script", "olustur"
  -> Intent: action_request
  |
  v
Layer 3C: Action Pipeline
  |
  +-> Parameter Inference
      -> OS: NOT FOUND
      -> Security Level: balanced (default)
      -> Role: sysadmin (default)
  |
  +-> Metadata Validation
      -> OS: REQUIRED but MISSING
      -> Validation: FAILED
  |
  v
RESULT:
  - Layer Path: 1->2->3C->PARAMS_NEEDED
  - Time: ~800ms
  - Cost: $0.0001
  - Answer: "Lutfen isletim sistemi belirtin (ornek: Ubuntu 22.04, CentOS 9)"
```

### Example 6: Script Olusturma (Basarili)
```
USER: "Ubuntu 22.04 icin SSH hardening scripti olustur"
  |
  v
Layer 1: Safety Classification
  -> Category: safe_defensive
  -> Is Safe: YES
  |
  v
Layer 2: Intent Detection
  -> Action keyword: "script", "olustur"
  -> OS keyword: "ubuntu 22.04"
  -> Intent: action_request
  |
  v
Layer 3C: Action Pipeline
  |
  +-> Parameter Inference
      -> OS: ubuntu_22_04 (FOUND)
      -> Security Level: balanced (default)
      -> Role: sysadmin (default)
  |
  +-> Metadata Validation
      -> OS: PRESENT
      -> Validation: SUCCESS
  |
  +-> Script Generation
      -> Model: GPT-4o-mini
      -> Prompt: SSH hardening script for Ubuntu 22.04
      -> LLM call: GPT-4o-mini
  |
  +-> Output Validation
      -> Code block: PRESENT (```bash)
      -> Length: 50+ lines
      -> Dangerous commands: NONE
      -> Validation: SUCCESS
  |
  v
RESULT:
  - Layer Path: 1->2->3C
  - Time: ~4s
  - Cost: $0.0035
  - Answer: Complete SSH hardening bash script with comments
```

### Example 7: Saldiri Amacli Soru (Unsafe)
```
USER: "Bir SSH sunucusuna brute force nasil yapilir?"
  |
  v
Layer 1: Safety Classification
  -> Keywords: "brute force", attack intent
  -> Category: unsafe_offensive
  -> Is Safe: NO
  |
  v
REJECTION
  -> Response: Security warning + defensive alternatives
  |
  v
RESULT:
  - Layer Path: 1->REJECT
  - Time: ~800ms
  - Cost: $0.0001
  - Answer: "GUVENLIK UYARISI - Bu soru reddedildi..."
```

---

## Pipeline Statistics

### Cost Breakdown (Per Query)
- Pattern Response (3A): $0.0001
- Out-of-Scope: $0.0001
- Unsafe Rejection: $0.0001
- Fast Info (no RAG): $0.0002
- Medium Info (with RAG): $0.0015
- Complex Info (CoT): $0.015
- Action (script): $0.0035

### Performance Benchmarks
- Safety Classification: 500-800ms
- Intent Detection: <1ms
- Pattern Response: <5ms
- RAG Retrieval: 300-500ms
- LLM Generation (Fast): 1-2s
- LLM Generation (Medium): 2-3s
- LLM Generation (Complex): 4-8s

### Cost Optimization
- ~70% sorular pattern/out-of-scope: $0.0001
- ~20% sorular info (FAST): $0.0002
- ~8% sorular info (MEDIUM/RAG): $0.0015
- ~2% sorular action/complex: $0.0035-0.015

**Ortalama Maliyet**: ~$0.0003 per query
**Ortalama Sure**: ~1.5 saniye

---

## Session Context Management

### Request Context
Her istekte saklanan bilgiler:
```python
RequestContext:
  - request_id: Unique ID
  - user_question: Original soru
  - os: Isletim sistemi (inferred or explicit)
  - role: Kullanici rolu (inferred or explicit)
  - security_level: Guvenlik seviyesi (default: balanced)
  - zt_maturity: Zero Trust maturity (default: medium)
  - session_id: Oturum ID (opsiyonel)
  - conversation_history: Onceki sorular (opsiyonel)
```

### Parameter Persistence
Bir kez cikarilmis parametreler session boyunca korunur:
```
USER 1: "Ubuntu 22.04 icin SSH hardening"
  -> os=ubuntu_22_04 (saved to session)

USER 2: "Firewall yapilandirmasi nasil yapilir?"
  -> os=ubuntu_22_04 (reused from session)
```

---

## Error Handling

### LLM API Hatasi
```python
try:
    result = llm_call(prompt)
except Exception as e:
    # Fallback to simpler model
    result = fallback_llm_call(prompt)
```

### RAG Retrieval Hatasi
```python
try:
    chunks = rag_retriever.search(query)
except Exception as e:
    # Continue without RAG
    chunks = []
```

### Timeout Handling
- LLM timeout: 30 saniye
- RAG timeout: 5 saniye
- Total pipeline timeout: 45 saniye

---

## Security Best Practices

### Input Sanitization
- Max length: 5000 characters
- Empty input check
- Injection pattern detection (basic)

### Output Sanitization
- LLM prompt leakage filtering
- System instruction removal
- Sensitive data masking

### Rate Limiting
- 100 requests/minute per IP
- 5 minute ban for violations

### Audit Logging
Her istek loglaniir:
- Timestamp
- Request ID
- User question (sanitized)
- Layer path
- Safety category
- Cost
- Response time

---

## Monitoring and Metrics

### Real-time Metrics
- Total queries
- Rejection rate (unsafe)
- Layer distribution (3A/3B/3C/OUT_OF_SCOPE)
- Average cost per query
- Average response time
- P50/P95/P99 latency

### Error Tracking
- LLM API errors
- RAG retrieval errors
- Timeout errors
- Validation errors

### Endpoint
```bash
GET /metrics
{
  "total_queries": 1000,
  "rejected_unsafe": 50,
  "pattern_responses": 300,
  "info_responses": 500,
  "action_responses": 100,
  "out_of_scope": 50,
  "avg_cost": 0.0003,
  "avg_time_s": 1.5
}
```

---

## Conclusion

Bu 4-katmanli pipeline, guvenlik ve maliyet dengesini optimize ederek:

1. **Guvenlik**: Unsafe sorular Layer 1'de durdurulur
2. **Verimlilik**: Basit sorular pattern matching ile aninda cevaplaniir
3. **Kapsam**: Out-of-scope sorular erkenden reddedilir
4. **Kalite**: Kompleks sorular uygun model + RAG ile cevaplaniir
5. **Maliyet**: Ortalama $0.0003/query ile cok dusuk maliyet

**Best Practice**:
- Layer 1 safety check HER ZAMAN yapilir
- Pattern matching LLM'den once denenir (cost optimization)
- RAG sadece spesifik sorular icin kullanilir (relevance optimization)
- Model secimi complexity-aware yapilir (quality/cost balance)
