# 🎯 PARAMETRE VE RAG STRATEJİSİ

## 1. PARAMETRE KULLANIM STRATEJİSİ

### ✅ **Önerilen Yaklaşım: Path-based Requirement**

Her path'in kendi parametre ihtiyacı var. Kullanıcıdan SADECE gerekli olanı iste.

---

### 📋 PATH BAZLI PARAMETRE İHTİYACI

#### **LOCAL PATH** (Pattern-based - LLM yok)
```
Gerekli Parametreler: YOK
Opsiyonel Parametreler: YOK

Neden: Önceden tanımlı cevaplar, context gerektirmez

Örnek:
Q: "merhaba"
A: "Merhaba! Size nasıl yardımcı olabilirim?"
→ Hiçbir parametre kullanılmadı
```

#### **FAST PATH** (Smalltalk)
```
Gerekli Parametreler: YOK
Opsiyonel Parametreler: YOK

Neden: Generic smalltalk, context gerektirmez

Örnek:
Q: "teşekkürler"
A: "Rica ederim! Başka sorunuz varsa sorabilirsiniz."
→ Hiçbir parametre kullanılmadı
```

#### **SIMPLE PATH** (Basit bilgi soruları)
```
Gerekli Parametreler: YOK
Opsiyonel Parametreler:
  - os (opsiyonel, eğer generic tanım soruluyorsa)

Neden: Basit tanımlar genellikle OS-agnostic

Örnek 1 - Generic:
Q: "Firewall nedir?"
A: "Firewall, ağ trafiğini kontrol eden güvenlik sistemidir..."
→ OS kullanılmadı (generic tanım)

Örnek 2 - OS-specific:
Q: "Ubuntu'da firewall nedir?"
Inferred: os=ubuntu_22_04
A: "Ubuntu'da firewall UFW (Uncomplicated Firewall) ile yönetilir..."
→ OS kullanıldı (sorudan çıkarıldı)

Strateji:
- Kullanıcı OS belirtmemişse: Generic cevap ver
- Kullanıcı OS belirtmişse (veya inference): OS-specific cevap ver
- ASLA kullanıcıya sorma (gereksiz)
```

#### **MEDIUM PATH** (Yapılandırma soruları)
```
Gerekli Parametreler:
  - os ✅ (çoğu konfigürasyon OS-specific)

Opsiyonel Parametreler:
  - role (cevap detayını etkileyebilir)
  - security_level (kuralların katılığı)

Strateji:
1. OS belirtilmemişse:
   a) Sorudan infer et (ParameterInferenceEngine)
   b) Inference başarısızsa → Kullanıcıya sor
   c) Soru ile yanıt ver

2. Role belirtilmemişse:
   → Default: sysadmin (sorma, gereksiz)

3. Security level belirtilmemişse:
   → Default: balanced (sorma, gereksiz)

Örnek 1 - Inference başarılı:
Q: "Ubuntu 22.04'te SSH nasıl yapılandırılır?"
Inferred: os=ubuntu_22_04, role=sysadmin (default), level=balanced (default)
→ Direkt cevap ver

Örnek 2 - Inference başarısız, OS gerekli:
Q: "SSH nasıl yapılandırılır?"
Inferred: os=None
→ Kullanıcıya sor: "Hangi işletim sistemi için? (Ubuntu / CentOS / Windows)"
User: "Ubuntu"
→ Devam et: os=ubuntu_22_04

Örnek 3 - Generic cevap verilebilir:
Q: "SSH port nasıl değiştirilir?"
Inferred: os=None
→ Generic cevap ver:
   "SSH port değiştirme:
    Linux: /etc/ssh/sshd_config → Port 2222
    Windows: Registry veya PowerShell

    Hangi OS için detaylı adımlar isterseniz belirtin."
```

#### **COMPLEX PATH** (Script/Hardening)
```
Gerekli Parametreler:
  - os ✅ (script OS-specific)
  - security_level ⚠️ (script içeriğini etkiler)

Opsiyonel Parametreler:
  - role (script detayını etkiler)
  - zt_maturity (ZT entegrasyonu)

Strateji:
1. OS belirtilmemişse:
   a) Sorudan infer et
   b) Başarısızsa → MUTLAKA sor (script için şart)

2. Security level belirtilmemişse:
   a) Sorudan infer et ("strict", "minimal" keywords)
   b) Başarısızsa → Sor veya default: balanced

3. Role belirtilmemişse:
   → Default: sysadmin (script use-case'e göre)

Örnek 1 - Tüm parametreler mevcut:
Q: "Ubuntu 22.04 için strict security level'da SSH hardening script yaz"
Inferred: os=ubuntu_22_04, level=strict
→ Direkt script üret

Örnek 2 - OS eksik (kritik):
Q: "SSH hardening script yaz"
Inferred: os=None
→ Kullanıcıya sor:
   "SSH hardening scripti için hangi işletim sistemini kullanıyorsunuz?
    1. Ubuntu 22.04
    2. Ubuntu 20.04
    3. CentOS 9
    4. Windows Server 2022
    5. Diğer (belirtin)"
User: "1"
→ Devam et: os=ubuntu_22_04

Örnek 3 - Security level eksik (önemli ama kritik değil):
Q: "Ubuntu 22.04 SSH hardening script"
Inferred: os=ubuntu_22_04, level=None
→ Kullanıcıya sor:
   "Güvenlik seviyesi tercihiniz:
    1. Balanced (Önerilen - production kullanıma hazır)
    2. Strict (Maksimum güvenlik, bazı özellikler kısıtlı)
    3. Minimal (Temel koruma, geliştirme ortamı için)

    Belirtmezseniz 'Balanced' kullanılacak."
User: "" (boş)
→ Default: balanced
```

---

### 🔄 PARAMETRE TOPLAMA AKIŞI

```
User Question
    ↓
[Parameter Inference Engine]
    ↓
Inferred Params = {os: ?, role: ?, level: ?}
    ↓
[Path Router] → Hangi path?
    ↓
┌────────────────────────────────────────┐
│ PATH: LOCAL/FAST                       │
│ Required Params: NONE                  │
│ → Direkt cevap ver                     │
└────────────────────────────────────────┘

┌────────────────────────────────────────┐
│ PATH: SIMPLE                           │
│ Required Params: NONE                  │
│ Optional: os (if mentioned)            │
│ → Inference başarılıysa kullan        │
│ → Başarısızsa generic cevap            │
└────────────────────────────────────────┘

┌────────────────────────────────────────┐
│ PATH: MEDIUM                           │
│ Required Params: os (for config)       │
│ Optional: role, level                  │
│                                        │
│ Check: os inferred?                    │
│   ├─ YES → Use it                      │
│   └─ NO  → Can answer generically?    │
│         ├─ YES → Generic answer       │
│         └─ NO  → Ask user             │
└────────────────────────────────────────┘

┌────────────────────────────────────────┐
│ PATH: COMPLEX                          │
│ Required Params: os, security_level    │
│ Optional: role, zt_maturity            │
│                                        │
│ Check: os inferred?                    │
│   ├─ YES → Check security_level       │
│   │         ├─ Inferred → Use it      │
│   │         └─ Not inferred → Ask     │
│   └─ NO  → MUST ask                   │
└────────────────────────────────────────┘
```

---

## 2. RAG TETIKLEME STRATEJİSİ

### ❓ Soru: RAG ne zaman devreye girmeli?

**Cevap: Router (path selector) karar vermeli, kullanıcı değil**

Neden:
- ✅ Kullanıcı RAG'i bilmiyor
- ✅ Router sorunun tipini biliyor
- ✅ Path+Intent kombinasyonu RAG ihtiyacını belirler

---

### 📋 PATH BAZLI RAG STRATEJİSİ

#### **LOCAL PATH**
```
RAG: ❌ ASLA

Neden: Pattern-based, LLM bile yok
```

#### **FAST PATH** (Smalltalk)
```
RAG: ❌ ASLA

Neden: Smalltalk için dokümana gerek yok
```

#### **SIMPLE PATH** (Basit bilgi)
```
RAG: 🟡 KOŞULLU

Karar Matrisi:
┌──────────────────────────────┬─────────┐
│ Soru Tipi                    │ RAG?    │
├──────────────────────────────┼─────────┤
│ Generic tanım: "Firewall nedir?" │ ❌ NO   │
│ Specific: "CIS 5.2.5 nedir?"     │ ✅ YES  │
│ Best practice: "SSH best practice" │ ✅ YES  │
│ Config: "SSH port nasıl değişir?"   │ ❌ NO   │
└──────────────────────────────┴─────────┘

Kural:
- Benchmark/standard referansı var → RAG
- Best practice keywords → RAG
- Generic tanım → NO RAG (LLM bilir)
- Basit how-to → NO RAG (LLM bilir)

Kod:
def _should_use_rag_simple(question: str) -> bool:
    # CIS/NIST/ISO reference
    if re.search(r'(CIS|NIST|ISO).*\d+', question):
        return True

    # Best practice keywords
    if 'best practice' in question.lower():
        return True

    # Generic questions
    if re.search(r'\b(nedir|ne demek|what is)\b', question.lower()):
        return False

    return False  # Default: NO RAG for simple
```

#### **MEDIUM PATH** (Yapılandırma)
```
RAG: ✅ HER ZAMAN (varsayılan)

Neden:
- Config soruları → Best practices gerekli
- OS-specific → CIS Benchmarks var
- Security hardening → Standartlar önemli

İstisnalar (RAG skip):
- Çok basit sorular: "SSH restart komutu?"
  → Bu da SIMPLE path'e düşmeliydi zaten

Kod:
def _should_use_rag_medium(question: str) -> bool:
    # Çok basit komut soruları
    if re.search(r'\b(restart|status|start|stop)\s+(command|komut)', question.lower()):
        return False  # LLM bilir

    return True  # Default: USE RAG
```

#### **COMPLEX PATH** (Script/Hardening)
```
RAG: ✅ HER ZAMAN (mutlak)

Neden:
- Script üretimi → CIS/NIST standartları şart
- Full hardening → Comprehensive best practices
- Compliance → Spesifik kontrol maddeleri

İstisnalar: YOK

Kod:
def _should_use_rag_complex(question: str) -> bool:
    return True  # ALWAYS use RAG
```

---

### 🎯 ENTEGRE RAG KARAR SİSTEMİ

```python
# pipeline_optimized.py

class OptimizedPipeline:

    def _should_use_rag(
        self,
        ctx: RequestContext,
        path_type: str,
        complexity: str
    ) -> bool:
        """
        RAG kullanılmalı mı?

        Args:
            ctx: Request context
            path_type: local/fast/simple/medium/complex
            complexity: simple/medium/complex (from classifier)

        Returns:
            bool
        """
        # User explicitly disabled
        if not self.use_rag:
            return False

        # Path-based decision
        if path_type in ["local", "fast"]:
            return False  # Never use RAG

        elif path_type == "simple":
            return self._should_use_rag_simple(ctx.user_question)

        elif path_type == "medium":
            return self._should_use_rag_medium(ctx.user_question)

        elif path_type == "complex":
            return True  # Always use RAG

        return False  # Safe default

    def _should_use_rag_simple(self, question: str) -> bool:
        """SIMPLE path RAG decision"""
        question_lower = question.lower()

        # Benchmark/standard reference → USE RAG
        if re.search(r'(CIS|NIST|ISO|PCI|HIPAA).*[\d\.\-]+', question):
            return True

        # Best practice keywords → USE RAG
        if any(kw in question_lower for kw in [
            'best practice', 'recommended', 'standard', 'compliance'
        ]):
            return True

        # Generic definition → NO RAG
        if re.search(r'\b(nedir|ne demek|what is|explain)\b', question_lower):
            return False

        # Default: NO RAG for simple questions
        return False

    def _should_use_rag_medium(self, question: str) -> bool:
        """MEDIUM path RAG decision"""
        question_lower = question.lower()

        # Very simple command queries → NO RAG
        if re.search(r'\b(restart|status|start|stop|enable|disable)\s+(command|komut)\b', question_lower):
            return False

        # Default: USE RAG for config questions
        return True
```

---

### 📊 RAG KULLANIM DAĞILIMI (Beklenen)

```
100 Sorgu:

LOCAL (35):   RAG=0   (0%)
FAST (15):    RAG=0   (0%)
SIMPLE (20):  RAG=5   (25% - sadece benchmark/best practice)
MEDIUM (20):  RAG=18  (90% - çoğu config sorusu)
COMPLEX (10): RAG=10  (100% - hepsi)

Toplam RAG Calls: 33/100 (33%)

Mevcut Sistem: %50+ RAG kullanımı
Yeni Sistem: %33 RAG kullanımı (-34% azalma)

Faydası:
✅ Gereksiz RAG call'lar azalır
✅ Latency düşer (RAG retrieval ~200-500ms)
✅ Maliyet azalır (embedding API calls)
✅ LLM zaten bildiği şeyleri RAG'den aramıyor
```

---

## 3. KULLANICI EKİLEŞİM AKIŞLARI

### Senaryo 1: Basit Soru (Parametre gerektirmez)

```
User: "Firewall nedir?"

System:
1. Inference: os=None, role=None (generic)
2. Path: SIMPLE
3. RAG Decision: NO (generic tanım)
4. LLM Call: "Firewall nedir?" → Generic cevap
5. Response: "Firewall, ağ trafiğini kontrol eden..."

Kullanıcıya soru sorulmadı ✅
RAG kullanılmadı ✅
```

### Senaryo 2: Config Sorusu (OS inference başarılı)

```
User: "Ubuntu 22.04'te SSH nasıl yapılandırılır?"

System:
1. Inference: os=ubuntu_22_04 (from question)
2. Path: MEDIUM
3. RAG Decision: YES (config question)
4. RAG Retrieval: CIS_Ubuntu_22_04 SSH bölümü
5. LLM Call: prompt + RAG context
6. Response: Ubuntu-specific SSH config

Kullanıcıya soru sorulmadı ✅
RAG kullanıldı ✅
```

### Senaryo 3: Config Sorusu (OS inference başarısız, generic cevap mümkün)

```
User: "SSH port nasıl değiştirilir?"

System:
1. Inference: os=None
2. Path: MEDIUM
3. Required Param Check: OS gerekli AMA generic cevap verilebilir
4. RAG Decision: NO (generic how-to)
5. LLM Call: Generic SSH port change
6. Response:
   "SSH port değiştirme:

    Linux:
    1. /etc/ssh/sshd_config düzenle
    2. Port 22 → Port 2222
    3. systemctl restart sshd/ssh

    Windows:
    1. Registry veya PowerShell
    2. Restart SSH service

    ℹ️ Belirli bir işletim sistemi için detaylı adımlar isterseniz belirtin."

Kullanıcıya soru sorulmadı ✅
Generic cevap verildi ✅
```

### Senaryo 4: Script İsteği (OS eksik, kritik)

```
User: "SSH hardening script yaz"

System:
1. Inference: os=None
2. Path: COMPLEX
3. Required Param Check: OS MUTLAKA gerekli
4. Missing Critical Param → ASK USER

Response:
{
    "status": "missing_params",
    "message": "SSH hardening scripti için ek bilgi gerekli:",
    "questions": [
        {
            "param": "os",
            "question": "Hangi işletim sistemi için?",
            "options": [
                {"value": "ubuntu_22_04", "label": "Ubuntu 22.04"},
                {"value": "ubuntu_20_04", "label": "Ubuntu 20.04"},
                {"value": "centos_9", "label": "CentOS 9"},
                {"value": "windows_server_2022", "label": "Windows Server 2022"}
            ],
            "required": true
        },
        {
            "param": "security_level",
            "question": "Güvenlik seviyesi? (opsiyonel, varsayılan: balanced)",
            "options": [
                {"value": "minimal", "label": "Minimal (Temel koruma)"},
                {"value": "balanced", "label": "Balanced (Önerilen)"},
                {"value": "strict", "label": "Strict (Maksimum güvenlik)"}
            ],
            "required": false
        }
    ]
}

User: { "os": "ubuntu_22_04", "security_level": "balanced" }

System:
1. Retry with params
2. Path: COMPLEX
3. RAG: YES
4. Generate script

Kullanıcıya minimal soru soruldu ✅
Sadece kritik parametre istendi ✅
```

---

## 4. UYGULAMA ÖNERİSİ

### A. Parametre Stratejisi

```
KURAL 1: Default First
→ Her parametre için safe default var

KURAL 2: Infer When Possible
→ Sorudan çıkarılabiliyorsa çıkar

KURAL 3: Ask Only When Critical
→ Kritik VE inference başarısızsa sor

KURAL 4: Generic Fallback
→ Mümkünse generic cevap ver, sorma
```

### B. RAG Stratejisi

```
KURAL 1: Router Decides
→ Kullanıcı değil, router karar verir

KURAL 2: Path-based Logic
→ Her path kendi RAG politikası

KURAL 3: Question Analysis
→ Benchmark/standard mention → RAG
→ Generic tanım → NO RAG

KURAL 4: Performance Priority
→ Gereksiz RAG call yapma
```

---

## 5. SONUÇ

✅ **Önerilen Yaklaşım:**

1. **Parametreler:**
   - Her path kendi gereksinimlerini bilir
   - Inference first, ask only when critical
   - Generic fallback when possible
   - User-friendly prompts

2. **RAG:**
   - Router decides (user agnostic)
   - Path + question type kombinasyonu
   - Performance optimized
   - %33 RAG usage (from %50+)

3. **User Experience:**
   - Minimum friction
   - Smart defaults
   - Contextual questions
   - Progressive disclosure

Bu yaklaşım hem performans hem UX için optimal!
