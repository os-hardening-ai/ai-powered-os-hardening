# 19 — Agentic AI ve Self-Verify (Üret → Doğrula → Düzelt)

> Bu doküman projedeki **agentic** bileşeni (İP-6 Görev Planlayıcı + İP-7 çok-adımlı
> ajan) ve son eklenen **sözdizimi self-verify / self-correct döngüsünü** anlatır.
> İlgili: [02_PIPELINE_VE_ROUTELAR](02_PIPELINE_VE_ROUTELAR.md),
> [18_QUOTA_VE_PERFORMANS_OPTIMIZASYONU](18_QUOTA_VE_PERFORMANS_OPTIMIZASYONU.md).

---

## 1. Agentic AI nedir? (kısa)

Sıradan bir LLM **cevap verir**. **Agentic** bir sistem bir **hedef** alır →
**plan yapar** → **araç çağırır** (tool-use: kural getir, script üret, doğrula) →
**sonucu gözlemler** → gerekirse **kendini düzeltip** hedefe ulaşana kadar döner.

> Üç bileşen: **otonomi + araç kullanımı + gözlem-düzeltme döngüsü.**

Bu projede agent **tam otonom değildir** — gerçek bir makinede komut çalıştırmaz
(bilinçli güvenlik kararı). Bunun yerine **uçtan uca doğrulanmış, çalıştırılabilir
bir artifact** (script/playbook) üretir ve insana sunar. Otonomi "üret→doğrula→düzelt"
döngüsündedir, "uygula"da değil.

---

## 2. Projedeki ajanlar

| Kod | Modül | Görev |
|-----|-------|-------|
| **İP-6** | `llm/agents/task_planner.py` — `TaskPlanner` | Doğal dil hedefini CIS kural seçimine + topolojik sıraya + çakışma tespitine çevirir |
| **İP-7** | `llm/agents/hardening_agent.py` — `HardeningAgent` | İP-6 planını çok-adımlı tool-use ile **doğrulanmış script'e** dönüştürür |

**Uç noktalar** (`api/router_agent.py`):

| Method | Path | Açıklama | Yetki |
|--------|------|----------|-------|
| `POST` | `/api/agent/plan` | İP-6: hedef → kural planı (sıralı + çakışmalı) | — |
| `POST` | `/api/agent/harden` | İP-7: plan → script üret → self-verify → (gerekirse) onar | `sysadmin` / `security` |

> LLM erişilemezse her iki uç da **deterministik** (RuleEngine + ArtifactGenerator)
> çalışmaya devam eder; LLM yalnız planlama, opsiyonel özet ve son-çare sözdizimi
> onarımı için kullanılır. LLM çağrıları chat ile **aynı lane havuzunu** kullanır
> (bkz. [18](18_QUOTA_VE_PERFORMANS_OPTIMIZASYONU.md)).

---

## 3. Çok-adımlı tool-use döngüsü (İP-7)

```
Hedef: "SSH ve parola politikasını sıkılaştır"  (os=ubuntu_24_04, level=balanced, fmt=bash)
   │
   ▼
[1] PLAN      → TaskPlanner: hedefe uygun kuralları seç + topolojik sırala + çakışma
   │            (boş plan → "uygulanabilir kural yok", success=False)
   ▼
[2] COLLECT   → RuleEngine: seçilen kuralların tam tanımlarını (audit+remediation) topla
   ▼
[3] GENERATE  → ArtifactGenerator: tek-shebang, fonksiyon-wrap, yedekli script üret
   ▼
[4] VERIFY    → OutputValidator: TEHLİKELİ KOMUT taraması (rm -rf /, mkfs, dd of=, …)
   │            geçerli mi?  ── evet ──┐
   │            hayır                  │
   ▼                                   │
[5] REFINE    → tehlikeli komut içeren kuralı ÇIKAR → [2]'ye dön (en fazla max_refine)
   │            (gözlem→akıl yürütme→yeniden eylem)
   └──────────────────────────────────┘
   ▼
[6] SYNTAX    → bash -n / yaml.load ile FİİLEN doğrula
   │            geçerli mi?  ── evet ──┐
   │            hayır                  │
   ├─ (a) izole et: hangi kural TEK BAŞINA patlıyor → çıkar → yeniden üret (deterministik)
   ├─ (b) hâlâ bozuk + LLM var → LLM-repair (son çare, TAM yeniden-doğrulamalı)
   └─ hâlâ bozuk → bozuk script'i SUNMA: success=False + issue (şeffaf)
   ▼                                   │
SUMMARIZE  ← ────────────────────────┘
   ▼
AgentResult {success, artifact, issues, steps[], summary}
```

Her adım bir **`AgentStep`** olarak kaydedilir (`name, tool, detail, ok`) → çıktı
**açıklanabilir ve denetlenebilir** bir iz taşır (UI'da "Ajan adımları" olarak gösterilir).

---

## 4. Self-Verify: iki bağımsız doğrulama katmanı

Ajan ürettiği script'i **iki kez** ve **iki farklı açıdan** kendi kendine doğrular:

### Katman A — Güvenlik (Step 4/5: VERIFY → REFINE)
- **Araç:** `OutputValidator` (regex, LLM'siz) — `DANGEROUS_COMMANDS` listesi.
- **Tetik:** `rm -rf /`, `mkfs`, `dd of=/dev/…`, fork-bomb, `chmod -R 777 /` …
- **Aksiyon:** tehlikeli komut içeren kuralı **çıkar**, kalanları yeniden üret.
  Tüm kurallar tehlikeliyse → güvenli script üretilemedi (`success=False`), önceki
  tehlikeli artifact **döndürülmez**.

### Katman B — Sözdizimi (Step 6: SYNTAX) — **YENİ**
GENERATE deterministik **geçerli iskelet** üretir (tek shebang, `set -euo pipefail`,
her kural `apply_<id>()` fonksiyonunda, `sshd -t` reload guard'ı). Ama bir kuralın
**ham CIS remediation içeriği** bozuk olabilir (dengesiz tırnak/parantez) → tüm script
`bash -n`'de patlar. Bu katman onu yakalar:

| Format | Doğrulayıcı | Not |
|--------|-------------|-----|
| `bash` | `bash -n` (subprocess, 10s timeout) | bash yoksa (ör. Windows) **atlanır** → "doğrulanamadı" ≠ "geçersiz" |
| `ansible` | `yaml.safe_load` | `safe_dump` zaten geçerli üretir; LLM-repair çıktısına karşı savunma |
| `powershell` / `reg` / `gpo` | — | güvenilir yerel doğrulayıcı yok → atlanır |

**Onarım sırası (en güvenliden en riskliye):**

1. **(a) Deterministik kural-izolasyonu** — her kuralı **tek başına** üretip
   `bash -n`'den geçir → tek başına patlayanın id'sini bul → **çıkar → yeniden üret**.
   Generator her kuralı kendi fonksiyonuna sardığı için suçlu kesin izole edilir.
   *LLM yok, semantik bozulmaz, kesinti riski yok.*
2. **(b) LLM-repair (son çare)** — izolasyon çözemezse (ör. iskelet düzeyi hata) ve
   LLM varsa + script makul boyuttaysa (≤6000 char), hatayı LLM'e **geri besle**,
   "sadece sözdizimini düzelt, komut ekleme/çıkarma" iste. Dönen script **yeniden**
   hem tehlikeli-komut hem `bash -n`'den geçirilir; **ikisi de geçerse** kabul edilir.
3. **Hiçbiri çözemezse** → bozuk script **sessizce sunulmaz**: `success=False` +
   `issues`'a "Sözdizimi doğrulaması başarısız" eklenir.

> **Neden izolasyon LLM'den önce?** Güvenlik script'i LLM tarafından sessizce
> yeniden yazılmamalı: (i) çıktı token limitinde **kesilme → veri kaybı** riski,
> (ii) **anlamsal kayma → yanlış sıkılaştırma** riski. Bozuk bir kuralı çıkarıp
> şeffafça bildirmek, LLM'in script'i "tahmin ederek düzeltmesinden" daha sorumludur.
> LLM-repair yalnızca deterministik yol tıkandığında, **tam yeniden-doğrulamayla**
> devreye girer.

---

## 5. Maliyet / kota etkisi

| Durum | Ekstra LLM çağrısı |
|-------|--------------------|
| Sözdizimi **geçerli** (tipik) | **0** — yalnızca yerel `bash -n` |
| Bozuk → **deterministik izolasyon** çözer | **0** — yerel araçlar |
| Bozuk → izolasyon çözemez → **LLM-repair** | **+1** (yalnız bu nadir durumda) |

Yani happy-path'te **sıfır** ek maliyet; döngü yalnızca gerçekten gerektiğinde ve
en fazla `max_syntax_fix` kez LLM'e başvurur. Cerebras **5 istek/dk** darboğazını
(bkz. [18](18_QUOTA_VE_PERFORMANS_OPTIMIZASYONU.md)) korur.

---

## 6. API örnekleri

### `POST /api/agent/harden` — istek
```json
{
  "goal": "SSH ve parola politikasını sıkılaştır",
  "os_target": "ubuntu_24_04",
  "security_level": "balanced",
  "format": "bash"
}
```

### Yanıt (kısaltılmış)
```json
{
  "success": true,
  "goal": "SSH ve parola politikasını sıkılaştır",
  "format": "bash",
  "rule_count": 6,
  "artifact_content": "#!/usr/bin/env bash\nset -euo pipefail\n...",
  "issues": [],
  "steps": [
    {"name": "plan",      "tool": "TaskPlanner",       "detail": "6 kural seçildi, 0 olası çakışma", "ok": true},
    {"name": "collect",   "tool": "RuleEngine",        "detail": "6 kural tanımı toplandı",          "ok": true},
    {"name": "generate",  "tool": "ArtifactGenerator", "detail": "6 kural → bash script (...)",       "ok": true},
    {"name": "verify",    "tool": "OutputValidator",   "detail": "güvenli",                           "ok": true},
    {"name": "syntax",    "tool": "bash -n / yaml.load","detail": "sözdizimi geçerli",                "ok": true},
    {"name": "summarize", "tool": "LLM",               "detail": "...",                               "ok": true}
  ],
  "summary": "'SSH ve parola politikasını sıkılaştır' hedefi için 6 kurallı bir bash sıkılaştırma planı üretildi ve doğrulandı.",
  "provider": "cerebras",
  "latency_s": 2.1
}
```

> `steps` dizisi **açıklanabilirlik** için kritiktir: bir kural sözdizimi nedeniyle
> çıkarıldıysa `refine / syntax-isolate` adımı + `summary`'deki "çıkarıldı" notu bunu
> şeffafça gösterir.

---

## 7. Test kapsamı

`tests/integration/test_hardening_agent.py` (18 test):

- **TestHappyPath** — uçtan uca doğrulanmış script, ansible formatı.
- **TestRefineLoop** — tehlikeli kural çıkarılır, çift `verify` adımı.
- **TestSummarySync** — özet **üretilen** kural sayısını yansıtır (plan'ı değil).
- **TestEdgeCases** — hepsi tehlikeli/boş plan/max_refine=0.
- **TestSyntaxSelfVerify** *(yeni)* — happy-path'te `syntax` adımı; bozuk kural
  izolasyonu + çıkarma; ansible `yaml.load` doğrulaması; LLM-repair **kabul** (geçerli
  onarım) ve **ret** (hâlâ bozuk → `success=False` + issue) yolları.
- **TestSyntaxHelpers** *(yeni)* — `_strip_code_fence`, doğrulanamayan format atlama,
  bozuk YAML tespiti.

```bash
python -m pytest tests/integration/test_hardening_agent.py -q   # 18 passed
```

---

## 8. Sınırlar / gelecek

- **PowerShell/Registry/GPO sözdizimi** yerel olarak doğrulanmıyor (pwsh genelde yok).
  İleride opsiyonel `pwsh -NoProfile -Command` parse adımı eklenebilir.
- **`sshd -t` semantik doğrulaması** üretilen script'in **içine** gömülüdür (reload
  öncesi config testi) — bu çalışma-zamanı guard'ı; ajan onu üretim öncesi *çalıştırmaz*
  (hedef makineye erişmez, bilinçli).
- **Çalıştırma (apply)** kapsam dışıdır (tam otonomi = yüksek risk). Ajan yalnızca
  doğrulanmış artifact üretir; uygulama kararını insan verir.
- LLM-repair script'i 6000 char'la sınırlıdır (token güvenliği) — daha büyük script'ler
  yalnız deterministik izolasyonla onarılır.
