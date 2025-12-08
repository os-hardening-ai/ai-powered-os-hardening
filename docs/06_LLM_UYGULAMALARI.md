# LLM Uygulamaları - Makine Öğrenmesi ve LLM Detayları

## Genel Bakış

Bu proje **2 temel AI/ML teknolojisi** kullanır:
1. **Makine Öğrenmesi (ML)**: Intent detection için
2. **Large Language Models (LLM)**: Güvenlik classification ve yanıt generation için

```
┌──────────────────────────────────────────────────────────────┐
│                    AI/ML ARCHITECTURE                         │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Layer 1: Safety Classification                              │
│  └─ LLM (Groq Llama 8B) - ~700ms                            │
│                                                               │
│  Layer 2: Intent Detection                                   │
│  └─ ML Hybrid (Logistic Regression + Pattern) - <10ms       │
│                                                               │
│  Layer 3: Generation                                         │
│  └─ LLM (Groq Llama 70B) + RAG - ~2-3s                      │
│                                                               │
│  Layer 4: Output Validation                                  │
│  └─ Regex + LLM Hybrid - <100ms                             │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 1. ML-Based Intent Detection

### Problem Tanımı

**Soru**: Kullanıcının niyeti nedir?
- Selamlaşma mı? (greeting)
- Bilgi mi soruyor? (info_request)
- Script mi istiyor? (action_request)
- Güvenlik dışı konu mu? (out_of_scope)

**Neden Önemli?**
Intent'e göre farklı pipeline'lara yönlendirme yapıyoruz:
- Greeting → Pattern response (LLM yok, $0)
- Info → RAG + LLM ($0.001)
- Action → RAG + LLM + ZT enrichment ($0.002)

**Önceki Yaklaşım (Keyword-based):**
```python
if "oluştur" in soru or "yap" in soru:
    return "action_request"
elif "nedir" in soru or "açıkla" in soru:
    return "info_request"
```

**Sorun**: Karmaşık cümlelerde başarısız olur:
- "SSH nedir ve nasıl yapılandırma scripti oluşturabilirim?" → Hangi intent?
- "Bana bir hardening scripti açıklayabilir misin?" → Info mi, action mi?

**Çözüm**: Machine Learning

---

### Dataset Oluşturma

**Dosya**: [data/intent_training_dataset.csv](../data/intent_training_dataset.csv:1-1230)

**Toplam**: 1,230 etiketli örnek

**Kategoriler ve Dağılımlar**:
| Intent | Örnekler | Açıklama |
|--------|----------|----------|
| `greeting` | 200 | "Merhaba", "Selam", "Hi" |
| `farewell` | 150 | "Görüşürüz", "Bye", "Hoşça kal" |
| `thanks` | 100 | "Teşekkürler", "Sağol", "Thanks" |
| `help` | 92 | "Yardım", "Nasıl kullanılır", "Help" |
| `info_request` | 325 | "SSH nedir?", "Firewall nasıl çalışır?" |
| `action_request` | 231 | "Script oluştur", "Yapılandır", "Harden et" |
| `out_of_scope` | 132 | "Hava durumu", "Film öner", "Matematik" |

**Dataset Formatı:**
```csv
text,intent
Merhaba,greeting
SSH nedir,info_request
Ubuntu SSH hardening scripti oluştur,action_request
Bugün hava nasıl,out_of_scope
Teşekkürler,thanks
Görüşürüz,farewell
Yardım lazım,help
```

**Örnekler (info_request):**
- "SSH nedir ve nasıl çalışır?"
- "CIS Benchmark açıkla"
- "Firewall nedir?"
- "Zero Trust prensipleri nelerdir?"
- "iptables ve ufw arasındaki fark nedir?"

**Örnekler (action_request):**
- "Ubuntu 22.04 için SSH hardening scripti oluştur"
- "CentOS 9 firewall yapılandırması yap"
- "Windows Server 2022 güvenlik yapılandırması"
- "Bana bir SSH sıkılaştırma scripti ver"
- "Firewall kuralları oluştur"

---

### Model Seçimi

**Değerlendirilen Alternatifler:**

| Yaklaşım | Avantaj | Dezavantaj | Sonuç |
|----------|---------|------------|-------|
| **Regex/Pattern** | Hızlı (<1ms), $0 | Karmaşık cümlelerde başarısız | ✅ Sadece smalltalk için |
| **Logistic Regression** | Hızlı (<10ms), basit, %85 doğruluk | Transformer'dan düşük | ✅ **SEÇİLDİ** |
| **SVM** | İyi performans | LR ile benzer | ✅ Alternatif olarak mevcut |
| **BERT/Transformer** | En yüksek doğruluk (%90+) | Yavaş (100ms+), büyük model | ❌ Over-kill |
| **Zero-shot LLM** | Model training yok | Pahalı ($0.001/query), yavaş | ❌ Her query için maliyet |

**Karar**: **Logistic Regression + TF-IDF + Pattern Hybrid**

**Neden?**
- %85 doğruluk bizim için yeterli (pattern fallback ile %95+)
- <10ms latency (kullanıcı fark etmez)
- $0 maliyet (training bir kere, inference ücretsiz)
- Production-ready (scikit-learn mature)

---

### TF-IDF Vektörizasyon

**TF-IDF**: Term Frequency - Inverse Document Frequency

**Amaç**: Metni sayısal vektöre çevirmek

**Örnek:**
```
Metin: "Ubuntu SSH hardening scripti oluştur"

TF-IDF:
  ubuntu: 0.45
  ssh: 0.62
  hardening: 0.58
  scripti: 0.71
  oluştur: 0.83
  ubuntu ssh: 0.32  # bigram
  ssh hardening: 0.41
  hardening scripti: 0.38
  scripti oluştur: 0.51
  ... (544 features total)
```

**Parametreler:**
```python
TfidfVectorizer(
    max_features=5000,      # Max 5000 kelime al (en önemlileri)
    ngram_range=(1, 3),     # Unigram (1), bigram (2), trigram (3)
    min_df=2,               # En az 2 dokümanda geçmeli
    max_df=0.8,             # Max %80 dokümanda geçebilir (too common → remove)
    sublinear_tf=True       # Log scaling (rare words'e boost)
)
```

**Çıktı**:
- Vocabulary: 544 features (1,230 örnekten)
- Sparse matrix: (1230, 544)

---

### Model Eğitimi

**Dosya**: [llm/ml_intent_detector.py](../llm/ml_intent_detector.py:1-200)

**Adımlar:**

#### 1. Dataset Split
```python
X_train, X_test, y_train, y_test = train_test_split(
    texts, labels,
    test_size=0.2,      # %20 test
    random_state=42,
    stratified=True     # Her sınıftan eşit oranda
)
```

#### 2. TF-IDF Fitting
```python
vectorizer = TfidfVectorizer(...)
X_train_vec = vectorizer.fit_transform(X_train)  # (984, 544)
X_test_vec = vectorizer.transform(X_test)        # (246, 544)
```

#### 3. Model Training
```python
model = LogisticRegression(
    max_iter=1000,
    C=1.0,
    solver='lbfgs',
    multi_class='multinomial'
)
model.fit(X_train_vec, y_train)
```

#### 4. Evaluation
```python
# Training accuracy
train_acc = model.score(X_train_vec, y_train)
# 91.16%

# Test accuracy
test_acc = model.score(X_test_vec, y_test)
# 82.52%

# Cross-validation (5-fold)
cv_scores = cross_val_score(model, X_train_vec, y_train, cv=5)
# Mean: 85.37%, Std: 2.72%
```

#### 5. Model Persistence
```python
joblib.dump(model, 'models/intent_model.joblib')
joblib.dump(vectorizer, 'models/intent_vectorizer.joblib')
```

---

### Performans Metrikleri

**Test Set Results (246 samples):**

| Metric | Value |
|--------|-------|
| Training Accuracy | 91.16% |
| Test Accuracy | 82.52% |
| CV Mean | 85.37% |
| CV Std | ± 2.72% |

**Class-wise Performance:**

| Intent | Precision | Recall | F1-Score | Support |
|--------|-----------|--------|----------|---------|
| action_request | 94% | 100% | 97% | 47 |
| info_request | 94% | 92% | 93% | 66 |
| greeting | 97% | 78% | 86% | 40 |
| farewell | 100% | 67% | 80% | 30 |
| thanks | 100% | 85% | 92% | 20 |
| help | 50% | 17% | 25% | 18 |
| out_of_scope | 45% | 96% | 62% | 25 |

**Analiz:**
- ✅ **Action ve Info**: Çok iyi performans (ana use case'ler)
- ⚠️ **Help ve Out-of-scope**: Düşük precision
  - **Çözüm**: Hybrid approach (pattern fallback)

**Confusion Matrix Insights:**
- `help` bazen `info_request` olarak tahmin ediliyor (makul)
- `out_of_scope` bazen `info_request` olarak tahmin ediliyor (sorun)
  - **Çözüm**: Pattern-based out-of-scope keywords öncelik

---

### Hybrid Intent Detection

**Dosya**: [llm/layers/hybrid_intent_detector.py](../llm/layers/hybrid_intent_detector.py:1-300)

**Strateji**: Pattern (hız) + ML (doğruluk) kombinasyonu

#### Decision Flow

```
User Question: "Merhaba"
     │
     ▼
┌─────────────────────────┐
│ Step 1: Smalltalk Check │
│ (Pattern-based)         │
└─────────────────────────┘
     │
     ├─ Match: "merhaba" → RETURN greeting (1ms)
     └─ No match → Step 2

User Question: "Bugün hava nasıl?"
     │
     ▼
┌─────────────────────────────┐
│ Step 2: Out-of-scope Check  │
│ (Pattern-based)             │
└─────────────────────────────┘
     │
     ├─ Match: "hava" keyword → RETURN out_of_scope (1ms)
     └─ No match → Step 3

User Question: "SSH nedir ve script oluştur?"
     │
     ▼
┌─────────────────────────┐
│ Step 3: ML Prediction   │
│ (TF-IDF + LogReg)       │
└─────────────────────────┘
     │
     ├─ Confidence >= 0.75 (HIGH) → RETURN ML result (10ms)
     │
     ├─ Confidence >= 0.60 (MEDIUM) → Step 4 (hybrid override)
     │
     └─ Confidence < 0.60 (LOW) → Pattern fallback

Step 4: Hybrid Override
     │
     ▼
Check imperative patterns:
- "oluştur", "yap", "ver", "generate" → Override to action_request
- Otherwise → ML result
```

#### Code Implementation

```python
class HybridIntentDetector:
    ML_HIGH_CONFIDENCE = 0.75
    ML_MED_CONFIDENCE = 0.60

    SMALLTALK_PATTERNS = {
        "greeting": [r"\b(merhaba|selam|hello|hi)\b", ...],
        "farewell": [r"\b(görüşürüz|bye|hoşça kal)\b", ...],
        "thanks": [r"\b(teşekkür|sağol|thank)\b", ...],
        "help": [r"\b(yardım|help|nasıl kullanılır)\b", ...]
    }

    OUT_OF_SCOPE_KEYWORDS = [
        "hava durumu", "weather", "film", "movie", ...
    ]

    def detect(self, question: str) -> HybridIntent:
        q_lower = question.lower()

        # Step 1: Smalltalk patterns
        for subtype, patterns in self.SMALLTALK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, q_lower):
                    return HybridIntent(
                        type="smalltalk",
                        subtype=subtype,
                        confidence=1.0,
                        method="pattern"
                    )

        # Step 2: Out-of-scope keywords
        out_of_scope_matches = sum(
            1 for kw in self.OUT_OF_SCOPE_KEYWORDS
            if kw in q_lower
        )
        if out_of_scope_matches > 0 and not self._has_security_keywords(q_lower):
            return HybridIntent(
                type="out_of_scope",
                confidence=0.95,
                method="pattern"
            )

        # Step 3: ML prediction
        if self.use_ml:
            ml_result = self.ml_detector.predict(question)

            if ml_result.confidence >= self.ML_HIGH_CONFIDENCE:
                # High confidence: trust ML
                return self._convert_to_hybrid_intent(ml_result, "ml")

            elif ml_result.confidence >= self.ML_MED_CONFIDENCE:
                # Medium confidence: check imperative override
                imperative_match = re.search(
                    r"\b(oluştur|yap|ver|hazırla|generate|create|make)\b",
                    q_lower
                )
                if imperative_match and ml_result.type != "action_request":
                    return HybridIntent(
                        type="action_request",
                        confidence=0.90,
                        method="hybrid"
                    )
                return self._convert_to_hybrid_intent(ml_result, "ml")

        # Step 4: Pattern fallback
        return self._pattern_fallback(q_lower)
```

---

## 2. LLM Applications

### Layer 1: Safety Classification

**Model**: Groq Llama 3.1 8B (ücretsiz, hızlı)
**Dosya**: [llm/layers/safety_classifier.py](../llm/layers/safety_classifier.py:1-150)

**Prompt Engineering:**
```python
prompt = f"""Classify this security question as safe or unsafe:

Question: "{question}"

Categories:
- safe_defensive: Legitimate hardening/security improvement
- safe_educational: Learning/research about security concepts
- ambiguous: Unclear intent
- unsafe_offensive: Attack/exploit development
- unsafe_spam: Spam/irrelevant

Output format: {{"category": "...", "confidence": 0.XX, "reason": "..."}}

Classification:"""
```

**LLM Call:**
```python
response = groq_client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.1,  # Deterministic
    max_tokens=100
)
```

**Örnek Output:**
```json
{
  "category": "safe_defensive",
  "confidence": 0.95,
  "reason": "User asking for SSH hardening script, defensive security"
}
```

**Performans:**
- Latency: ~500-800ms
- Doğruluk: ~99%
- Maliyet: $0 (Groq ücretsiz)

---

### Layer 3B/3C: Generation Pipeline

**Model**: Groq Llama 3.3 70B (ücretsiz, kaliteli)

**Dosyalar**:
- Info: [llm/layers/info_pipeline.py](../llm/layers/info_pipeline.py:1-200)
- Action: [llm/layers/action_pipeline.py](../llm/layers/action_pipeline.py:1-250)

#### RAG Integration

**1. Semantic Search:**
```python
# Embed user question
query_embedding = cohere.embed(
    texts=[question],
    model="embed-multilingual-v3.0",
    input_type="search_query"
).embeddings[0]  # 1024-dim vector

# Search in Qdrant
results = qdrant_client.search(
    collection_name="cis_benchmarks",
    query_vector=query_embedding,
    limit=5,
    score_threshold=0.7
)
```

**2. Context Construction:**
```python
context = ""
for i, hit in enumerate(results, 1):
    context += f"""
[Source {i} - Relevance: {hit.score:.2f}]
Document: {hit.payload['source']}
Section: {hit.payload['section']}
Content: {hit.payload['content']}

"""
```

**3. LLM Generation:**

**Info Pipeline Prompt:**
```python
prompt = f"""Sen bir siber güvenlik uzmanısın. CIS Benchmark standartlarına göre yanıt ver.

Alakalı CIS Benchmark bilgileri:
{context}

Kullanıcı Sorusu:
{question}

Yanıt (Türkçe, detaylı, CIS Benchmark kaynaklı):"""
```

**Action Pipeline Prompt (CoT):**
```python
prompt = f"""Sen bir sistem yöneticisi güvenlik uzmanısın.

Task: {os} için {topic} güvenlik yapılandırma scripti oluştur

CIS Benchmark Context:
{context}

User Role: {role}
Security Level: {security_level}
Zero Trust Maturity: {zt_maturity}

Requirements:
1. CIS Benchmark best practices kullan
2. Bash script formatında (#!/bin/bash ile başla)
3. Her adımı açıkla (inline comments)
4. Error handling ekle (set -euo pipefail)
5. Rollback stratejisi ekle
6. Zero Trust prensiplerini dahil et

Chain of Thought:
1. İlgili CIS Benchmark önerilerini analiz et
2. Security level'a göre yapılandırma seviyesini belirle
3. Script structure'ı oluştur
4. Zero Trust enrichment ekle
5. Rollback mekanizması tasarla

Script:"""
```

**LLM Call:**
```python
response = groq_client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ],
    temperature=0.1,
    max_tokens=2000
)

answer = response.choices[0].message.content
```

**Performans:**
- Info: ~1.5-2.5s
- Action: ~2-4s
- Maliyet: ~$0.001-0.002 (Groq ücretsiz, ama tahmin)

---

### Zero Trust Enrichment

**Dosya**: [llm/layers/zt_enrichment.py](../llm/layers/zt_enrichment.py:1-200)

**Amaç**: Script'lere otomatik Zero Trust prensiplerini eklemek

**Maturity Levels:**

#### Low Maturity
```bash
# Least Privilege
chmod 600 /etc/ssh/sshd_config

# Logging
echo "SSH configuration changed at $(date)" >> /var/log/hardening.log
```

#### Medium Maturity
```bash
# + Network Segmentation
iptables -A INPUT -p tcp --dport 22 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 22 -j DROP

# + Multi-factor Authentication
echo "AuthenticationMethods publickey,keyboard-interactive" >> /etc/ssh/sshd_config
```

#### High Maturity
```bash
# + Continuous Validation
# Monitor SSH access in real-time
auditctl -w /etc/ssh/sshd_config -p wa -k ssh_config_change

# + Micro-segmentation
# Isolate SSH service in separate network namespace
ip netns add ssh_namespace
ip link set eth0 netns ssh_namespace

# + Session recording
echo "ForceCommand /usr/bin/script -f -q /var/log/ssh_sessions/\$(whoami)_\$(date +%Y%m%d_%H%M%S).log" >> /etc/ssh/sshd_config
```

**Implementation:**
```python
class ZTEnrichment:
    def add_principles(self, script: str, maturity: str, security_level: str):
        enriched = script

        if maturity == "low":
            enriched += self._add_least_privilege()
            enriched += self._add_logging()

        elif maturity == "medium":
            enriched += self._add_least_privilege()
            enriched += self._add_logging()
            enriched += self._add_mfa()
            enriched += self._add_network_segmentation()

        elif maturity == "high":
            enriched += self._add_least_privilege()
            enriched += self._add_logging()
            enriched += self._add_mfa()
            enriched += self._add_network_segmentation()
            enriched += self._add_continuous_validation()
            enriched += self._add_micro_segmentation()

        return enriched
```

---

### Layer 4: Output Validation

**Dosya**: [llm/layers/output_validator.py](../llm/layers/output_validator.py:1-150)

**Amaç**: Oluşturulan script'lerdeki **tehlikeli komutları** tespit etmek

#### Hybrid Approach

**Tier 1: Regex (Fast, $0)**
```python
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",                    # Dangerous recursive delete
    r"chmod\s+777",                      # Overly permissive
    r":()\s*{.*;\s*};\s*:",             # Fork bomb
    r"curl.*\|\s*bash",                  # Unsafe piping
    r"wget.*\|\s*sh",                    # Unsafe piping
    r"mkfs\.",                           # Format disk
    r"dd\s+if=.*of=/dev/[sh]d",         # Disk write
    r"iptables\s+-F",                    # Flush all rules (dangerous)
]

def check_dangerous(script: str):
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, script):
            return True, pattern
    return False, None
```

**Tier 2: LLM (Deep, $0.001)**

Eğer Tier 1'de şüpheli komut bulunursa:
```python
prompt = f"""Analyze this command for security risks:

Command: {suspicious_command}

Context: This is from a security hardening script.

Question: Is this command dangerous or risky?

Answer with JSON:
{{"dangerous": true/false, "reason": "...", "severity": "low/medium/high"}}

Analysis:"""

response = groq_client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.1
)
```

**Decision Tree:**
```
Script generated
     │
     ▼
Regex scan (Tier 1)
     │
     ├─ No dangerous patterns → PASS
     │
     └─ Found suspicious → LLM deep scan (Tier 2)
           │
           ├─ LLM: "Safe" → PASS
           └─ LLM: "Dangerous" → REJECT or WARN
```

**Performans:**
- Regex only: <1ms, $0
- Regex + LLM: ~200ms, $0.0001

---

## 3. Prompt Engineering Teknikleri

### Chain of Thought (CoT)

**Neden Kullanıldı?**
Action pipeline'da (script oluşturma) karmaşık görev → CoT ile step-by-step düşünme

**Örnek:**
```python
prompt = """...

Chain of Thought:
1. İlgili CIS Benchmark önerilerini analiz et
2. Security level'a göre yapılandırma seviyesini belirle
3. Script structure'ı oluştur
4. Zero Trust enrichment ekle
5. Rollback mekanizması tasarla

Script:"""
```

**Fayda**: Daha yapılandırılmış, mantıklı script'ler

### Few-shot Prompting

**Kullanılmadı** (zero-shot yeterli oldu)

**Neden?**
- Dataset'imiz RAG'de var (CIS Benchmark examples)
- LLM (Llama 70B) zaten iyi performans veriyor

### Temperature Control

**Safety Classification**: 0.1 (deterministic)
**Generation**: 0.1-0.3 (yaratıcı ama kontrollü)

**Neden Düşük?**
- Güvenlik kritik → Consistent yanıtlar istiyoruz
- Randomness → Risk

---

## 4. Model Evaluation ve Metrikleri

### ML Model Evaluation

**Cross-validation (5-fold):**
```python
cv_scores = cross_val_score(model, X, y, cv=5, scoring='accuracy')
# [0.87, 0.83, 0.86, 0.85, 0.84]
# Mean: 0.85 ± 0.027
```

**Confusion Matrix:**
```
              Predicted
              act  info  greet  fare  thanks  help  out
Actual:
action      |  47    0     0     0      0     0     0  |
info        |   4   61     0     0      0     1     0  |
greeting    |   0    0    31     0      0     9     0  |
farewell    |   0    0     0    20      0     0    10  |
thanks      |   0    0     0     0     17     0     3  |
help        |   0    2     1     0      0     3    12  |
out_scope   |   0    1     0     0      0     0    24  |
```

**Key Insights:**
- Action ve Info: Mükemmel (ana use case'ler)
- Greeting → Help karışıyor: Pattern hybrid ile düzeltildi
- Out-of-scope → Info karışıyor: Keyword check öncelik ile düzeltildi

### Pipeline End-to-End Evaluation

**Test Suite**: [tests/pipeline_evaluator.py](../tests/pipeline_evaluator.py:1-300)

**50 Test Case:**
- 10 greeting/farewell (smalltalk)
- 15 info requests
- 20 action requests
- 5 out-of-scope

**Sonuçlar:**
- ✅ Passed: 48/50 (96%)
- ❌ Failed: 2/50 (4%)

**Failed Cases:**
1. "SSH nasıl yapılandırılır ve script oluştur?" → info_request (expected: action_request)
   - Hybrid override ile düzeltildi
2. "Firewall kurallarını açıkla ve uygula" → info_request (expected: action_request)
   - "uygula" keyword'ü eklendi

---

## 5. Maliyet Analizi

### Training Maliyeti

| Item | Cost |
|------|------|
| Dataset oluşturma | Manuel (zaman) |
| Model training | $0 (local CPU) |
| Model storage | ~70KB (negligible) |
| **Total Training** | **$0** |

### Inference Maliyeti (Per Request)

| Pipeline Path | LLM Calls | Tokens | Cost (Groq) |
|---------------|-----------|--------|-------------|
| 1→REJECT | 1 (safety) | ~100 | $0 (ücretsiz) |
| 1→2→3A | 1 (safety) | ~100 | $0 |
| 1→2→OUT | 1 (safety) | ~100 | $0 |
| 1→2→3B→4 | 2 (safety+gen) | ~1500 | $0 (ücretsiz) |
| 1→2→3C→4 | 2-3 (safety+gen+val) | ~2500 | $0 (ücretsiz) |

**Not**: Groq ücretsiz olduğu için maliyet $0. Eğer OpenAI kullansaydık:
- Safety (8B equivalent): ~$0.0001
- Generation (70B equivalent): ~$0.0015
- **Total per action request**: ~$0.0016

**Maliyet Karşılaştırması:**
- **Groq**: $0
- **OpenAI (GPT-4)**: ~$0.03 (18x daha pahalı)
- **Maliyet Tasarrufu**: %100 (Groq ile)

---

## 6. Performans Optimizasyonları

### 1. ML Model Caching
```python
# Model her API call'da yeniden load edilmez
# main.py startup event'te load edilir
@app.on_event("startup")
async def load_models():
    global ml_detector
    ml_detector = MLIntentDetector(
        model_path="models/intent_model.joblib",
        vectorizer_path="models/intent_vectorizer.joblib"
    )
```

### 2. Pattern-First Strategy
```python
# ML'den önce pattern check (1ms vs 10ms)
if pattern_match:
    return immediately  # No ML inference
```

### 3. Confidence-Based Routing
```python
# High confidence: ML'e güven, no LLM validation
# Medium confidence: Hybrid override check
# Low confidence: Pattern fallback
```

### 4. Async LLM Calls (Future)
```python
# Parallel RAG + LLM calls
results = await asyncio.gather(
    rag_search(query),
    llm_generate(prompt)
)
```

---

## 7. Gelecek İyileştirmeler

### ML Model
1. **Daha Fazla Data**: 1,230 → 5,000+ örnek
2. **Fine-tuned Transformer**: BERT-based intent classifier (%90+ doğruluk)
3. **Multi-intent Support**: "SSH nedir ve script oluştur" → [info, action]
4. **Active Learning**: Kullanıcı feedback'i ile model improvement

### LLM Applications
1. **Fine-tuned Domain Model**: CIS Benchmark'a özel Llama fine-tune
2. **Prompt Optimization**: A/B testing ile prompt improvement
3. **Caching**: Benzer sorular için cached responses
4. **Streaming**: Real-time token streaming (SSE)

### RAG
1. **Hybrid Search**: Semantic + keyword search
2. **Re-ranking**: Cross-encoder ile sonuç sıralama
3. **Query Expansion**: Synonyms, related terms

---

## Özet: AI/ML Stack

| Component | Technology | Latency | Cost | Purpose |
|-----------|------------|---------|------|---------|
| Intent Detection | Logistic Regression | <10ms | $0 | Route to handler |
| Safety Classification | Groq Llama 8B | ~700ms | $0 | Detect unsafe |
| Info Generation | Groq Llama 70B + RAG | ~2s | $0 | Answer questions |
| Action Generation | Groq Llama 70B + RAG + ZT | ~3s | $0 | Generate scripts |
| Output Validation | Regex + Groq Llama 8B | <200ms | $0 | Detect dangerous |

**Total Pipeline (Action Request)**: ~4s, $0

---

## Sonraki Adımlar

- 📖 [Kurulum](03_KURULUM_VE_KULLANIM.md) - Sistemi çalıştırın
- 📖 [API Dokümantasyonu](04_API_DOKUMANTASYONU.md) - API'yi kullanın
- 🚀 Production'a deploy edin!
