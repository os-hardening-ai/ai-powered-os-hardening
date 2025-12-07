# 🔍 PIPELINE DETAYLI ANALİZ RAPORU

## 📊 Genel Bakış

Pipeline'da **5 farklı route** bulunmaktadır:

1. **LOCAL PATH** - Pattern-based (LLM yok, $0)
2. **FAST PATH** - Smalltalk (ultra-fast model)
3. **SIMPLE PATH** - Basit sorular (small model)
4. **MEDIUM PATH** - Orta karmaşıklık (large model, minimal CoT)
5. **COMPLEX PATH** - Karmaşık analiz (large model, full CoT)

---

## 🎯 ROUTE 1: LOCAL PATH (Pattern-Based)

### Akış Şeması
```
User Input
    ↓
[Local Responder Pattern Matching]
    ↓
Match Found?
    ├── YES → Return Local Response (DONE) ✅
    └── NO  → Continue to STEP 0.5 (RAG)
```

### Tetiklenme Koşulları
```python
# local_responder.py
Patterns:
1. Selamlaşma: "merhaba", "selam", "hi", "hello" (≤3 kelime)
2. Vedalaşma: "görüşürüz", "hoşça kal", "bye"
3. Teşekkür: "teşekkür", "sağol", "thanks"
4. Yardım: "sana bir sorum var", "yardım"
5. Tanımlar: "zero trust nedir?", "cis nedir?"
6. Hızlı komutlar: "ssh port değiştir", "firewall durum"
```

### Kullanılan Parametreler
| Parametre | Kullanım | Neden |
|-----------|----------|-------|
| `user_question` | ✅ Kullanılır | Pattern matching için |
| `os` | ❌ Kullanılmaz | Generic cevaplar |
| `role` | ❌ Kullanılmaz | Generic cevaplar |
| `security_level` | ❌ Kullanılmaz | Generic cevaplar |
| `zt_maturity` | ❌ Kullanılmaz | Generic cevaplar |
| `RAG` | ❌ Kullanılmaz | Önceden tanımlı cevaplar |

### LLM Çağrısı
- **LLM Calls:** 0
- **Maliyet:** $0.00
- **Süre:** <1ms
- **Model:** None (Regex matching)

### Örnek
```
Input: "merhaba"
Processing: Regex match on greeting_patterns
Output: "Merhaba! Siber güvenlik konusunda size nasıl yardımcı olabilirim?"
Stats: {local_response_count: 1}
```

---

## 🚀 ROUTE 2: FAST PATH (Smalltalk)

### Akış Şeması
```
User Input
    ↓
[Quick Intent Check] (keyword-based, NO LLM)
    ↓
Intent = smalltalk?
    ├── YES → [FAST PATH]
    │         ↓
    │     [Build Simple Smalltalk Prompt]
    │         ↓
    │     [Call Small LLM] (gpt-3.5-turbo / groq-llama-8b)
    │         ↓
    │     [Return Response] ✅
    │
    └── NO  → Continue to STEP 3 (Complexity Classification)
```

### Tetiklenme Koşulları
```python
# pipeline_optimized.py - _quick_intent_check()
Keywords:
- Greeting: "merhaba", "selam", "hey", "hi", "hello" (≤5 kelime)
- Farewell: "görüşürüz", "hoşçakal", "bye"
→ Return: "smalltalk_greeting" or "smalltalk_farewell"
```

### Kullanılan Parametreler
| Parametre | Kullanım | Prompt'ta Var mı? |
|-----------|----------|-------------------|
| `user_question` | ✅ Kullanılır | ✅ Evet |
| `os` | ❌ Kullanılmaz | ❌ Hayır |
| `role` | ❌ Kullanılmaz | ❌ Hayır |
| `security_level` | ❌ Kullanılmaz | ❌ Hayır |
| `zt_maturity` | ❌ Kullanılmaz | ❌ Hayır |
| `RAG` | ❌ Kullanılmaz | ❌ Hayır |

### LLM Çağrısı
```python
# _fast_path_smalltalk()
Prompt:
"""
Kullanıcı sana şunu yazdı: "{ctx.user_question}"

Bu bir smalltalk mesajı. Kısa, dostça ve profesyonel bir şekilde cevap ver.
Kullanıcıya güvenlik konusunda nasıl yardımcı olabileceğini belirt.

Cevap (1-2 cümle):
"""

Model: self.llm_small (Groq Llama 8B / GPT-3.5-turbo)
Cost: $0.0001
```

### Örnek
```
Input: "merhaba, nasılsın?"
Processing:
  1. quick_intent_check() → "smalltalk_greeting"
  2. _fast_path_smalltalk()
  3. LLM call with minimal prompt
Output: "Merhaba! Ben iyiyim, teşekkürler. SSH, firewall veya sistem güvenliği hakkında size nasıl yardımcı olabilirim?"
Stats: {fast_path_count: 1, total_calls: 1, total_cost: $0.0001}
```

---

## 📘 ROUTE 3: SIMPLE PATH (Basit Sorular)

### Akış Şeması
```
User Input
    ↓
[RAG Retrieval] (optional, kullanılmayabilir)
    ↓
[Quick Intent Check] → NOT smalltalk
    ↓
[Complexity Classifier]
    ↓
Complexity = "simple"?
    ├── YES → [SIMPLE PATH]
    │         ↓
    │     [Build Simple Prompt] (minimal format)
    │         ↓
    │     [Call Small LLM]
    │         ↓
    │     [Return Response] ✅
    │
    └── NO  → Continue to MEDIUM or COMPLEX
```

### Tetiklenme Koşulları
```python
# question_classifier.py - classify()
SIMPLE Patterns:
1. Çok kısa sorular (≤3 kelime)
2. Pattern match:
   - "nedir", "ne demek", "nasıl yapılır"
   - "command nedir", "açıkla X"
3. Kelime sayısı ≤10 (default case)

Examples:
- "SELinux nedir?"
- "ssh port değiştir"
- "firewall nedir"
```

### Kullanılan Parametreler
| Parametre | Kullanım | Prompt'ta Var mı? | Etki Seviyesi |
|-----------|----------|-------------------|---------------|
| `user_question` | ✅ Kullanılır | ✅ Evet | 🔴 Yüksek |
| `os` | ⚠️ Kısmen | ✅ Evet (minimal) | 🟡 Düşük |
| `role` | ⚠️ Kısmen | ✅ Evet (minimal) | 🟡 Düşük |
| `security_level` | ❌ Kullanılmaz | ❌ Hayır | - |
| `zt_maturity` | ❌ Kullanılmaz | ❌ Hayır | - |
| `RAG` | ⚠️ Opsiyonel | ❌ Genelde hayır | 🟢 Çok düşük |

### LLM Çağrısı
```python
# simple_prompts.py - build_simple_prompt()
Prompt:
"""
Sen bir siber güvenlik uzmanısın. Kullanıcının sorusuna kısa, net ve pratik bir şekilde cevap ver.

SORU: "{ctx.user_question}"

BAĞLAM:
- OS: {ctx.os or 'genel'}           # Minimal kullanım
- Rol: {ctx.role or 'sysadmin'}     # Minimal kullanım

GÖREV:
Soruya KISA ve ÖZ bir şekilde cevap ver (1-3 paragraf).

FORMAT:
1. Ana cevap (açık ve net)
2. Örnek komut/config varsa ekle
3. Önemli uyarı varsa 1 cümle ile belirt

NOT:
- Gereksiz emoji kullanma
- Çok fazla bölüm açma
- Direkt ve pratik ol
- Zero Trust ile ilgiliyse sadece 1 cümle ile bahset

CEVAP:
"""

Model: self.llm_small (Groq Llama 8B - BEDAVA)
Cost: $0.0002 (veya $0 Groq ile)
```

### Parametre Kullanım Analizi

**OS Parametresi:**
```python
# Prompt'ta: "OS: ubuntu_22_04" veya "OS: genel"
# Etki: Minimal - LLM zaten context'ten anlıyor
# Örnek:
Soru: "SELinux nedir?"
OS: ubuntu_22_04 → Cevap: "SELinux... Ubuntu'da varsayılan AppArmor'dur."
OS: rhel8         → Cevap: "SELinux... RHEL'de varsayılan aktiftir."
```

**Role Parametresi:**
```python
# Prompt'ta: "Rol: sysadmin" veya "Rol: developer"
# Etki: Minimal - Basit tanımlar değişmez
# Örnek:
Soru: "Firewall nedir?"
Role: sysadmin   → Cevap: "... ufw/firewalld ile yönetilir"
Role: developer  → Cevap: "... geliştirme ortamında docker networking etkileyebilir"
```

### Örnek
```
Input: "SELinux nedir?"

Processing:
  1. Local Path → NO MATCH
  2. RAG Retrieval → SKIPPED (genel bilgi)
  3. quick_intent_check() → "os_hardening"
  4. classify_question() → "simple" (pattern: "nedir", 2 kelime)
  5. _simple_path()
  6. build_simple_prompt(ctx) with:
     - user_question: "SELinux nedir?"
     - os: "ubuntu_22_04" (minimal effect)
     - role: "sysadmin" (minimal effect)
  7. LLM call (Groq Llama 8B)

Output:
"""
SELinux (Security-Enhanced Linux), Linux kernel'ine entegre mandatory access control (MAC) güvenlik mekanizmasıdır.

Kullanıcı/grup izinlerine ek olarak, her dosya/süreç için güvenlik politikaları tanımlar. RedHat/CentOS'ta varsayılan aktiftir.

Ubuntu'da alternatifi AppArmor kullanılır.

Durum kontrolü: sestatus (RHEL) veya aa-status (Ubuntu)

Uyarı: SELinux yanlış yapılandırılırsa servisler başlamayabilir.
"""

Stats: {simple_path_count: 1, total_calls: 1, total_cost: $0}
```

---

## 📗 ROUTE 4: MEDIUM PATH (Orta Karmaşıklık)

### Akış Şeması
```
User Input
    ↓
[RAG Retrieval] (AKTIF - güvenlik soruları için)
    ↓
[Quick Intent Check] → NOT smalltalk
    ↓
[Complexity Classifier]
    ↓
Complexity = "medium"?
    ├── YES → [MEDIUM PATH]
    │         ↓
    │     [Build Medium Prompt] (orta format)
    │         ↓
    │     [Call Large LLM] (gpt-4o-mini)
    │         ↓
    │     [Return Response] ✅
    │
    └── NO  → Continue to COMPLEX
```

### Tetiklenme Koşulları
```python
# question_classifier.py
MEDIUM Patterns:
1. "nasıl" soruları: "nasıl güvenli", "how to"
2. Spesifik servis config: "ssh config", "firewall rule", "rdp hardening"
3. Tek servis güvenlik: "nginx güvenlik", "apache harden"
4. Kelime sayısı 11-20

Examples:
- "SSH yapılandırmasını nasıl güvenli hale getiririm?"
- "nginx için güvenlik ayarları nelerdir?"
- "Ubuntu'da log rotation nasıl yapılır?"
```

### Kullanılan Parametreler
| Parametre | Kullanım | Prompt'ta Var mı? | Etki Seviyesi |
|-----------|----------|-------------------|---------------|
| `user_question` | ✅ Kullanılır | ✅ Evet | 🔴 Yüksek |
| `os` | ✅ Kullanılır | ✅ Evet | 🔴 Yüksek |
| `role` | ✅ Kullanılır | ✅ Evet | 🟡 Orta |
| `security_level` | ✅ Kullanılır | ✅ Evet | 🟡 Orta |
| `zt_maturity` | ❌ Kullanılmaz | ❌ Hayır | - |
| `RAG` | ✅ Kullanılır | ✅ Evet (context'te) | 🔴 Yüksek |

### LLM Çağrısı
```python
# simple_prompts.py - build_medium_prompt()
Prompt:
"""
Sen bir Zero Trust siber güvenlik uzmanısın. Kullanıcının sorusuna pratik ve uygulanabilir bir şekilde cevap ver.

SORU: "{ctx.user_question}"

BAĞLAM:
- OS: {ctx.os or 'genel'}                    # YÜKSEK ETKİ
- Rol: {ctx.role or 'sysadmin'}              # ORTA ETKİ
- Security Level: {ctx.security_level}       # ORTA ETKİ

GÖREV:
Kullanıcıya pratik, adım adım bir cevap sun.

FORMAT (Basit):

ÖZET
[1-2 cümle: Ne yapılacak?]

ÖNERİLEN ADIMLAR
1. [İlk adım]
2. [İkinci adım]
...

ÖRNEK KOMUTLAR
```bash
# Örnek komutlar
```

ZERO TRUST İLİŞKİSİ (opsiyonel)
[Sadece alakalıysa, 1-2 cümle]

RİSK / UYARILAR
[Varsa, önemli noktalar]

CEVAP:
"""

Model: self.llm_large (GPT-4o-mini)
Cost: $0.0005
```

### Parametre Kullanım Analizi

**OS Parametresi:**
```python
# YÜKSEK ETKİ - Komutlar OS'e göre değişir
Soru: "SSH yapılandırması nasıl yapılır?"
OS: ubuntu_22_04 → Config: /etc/ssh/sshd_config, sudo systemctl restart ssh
OS: centos_8     → Config: /etc/ssh/sshd_config, sudo systemctl restart sshd
OS: windows_11   → GUI: Server Manager, PowerShell komutları
```

**Role Parametresi:**
```python
# ORTA ETKİ - Detay seviyesi değişir
Soru: "nginx güvenlik ayarları nelerdir?"
Role: sysadmin   → Detaylı config, monitoring, log rotation
Role: developer  → Temel security headers, CORS, local dev uyarıları
Role: devops     → CI/CD entegrasyonu, automation, IaC örnekleri
```

**Security Level Parametresi:**
```python
# ORTA ETKİ - Kuralların katılığı değişir
Soru: "SSH hardening nasıl yapılır?"

Security Level: minimal
→ PasswordAuthentication no
→ PermitRootLogin prohibit-password

Security Level: balanced
→ PasswordAuthentication no
→ PermitRootLogin no
→ MaxAuthTries 3

Security Level: strict
→ PasswordAuthentication no
→ PermitRootLogin no
→ MaxAuthTries 2
→ AllowUsers specific_user
→ Protocol 2 (enforce)
→ Key-based only + 2FA
```

**RAG Parametresi:**
```python
# YÜKSEK ETKİ - Best practice'leri sağlar
Soru: "SSH hardening nasıl yapılır?"

RAG Context:
"""
[Kaynak 1] (Relevance: 0.92)
Doküman: CIS_Ubuntu_22_04_Benchmark.pdf
Bölüm: 5.2 - SSH Server Configuration

Kontroller:
5.2.3 - Ensure permissions on /etc/ssh/sshd_config are configured
5.2.5 - Ensure SSH LogLevel is appropriate
5.2.15 - Ensure only strong ciphers are used
...
"""

LLM Output (RAG ile):
→ CIS standartlarına uygun
→ Spesifik cipher suites
→ Tam kontrol listesi
```

### Örnek
```
Input: "Ubuntu 22.04'te SSH yapılandırmasını nasıl güvenli hale getiririm?"

Processing:
  1. Local Path → NO MATCH
  2. RAG Retrieval → AKTIF
     Retrieved: CIS_Ubuntu_22_04_Benchmark (SSH bölümü)
  3. quick_intent_check() → "os_hardening"
  4. classify_question() → "medium" (pattern: "nasıl güvenli", 10 kelime)
  5. _medium_path()
  6. build_medium_prompt(ctx) with:
     - user_question: "Ubuntu 22.04'te SSH..."
     - os: "ubuntu_22_04" (YÜKSEK ETKİ)
     - role: "sysadmin" (ORTA ETKİ)
     - security_level: "balanced" (ORTA ETKİ)
     - RAG context: CIS benchmarks (YÜKSEK ETKİ)
  7. LLM call (GPT-4o-mini)

Output:
"""
ÖZET
SSH server'ınızı CIS Ubuntu 22.04 standardına göre sıkılaştıracağız.

ÖNERİLEN ADIMLAR
1. SSH config dosyasını düzenleyin
2. Root login'i devre dışı bırakın
3. Şifre authentication'ı kapatın (key-based)
4. Port değiştirmeyi düşünün
5. Fail2ban kurun

ÖRNEK KOMUTLAR
```bash
# 1. Config düzenle
sudo nano /etc/ssh/sshd_config

# Değişiklikler (Balanced seviye):
PermitRootLogin no
PasswordAuthentication no
MaxAuthTries 3
Protocol 2

# 2. SSH restart
sudo systemctl restart ssh

# 3. Firewall (yeni port için)
sudo ufw allow 2222/tcp
```

ZERO TRUST İLİŞKİSİ
SSH sıkılaştırma "strong_identity" ve "continuous_verification" prensiplerine uyar.

RİSK / UYARILAR
- Config değişikliği öncesi SSH bağlantınızı koruyun
- Test kullanıcısı ile önce deneyin
"""

Stats: {
  medium_path_count: 1,
  total_calls: 1,
  rag_retrieval_count: 1,
  total_cost: $0.0005
}
```

---

## 📕 ROUTE 5: COMPLEX PATH (Karmaşık Analiz - CoT)

### Akış Şeması
```
User Input
    ↓
[RAG Retrieval] (AKTIF - full context)
    ↓
[Quick Intent Check] → NOT smalltalk
    ↓
[Complexity Classifier]
    ↓
Complexity = "complex"?
    └── YES → [COMPLEX PATH]
              ↓
          [Adaptive Model Router] (task-based model selection)
              ↓
          [Build CoT Prompt] (6-step reasoning chain)
              ↓
          [Call Large LLM] (GPT-4o / GPT-4o-mini)
              ↓
          [Parse CoT Response] (extract 6 steps)
              ↓
          [Return Response] ✅
```

### Tetiklenme Koşulları
```python
# question_classifier.py
COMPLEX Patterns:
1. Full hardening: "full hardening script", "hardening script yaz"
2. Zero Trust: "zero trust mimari", "zt architecture"
3. Compliance/Audit: "compliance check", "tam audit"
4. Incident response: "saldırı analizi", "incident response"
5. Script/automation: "script yaz", "automation kur"
6. Monitoring: "monitoring kur", "alerting setup"
7. Kelime sayısı >20

Examples:
- "Ubuntu 22.04 için full hardening script yaz"
- "Zero Trust mimarisini nasıl uygularım?"
- "Sistemde saldırı analizi yap ve raporla"
```

### Kullanılan Parametreler
| Parametre | Kullanım | Prompt'ta Var mı? | Etki Seviyesi |
|-----------|----------|-------------------|---------------|
| `user_question` | ✅ Kullanılır | ✅ Evet | 🔴 Çok Yüksek |
| `os` | ✅ Kullanılır | ✅ Evet | 🔴 Çok Yüksek |
| `role` | ✅ Kullanılır | ✅ Evet | 🔴 Yüksek |
| `security_level` | ✅ Kullanılır | ✅ Evet | 🔴 Yüksek |
| `zt_maturity` | ✅ Kullanılır | ✅ Evet | 🔴 Yüksek |
| `RAG` | ✅ Kullanılır | ✅ Evet (full) | 🔴 Çok Yüksek |

### LLM Çağrısı
```python
# cot_prompts.py - build_cot_prompt()
Prompt (6-Step CoT):
"""
═══════════════════════════════════════════════════════════════════
🎯 SENİN GÖREVİN: Aşağıdaki kullanıcı sorusunu 6 ADIMDA analiz et
═══════════════════════════════════════════════════════════════════

Sen bir Zero Trust siber güvenlik uzmanısın. Kullanıcının sorusunu
sistematik olarak analiz edip, savunma odaklı, uygulanabilir öneriler sun.

KULLANICI SORUSU:
\"\"\"{ctx.user_question}\"\"\"

BAĞLAM:
- OS: {ctx.os or 'belirtilmemiş'}           # ÇOK YÜKSEK ETKİ
- Rol: {ctx.role or 'sysadmin'}             # YÜKSEK ETKİ
- Security Level: {ctx.security_level}      # YÜKSEK ETKİ
- ZT Maturity: {ctx.zt_maturity}            # YÜKSEK ETKİ

─────────────────────────────────────────────────────────────────

📋 GÖREV: Aşağıdaki 6 ADIMI TAM OLARAK takip et ve her adımı düşünerek ilerle.

═══════════════════════════════════════════════════════════════════
ADIM 1: GÜVENLİK DEĞERLENDİRMESİ
═══════════════════════════════════════════════════════════════════

Bu talep güvenlik açısından nasıl sınıflandırılır?

✅ **defensive_security**: Savunma, hardening, monitoring
⚠️  **ambiguous**: Belirsiz
❌ **offensive_illegal**: Saldırı, exploit

**DÜŞÜNCE SÜRECİN:**
[Soruyu analiz et - hangi amaçla sorulmuş?]

**SONUÇ:** [defensive_security / ambiguous / offensive_illegal]

─────────────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════════════
ADIM 2: NİYET ANALİZİ
═══════════════════════════════════════════════════════════════════

Kullanıcı tam olarak ne istiyor?

**İntent Kategorileri:**
- os_hardening
- script_or_config
- incident_analysis
- conceptual_explanation

**DÜŞÜNCE SÜRECİN:**
[Sorunun odak noktası ne?]

**Intent:** [...]
**Hedef Alan:** [ssh / firewall / network / vb.]
**Script Gerekli mi?:** [Evet / Hayır]

─────────────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════════════
ADIM 3: ZERO TRUST PRENSİPLERİ VE STANDARTLAR
═══════════════════════════════════════════════════════════════════

Bu talep hangi Zero Trust prensipleriyle ilişkili?

**Mevcut ZT Prensipleri:**
- least_privilege
- continuous_verification
- assume_breach
- micro_segmentation
- strong_identity
- device_posture
- secure_access
- visibility_and_analytics

**DÜŞÜNCE SÜRECİN:**
[Her prensibi ele al ve ilişkisini düşün]

**İlgili Prensipler:**
[2-4 prensip seç ve NEDEN ilgili olduğunu açıkla]

**Standart Referansları:**
[CIS/NIST/ISO - MADDE NUMARALI]
[Örnek: CIS_Ubuntu_22_04:5.2.5, NIST_800-53:AC-17]

─────────────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════════════
ADIM 4: RİSK VE ETKİ DEĞERLENDİRMESİ
═══════════════════════════════════════════════════════════════════

Bu değişikliğin sistem üzerindeki etkisi ve riski nedir?

**Risk Seviyesi:** [low / medium / high / critical]

**Etki Analizi:**
- Sistem kararlılığına etkisi?
- Kullanıcı deneyimine etkisi?
- Geri dönüş (rollback) planı?

**Rollback Yaklaşımı:**
[Somut geri alma adımları]

─────────────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════════════
ADIM 5: UYGULAMA PLANI
═══════════════════════════════════════════════════════════════════

**Adım Adım Plan:**
1. [İlk adım]
2. [İkinci adım]
...

**Öncelikler:**
[Hangi adım önce, hangisi sonra?]

─────────────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════════════
ADIM 6: DETAYLI KULLANICI CEVABI
═══════════════════════════════════════════════════════════════════

Kullanıcıya vereceğin FINAL CEVAP (FULL FORMAT):

[Detaylı, adım adım, script'li, rollback'li, standart referanslı]

CEVAP:
"""

Model: self.llm_large (GPT-4o-mini / GPT-4o)
       Selected by AdaptiveModelRouter based on priority
Cost: $0.002 - $0.05 (context length'e bağlı)
```

### Parametre Kullanım Analizi

**Tüm Parametreler Maksimum Etkili:**

```python
# OS - ÇOK YÜKSEK ETKİ
OS: ubuntu_22_04 → apt, systemd, ufw, apparmor
OS: centos_8     → yum, systemd, firewalld, selinux
OS: windows_11   → PowerShell, Windows Defender, GPO

# Role - YÜKSEK ETKİ
Role: sysadmin   → Full system access, automation, monitoring
Role: developer  → Dev env, local testing, CI/CD integration
Role: devops     → IaC, Terraform/Ansible, orchestration
Role: security   → Audit, compliance, penetration testing

# Security Level - YÜKSEK ETKİ
Level: minimal   → Temel kurallar, az kısıtlama
Level: balanced  → Önerilen, production-ready
Level: strict    → Maksimum güvenlik, compliance-focused

# ZT Maturity - YÜKSEK ETKİ
Maturity: low    → Temel ZT prensipleri, giriş seviyesi
Maturity: medium → Orta seviye, mikro-segmentation başlangıç
Maturity: high   → Tam ZT, continuous verification, analytics

# RAG - ÇOK YÜKSEK ETKİ
RAG Context: Full benchmarks, best practices, specific controls
```

### Örnek - Karmaşık Script İsteği
```
Input: "Ubuntu 22.04 için sysadmin rolüme uygun, balanced security level'da full SSH hardening script yaz. ZT maturity medium."

Processing:
  1. Local Path → NO MATCH
  2. RAG Retrieval → AKTIF (full context)
     Retrieved:
       - CIS_Ubuntu_22_04_Benchmark (SSH section)
       - NIST_800-53 (Access Control)
       - Zero_Trust_Architecture (Strong Identity)
  3. quick_intent_check() → "os_hardening"
  4. classify_question() → "complex" (pattern: "full hardening script", 20+ kelime)
  5. _complex_path_cot()
  6. Adaptive Router → GPT-4o-mini (balanced priority)
  7. build_cot_prompt(ctx) with ALL PARAMETERS
  8. LLM call with 6-step CoT reasoning
  9. parse_cot_response() → Extract structured output

Output (LLM reasoning):
"""
ADIM 1: GÜVENLİK DEĞERLENDİRMESİ
**DÜŞÜNCE:** SSH hardening, savunma amaçlı, defensive.
**SONUÇ:** defensive_security

ADIM 2: NİYET ANALİZİ
**Intent:** script_or_config
**Hedef:** ssh
**Script:** Evet, tam otomasyon gerekli

ADIM 3: ZERO TRUST PRENSİPLERİ
**İlgili Prensipler:**
- strong_identity: SSH key-based auth, multi-factor
- continuous_verification: Session timeout, re-auth
- least_privilege: Specific user allow-list

**Standart Referanslar:**
- CIS_Ubuntu_22_04:5.2.1 (SSH Protocol 2)
- CIS_Ubuntu_22_04:5.2.5 (SSH LogLevel)
- NIST_800-53:AC-17 (Remote Access)

ADIM 4: RİSK DEĞERLENDİRMESİ
**Risk:** medium (SSH lockout riski var)
**Rollback:**
1. Backup: cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup
2. Test kullanıcı ile dene
3. Geri alma: mv /etc/ssh/sshd_config.backup /etc/ssh/sshd_config

ADIM 5: PLAN
1. Backup config
2. Config değişiklikleri
3. Firewall update
4. SSH restart
5. Test
6. Fail2ban kurulum

ADIM 6: KULLANICI CEVABI

# SSH Hardening Script - Ubuntu 22.04
# Role: SysAdmin | Security: Balanced | ZT: Medium

#!/bin/bash
set -euo pipefail

# 1. Backup
echo "[1/6] Backing up SSH config..."
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup.$(date +%F)

# 2. SSH Hardening (Balanced Level)
echo "[2/6] Applying SSH hardening..."
sudo tee /etc/ssh/sshd_config.d/99-hardening.conf <<EOF
# CIS Ubuntu 22.04 - Section 5.2
Protocol 2
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
LoginGraceTime 60
AllowUsers sysadmin_user  # ZT: Least Privilege
ClientAliveInterval 300   # ZT: Continuous Verification
ClientAliveCountMax 2

# Strong Ciphers (ZT: Strong Identity)
Ciphers aes256-gcm@openssh.com,chacha20-poly1305@openssh.com
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
KexAlgorithms curve25519-sha256,diffie-hellman-group-exchange-sha256

# Logging (ZT: Visibility)
LogLevel VERBOSE
SyslogFacility AUTH
EOF

# 3. Firewall (optional port change)
echo "[3/6] Updating firewall..."
# sudo ufw allow 2222/tcp  # Uncomment for custom port

# 4. Restart SSH
echo "[4/6] Restarting SSH..."
sudo systemctl restart ssh

# 5. Test
echo "[5/6] Testing SSH config..."
sudo sshd -t && echo "✅ SSH config valid"

# 6. Fail2ban (ZT: Assume Breach)
echo "[6/6] Installing Fail2ban..."
sudo apt update && sudo apt install fail2ban -y
sudo systemctl enable --now fail2ban

echo "
✅ SSH Hardening Complete!

ROLLBACK:
sudo mv /etc/ssh/sshd_config.backup.$(date +%F) /etc/ssh/sshd_config
sudo systemctl restart ssh

NEXT STEPS:
1. Test SSH login from another session
2. Review fail2ban logs: sudo fail2ban-client status sshd
3. Monitor auth logs: sudo tail -f /var/log/auth.log

ZERO TRUST ALIGNMENT:
✅ Strong Identity (key-based + strong ciphers)
✅ Continuous Verification (session timeout)
✅ Least Privilege (user whitelist)
✅ Visibility (verbose logging)
"
"""

Stats: {
  complex_path_count: 1,
  total_calls: 1,
  rag_retrieval_count: 1,
  total_cost: $0.015
}
```

---

## 📊 Route Karşılaştırma Tablosu

| Route | LLM Calls | Model | Maliyet | Süre | OS | Role | Sec Level | ZT | RAG |
|-------|-----------|-------|---------|------|-----|------|-----------|-----|-----|
| **LOCAL** | 0 | None | $0 | <1ms | ❌ | ❌ | ❌ | ❌ | ❌ |
| **FAST** | 1 | Small | $0.0001 | 1s | ❌ | ❌ | ❌ | ❌ | ❌ |
| **SIMPLE** | 1 | Small | $0 (Groq) | 1-2s | 🟡 | 🟡 | ❌ | ❌ | 🟢 |
| **MEDIUM** | 1 | Large | $0.0005 | 2-4s | 🔴 | 🟡 | 🟡 | ❌ | 🔴 |
| **COMPLEX** | 1 | Large | $0.002-$0.05 | 5-10s | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 |

**Sembol Açıklaması:**
- ❌ Kullanılmaz
- 🟢 Minimal etki
- 🟡 Orta etki
- 🔴 Yüksek/Çok yüksek etki

---

## 🎯 Karar Ağacı (Decision Tree)

```
                        User Question
                             |
                             ↓
                  [Local Pattern Match?]
                   /                  \
                 YES                  NO
                  ↓                    ↓
            [LOCAL PATH]        [RAG Retrieval]
                ✅                     ↓
                              [Quick Intent Check]
                               /              \
                        Smalltalk?           Security
                            ↓                    ↓
                      [FAST PATH]      [Complexity Classifier]
                            ✅               /    |    \
                                      Simple Medium Complex
                                         ↓      ↓       ↓
                                    [SIMPLE] [MEDIUM] [COMPLEX]
                                        ✅      ✅        ✅
```

---

## 💡 Önemli Bulgular

### 1. Parametre Kullanım Hiyerarşisi
```
user_question: TÜM route'larda kullanılır (temel girdi)

os:
  - LOCAL: ❌
  - FAST: ❌
  - SIMPLE: 🟡 (minimal)
  - MEDIUM: 🔴 (yüksek)
  - COMPLEX: 🔴 (çok yüksek)

role:
  - LOCAL/FAST: ❌
  - SIMPLE: 🟡 (minimal)
  - MEDIUM: 🟡 (orta)
  - COMPLEX: 🔴 (yüksek)

security_level:
  - LOCAL/FAST/SIMPLE: ❌
  - MEDIUM: 🟡 (orta)
  - COMPLEX: 🔴 (yüksek)

zt_maturity:
  - LOCAL/FAST/SIMPLE/MEDIUM: ❌
  - COMPLEX: 🔴 (yüksek)

RAG:
  - LOCAL/FAST: ❌
  - SIMPLE: 🟢 (nadiren)
  - MEDIUM: 🔴 (sık)
  - COMPLEX: 🔴 (her zaman)
```

### 2. Maliyet Optimizasyonu
```
Basit sorular (80% traffic):
  → LOCAL/FAST/SIMPLE paths
  → Maliyet: $0 (Groq kullanımı ile)

Orta sorular (15% traffic):
  → MEDIUM path
  → Maliyet: $0.0005

Karmaşık sorular (5% traffic):
  → COMPLEX path
  → Maliyet: $0.002-$0.05

Ortalama maliyet/sorgu: ~$0.001
```

### 3. Akıllı Route Selection
Pipeline otomatik olarak:
1. Pattern matching ile LLM'siz cevaplar üretir
2. Complexity'ye göre doğru modeli seçer
3. Gereksiz parametreleri ignore eder
4. RAG'i sadece gerektiğinde kullanır

---

## 🚀 Sonuç

Pipeline **5 farklı route** ile **akıllı** ve **maliyet-etkin** çalışır:

✅ Basit sorular: LLM'siz veya ücretsiz (Groq)
✅ Orta sorular: Gerekli parametreler + RAG
✅ Karmaşık sorular: Tüm parametreler + Full CoT + RAG

Kullanıcı perspektifinden tek bir API call, arka planda akıllı optimizasyon!
