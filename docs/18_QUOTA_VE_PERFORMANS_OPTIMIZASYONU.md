# 18 — Quota Darboğazı, Performans Optimizasyonu ve Yük Dengeleme

> Bu doküman, sistemin **LLM sağlayıcı istek-limiti (quota)** kaynaklı performans
> darboğazının tespit edilip çözüldüğü çalışmanın tam kaydıdır: karşılaşılan sorunlar,
> ölçüm-odaklı (eval-driven) teşhis, uygulanan çözümler ve ölçülen sonuçlar.

---

## 1. Başlangıç durumu ve semptomlar

Aktif LLM sağlayıcısı **Cerebras `gpt-oss-120b`** (free tier). Gözlemlenen semptomlar:

- RAG'li `info` istekleri **~55s**, bazı `action` istekleri **65–95s** ve **timeout (504)**.
- Aynı sorunun tekrarında süre **1.3s ↔ 65s** arası savruluyordu (deterministik değil).
- 100 soruluk canlı eval'de **%73 başarı, 14 timeout** (kötü bir pencerede).

### Kök neden: 5 istek/dakika + çok-çağrılı pipeline
Cerebras free tier limiti **5 istek/dk + 30k token/dk**. Kritik bulgu: **token değil, istek/dk darboğaz** (tüm 429'lar `"Requests per minute limit exceeded"`).

Tek bir chat isteği **birden çok LLM çağrısı** yapıyordu:

| Adım | Çağrı |
|------|-------|
| Layer-1 Safety | 1 (LLM) |
| QueryPlanner (decompose+HyDE+stepback) | 3 (paralel) |
| FilterAgent | 0–1 |
| Generation | 1 |
| ClaimVerifier | 1–N |
| **Toplam (medium info)** | **~6** |

→ **Tek istek bile 5/dk limitini tek başına aşıyordu.** Aşımda Cerebras `429 + Retry-After` (30–60s backoff) → gözlenen "65s LLM" aslında **rate-limit backoff'uydu**, model yavaşlığı değil. (`pipeline_metrics.log`'da `llm=65s` görünen değer, generation adımının fallback-zinciri + backoff dahil toplamıydı.)

---

## 2. Ölçüm-odaklı teşhis (eval-driven)

100 çeşitli soru (smalltalk / kapsam-dışı / RDP / SSH / firewall / ZTA / action /
CIS / tanım) canlı API'ye sorulup performans + doğruluk + cevap kaydedildi
(`scripts`/geçici eval). Üç sürüm karşılaştırıldı:

| Metrik | v1 (fix yok) | v2 (ara) | **v3 (tüm fix)** |
|--------|------|------|------|
| Başarılı | 98/100 | 73/100 | **100/100** |
| Timeout (504) | 2 | 14 | **0** |
| Ort. gecikme | 21.7s | 29.0s | **7.0s** |
| p50 | 12.5s | 16.1s | **4.6s** |
| p95 | 75s | 77s | **23.3s** |
| max | 92s | 95s | **34.9s** |
| Kapsam-dışı doğru | 5/10 | 3/10 | **10/10** |
| RDP kapsam-içi | 10/10 | 8/10 | **10/10** |
| Maliyet | $0.101 | $0.054 | $0.058 |

**Sonuç: ~4× daha hızlı, 0 timeout, %100 başarı, doğruluk tam.**

---

## 3. Uygulanan çözümler

### 3.1. Kritik-yol LLM çağrılarını azalt (3 → 1)
Best-practice: **kritik yolda tek üretim çağrısı**; guardrail ucuz/yerel, kalite-kontrol hat-dışı.

| Değişiklik | Etki | Nerede |
|-----------|------|--------|
| **ClaimVerifier kapatıldı** (`use_claim_verification=false`) | −1 call; kalibrasyon bug'ı da gitti | `config.json` |
| **Yerel safety fast-path** (`fast_local_safety`) | net güvenlik-savunma / net alan-dışı → LLM'siz; saldırgan/dual-use/uzun girdi → LLM'e düşer | `safety_classifier.py` |
| **QueryPlanner yalnız `complex`** | `medium` artık `retrieve_balanced` → 3 paralel call kalkar | `info_pipeline.py` |
| **Action judge/correction kapatıldı** (`use_deep_check=False`) | statik regex güvenlik kalır, 1–2 LLM call gider | `action_pipeline.py` |
| **`max_verification_claims` 4→1→(off)** | verify burst'ü kaldırıldı | `config.json` |
| **Answer cache** (exact-match, TTL, LRU) | tekrar eden soru → **0 call** | `info_pipeline.py` |

**Sonuç:** medium info **6 call → ~1 call** (yalnız generation); tekrar **0 call**.

### 3.2. Lane-tabanlı yük dengeleme (round-robin + fallback)
Tek sağlayıcının 5/dk limiti darboğaz olduğundan, yük **birden çok (provider:model) lane**'e
round-robin dağıtılır → her lane'in **ayrı limiti** → agregat throughput ~lane sayısı katı.
`small` (helper/burst) ve `large` (üretim) havuzları **ayrı**.

- `FallbackLLM`: ilk N sağlayıcıyı her çağrıda döndürür (`LLM_BALANCE_TOP_N`, default 3).
- `LaneLoadBalancer` (yeni): `LLM_SMALL_LANES` / `LLM_LARGE_LANES` env ile açık lane'ler;
  her call round-robin başlar, lane fail ederse (429/timeout) sıradakine düşer.
- Per-call timeout (`CHAIN_LLM_TIMEOUT`, default 30s) → yavaş lane erken iptal → hızlı fallback.

> Detaylı env: bkz. [17_LLM_SAGLAYICI_SECIMI.md](17_LLM_SAGLAYICI_SECIMI.md) ve `.env.example`.

### 3.3. Doğruluk düzeltmeleri (yan bulgular)
- **stream paritesi**: `/api/chat/stream` artık `/api/chat` ile birebir aynı `SecurePipelineV2` (smalltalk "naber" artık RAG güvenlik cevabı dönmüyor).
- **Action parametre**: "tespit edildiyse sorma, boşsa sor" — role/security otomatik dolar, OS yalnız tespit edilemezse sorulur. + pending-param follow-up (sorulan cevabın kapsam-dışına düşmesi engellendi).
- **RDP / kapsam**: yeni `off_topic` safety kategorisi → math/hava `OUT_OF_SCOPE`; `safe_defensive/educational` semantik sinyaliyle "rdp kuralları" gibi sorular kurtarılır (keyword whack-a-mole değil).
- **Refinement hafifletildi**: full re-RAG (≈9 call, ~36s) → mevcut kaynaklara tek küçük-model düzeltme çağrısı.

### 3.4. Gözlemlenebilirlik
- **Token/provider metriği** streaming trafikte de kaydedilir.
- `/metrics` `llm_providers` artık **gerçek lane dağılımını** gösterir (statik config değil).
- **Lane başına `llm_lane_latency_ms` + `llm_lane_failures`** → yavaş/ölü lane tespiti.
- **`latency_by_endpoint`** → chat / agent / rules / rag grubu bazlı gecikme.

---

## 4. Karşılaşılan kritik olaylar (lessons learned)

1. **"65s LLM" yanılgısı**: Süre model hızı sanıldı; aslında rate-limit backoff'uydu. `pipeline_metrics.log` breakdown'u + Cerebras request logları (`429 "requests per minute"`) gerçeği gösterdi.
2. **Metrik yanılgısı ("sadece cerebras")**: Dashboard statik `cfg.llm.default_provider` okuyordu → lane'ler aktifken bile tek sağlayıcı görünüyordu. Gerçek `by_provider` expose edildi.
3. **OpenRouter 402 (kredi)**: Lane'ler eklendikten sonra tüm OpenRouter lane'leri fail etti → loglar `Error 402: "more credits, or fewer max_tokens (requested 2048, can only afford ~229–1719)"`. Key geçerliydi ama **hesapta kredi yetersizdi** (`max_tokens=2048` > karşılanabilir). Çözüm: kredi ekle **veya** `:free` model varyantları. → Yeni `llm_lane_failures` metriği bunu **anında** teşhis etti.
4. **Eval metodolojisi**: 1.5s aralıklı 100-soru eval, çok-çağrılı pipeline ile 5/dk limitini ezip **yanıltıcı yüksek gecikme** üretiyordu (+ prod quota'sını tüketiyordu). Çözüm: ≥3–15s aralık ile ölç; call-azaltma sonrası eval gerçekçi sonuç verdi.

---

## 5. Yapılandırma özeti (bu çalışmayla gelen)

```jsonc
// config/config.json → rag.enhanced
"use_query_planning": true,        // ama yalnız complexity=="complex"te koşar
"use_claim_verification": false,   // kapalı (kalibrasyon + quota); ">=2 desteksiz" disclaimer kapısı
```

```bash
# .env (opsiyonel lane yük dengeleme)
LLM_SMALL_LANES=openrouter:meta-llama/llama-3.2-1b-instruct,openrouter:liquid/lfm-2-24b-a2b,openrouter:mistralai/codestral-2508,openrouter:amazon/nova-micro-v1,sambanova:gemma-3-12b-it
LLM_LARGE_LANES=cerebras:gpt-oss-120b,openrouter:deepseek/deepseek-v4-flash,sambanova:gemma-3-12b-it
OPENROUTER_API_KEY=...   # kredi gerektirir (free değilse) — bkz. 402 notu
SAMBANOVA_API_KEY=...
CHAIN_LLM_TIMEOUT=30     # lane başına timeout (s)
LLM_BALANCE_TOP_N=3      # klasik zincirde round-robin baş sağlayıcı sayısı (1=kapalı)
ANSWER_CACHE_TTL_S=1800  # answer cache TTL (0=kapalı)
```

---

## 6. Kalan iyileştirmeler

- **`off_topic` aşırı agresifliği**: safety LLM bazı güvenlik-bitişik konuları ("parola politikası scripti", "log rotation") yanlışlıkla `off_topic` → kapsam-dışı sayabiliyor. `fast_local_safety` terim setini + off_topic prompt'unu sıkılaştırmak gerek.
- **pending-param follow-up** entegrasyon testi (router_chat, async + tam pipeline mock).
- **OpenRouter `:free` varyantları** veya sürekli kredi — paid model lane'leri kredi tüketir.
