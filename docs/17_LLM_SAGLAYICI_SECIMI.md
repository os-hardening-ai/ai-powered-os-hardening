# 17 — LLM Sağlayıcı Seçimi: Testler, Alternatifler ve Performans

**Güncelleme:** 2026-05-31
**İlgili kod:** `evaluation/provider_benchmark.py`, `llm/clients/registry.py`, `llm/clients/openai_compatible_client.py`, `llm/clients/__init__.py` (FallbackLLM)
**İlgili ölçüm:** [14_DEGERLENDIRME.md](14_DEGERLENDIRME.md) (H3 — P95 < 5sn)

Bu belge, projenin LLM sağlayıcısının **neden ve nasıl** seçildiğini, denenen alternatifleri ve
ampirik performans sonuçlarını belgeler. Amaç: sunumda "neden Cerebras?" / "neden Groq değil?"
sorularına ölçüme dayalı cevap vermek.

---

## 1. Seçim Kriterleri (proje politikası)

1. **Ücretsiz-first:** Tez bütçesi yok → öncelik ücretsiz veya çok düşük ücretli sağlayıcılar.
   Pahalı (OpenAI gpt-4 sınıfı) **dışlandı**.
2. **Hız (H3):** Hedef P95 < 5 sn. Uçtan-uca gecikme kritik (interaktif danışman).
3. **Groundedness/kalite:** CIS/NIST gibi teknik içerikte doğru, kaynak-temelli cevap (İP-5).
4. **Context window:** Uzun RAG bağlamı için geniş pencere avantaj.
5. **Güvenilirlik:** Kararlı erişim; "bazen çalışan" free-tier'lar riskli.

---

## 2. Test Metodolojisi

`evaluation/provider_benchmark.py` ile **ampirik** ölçüm yapıldı:
- **Matris modu:** *Aynı model* (`gpt-oss-120b`) farklı sağlayıcılarda → adil hız kıyası
  (model değil **altyapı** farkını izole eder).
- Her sağlayıcı için gerçek API anahtarıyla: tek çağrı latency, hata/erişim durumu.
- Embedding sabit tutuldu (Novita `qwen3-embedding-8b`, 4096) — kıyas yalnız LLM katmanı.
- Sonuçlar `evaluation/results/` altına loglandı (bench_matrix.log, bench_cheap.log vb.).

> Not: OpenRouter "latency" metriği **TTFT** (ilk token) ölçer, uçtan-uca değil; "thinking"
> modelleri TTFT düşük ama E2E yüksek çıkabiliyor → E2E ölçümü esas alındı.

---

## 3. Sonuçlar (ampirik)

| Sağlayıcı | Model | Donanım | Tek-çağrı latency | Maliyet | Durum |
|-----------|-------|---------|-------------------|---------|-------|
| **Cerebras** | gpt-oss-120b | WSE (özel) | **~1.36s** | Ücretsiz (1M tok/gün, 30 RPM) | ✅ **PRIMARY** |
| **SambaNova** | gpt-oss-120b | RDU (özel) | ~3.17s | Ücretsiz (dar kota) | ✅ Fallback #1 |
| **Gemini 3.1 Flash Lite** | google/gemini-3.1-flash-lite | GPU (OpenRouter) | ~3.06s | $0.25 / $1.50 (1M token) | ✅ Fallback #2 (1M context) |
| **Novita** | deepseek-v3 vb. | GPU | ~12-60s* | Düşük, kotasız | ✅ Güvenlik ağı |
| Groq | llama-3.x | LPU | (değişken) | Ücretsiz-tier | ❌ DEPRECATED |
| Ollama | yerel | CPU/GPU | yavaş (GPU yok) | Ücretsiz (yerel) | ❌ DEPRECATED |
| HuggingFace | meta-llama vb. | Inference API | — | Ücretsiz-tier | ❌ DEPRECATED |
| OpenAI | gpt-4o vb. | GPU | hızlı | **Pahalı** | ⛔ Politika gereği dışlandı |

\* GPU bulutlarında aynı `gpt-oss-120b` 12-59s'ye kadar çıkabildi → **özel donanım** (Cerebras WSE,
SambaNova RDU) GPU bulutlarına göre **5-20× daha hızlı** (aynı model, aynı prompt).

### 3.1 OpenRouter ek aday modeller (sonradan test edilen 5 model)

Cerebras/SambaNova'ya ek olarak, OpenRouter üzerinden **5 popüler model daha** ampirik olarak
denendi (hızlı + güçlü + geniş context arayışı). Hepsi erişilebilir ve çalışır (2/2 OK) çıktı,
ancak **hiçbiri H3 (<5sn) eşiğini geçemedi** — uçtan-uca gecikmeleri çok yüksek.
Ölçüm: `evaluation/results/or5_test.log` + `provider_benchmark.json` (n=2, gerçek API).

| Sağlayıcı | Model | E2E P50 (s) | Ortalama (s) | H3 (<5s) | Sonuç |
|-----------|-------|------------:|-------------:|:--------:|-------|
| openrouter | `openai/gpt-5.4-nano` | 11.66 | 10.94 | ❌ | Elendi — yavaş |
| openrouter | `arcee-ai/trinity-large-thinking` | 12.33 | 8.54 | ❌ | Elendi — "thinking" gecikmesi |
| openrouter | `qwen/qwen3.6-flash` | 17.06 | 15.77 | ❌ | Elendi — yavaş |
| openrouter | `minimax/minimax-m2.5` | 24.78 | 24.22 | ❌ | Elendi — çok yavaş |
| openrouter | `stepfun/step-3.5-flash` | 58.94 | 47.30 | ❌ | Elendi — aşırı yavaş |

> **Çıkarım:** Beşi de **kaliteli çıktı** üretti (CIS'e uygun SSH sıkılaştırma), ama OpenRouter'ın
> GPU-yönlendirmeli altyapısında E2E gecikme **11.66s–58.94s** aralığında — Cerebras'ın **1.36s**'sinin
> **8–43 katı**. "OpenRouter latency" pazarlaması TTFT (ilk token) odaklıdır; **uçtan-uca** (tam yanıt)
> ölçünce hepsi H3'ü kat kat aştı. Bu, **özel-donanım (Cerebras WSE / SambaNova RDU)** kararını bir kez
> daha doğruladı: aynı OpenRouter üzerinden yalnız **Gemini 3.1 Flash Lite (~3.06s)** kabul edilebilir
> kaldı ve fallback #2 olarak tutuldu; diğer 5 model zincire **alınmadı**.

### Ana bulgu
> Aynı modeli (`gpt-oss-120b`) çalıştıran sağlayıcılar arasında **uçurum donanımdan** geliyor.
> Cerebras'ın WSE'si (wafer-scale) tek çağrıyı ~1.4s'de bitirirken, GPU bulutları 12s+ alabildi.
> Yani "en hızlı + ücretsiz" seçimi (Cerebras) aynı zamanda kalite kaybı getirmedi:
> İP-6/7/8 = %100, groundedness 0.81 (bkz. [14_DEGERLENDIRME.md](14_DEGERLENDIRME.md)).

---

## 4. Neden Deprecated?

- **Groq:** Free-tier "temporarily unavailable due to high demand" hatası ile **kararsız**;
  "bazen çalışan" API tez demosu için riskli (kullanıcı kararı). Developer (ücretli) tier de
  o dönem erişilemezdi. → otomatik zincirden çıkarıldı.
- **Ollama:** Yerel/limitsiz ama **GPU yok** → CPU'da çok yavaş; demo donanımı yetersiz.
- **HuggingFace:** `meta-llama` modelleri hf-inference'ta **chat-template** desteğini yitirdi
  (HTTP 400) + sağlayıcı artık aracı rolüne kaymış. → çıkarıldı.

Bu üçü kayıtta (`registry.py`) `deprecated=True` ile durur — yalnızca **açıkça**
`LLM_PROVIDER=<x>` ile seçilirse kullanılır; otomatik fallback zincirine girmez.

---

## 5. Fail-Fast Fallback (H3'ün asıl çözümü)

Sağlayıcı seçimi kadar **fallback davranışı** da kritikti. İlk ölçümlerde zincir 128-148s sürüyordu:
rate-limit yiyen birincil sağlayıcı, SDK'nın `Retry-After` **backoff**'unu bekliyordu (sonra yine
düşüyordu). Çözüm:

- **`max_retries=0`** (fail-fast): 429/5xx'te **anında** bir sonraki sağlayıcıya geç (backoff yok).
- `FallbackLLM`: tembel, paylaşımlı cache, ilk-token'da commit (streaming), hepsi düşerse anlamlı hata.

Sonuç: **128-148s → tek çağrı 1.36s; agent_plan 3.55s, agent_harden 4.62s (medyan)**. H3 hedefi
(P95 < 5sn) tek-çağrılı yollarda sağlandı; çok-adımlı agent borderline (~4.6s, RPM+n gürültüsü).

---

## 6. Nihai Zincir + Yapılandırma

```
Cerebras (gpt-oss-120b, ücretsiz)        ← PRIMARY
   ↓ (429/hata → fail-fast)
SambaNova (gpt-oss-120b, ücretsiz)
   ↓
Gemini 3.1 Flash Lite (OpenRouter, 1M ctx)
   ↓
Novita (düşük ücretli, kotasız)          ← güvenlik ağı
```

`config/config.json` → `default_provider: "cerebras"`, `.env` → ilgili `*_API_KEY` anahtarları.
Embedding her durumda Novita `qwen3-embedding-8b` (LLM seçiminden bağımsız).

Sağlayıcı eklemek/çıkarmak: `llm/clients/registry.py` (free_priority + deprecated bayrağı) tek
otoritedir; `build_order(primary=..., include_cheap=True)` zinciri buradan üretir.

---

## 7. Tekrar Üretim (reproduce)

```bash
# Tüm sağlayıcıları (anahtarı olanları) aynı modelle kıyasla:
python -m evaluation.provider_benchmark            # matris modu
# H3 yük testi (P50/P95/P99):
LLM_PROVIDER=cerebras python -m evaluation.load_test
```
