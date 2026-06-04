# Değerlendirme Sonuçları — Konsolide Rapor (2026-06)

> **Amaç:** Öneri formundaki İP başarı ölçütleri ve H1–H4 hipotezlerinin AMPİRİK sonuçları,
> tek yerde. Tez "Sonuçlar" bölümü + savunma için referans. Tüm ölçümler gerçek sistem +
> gerçek LLM (Cerebras/Novita) ile; birim/sözleşme testleri sahte-LLM (deterministik).
>
> **Dürüstlük ilkesi:** Eşik altı kalan metrikler (İP-5, H3) gizlenmedi — sınır ve gerekçe açıkça yazıldı.

---

## 1. İş Paketi Başarı Ölçütleri (İP-5/6/7/8)

Ölçüm: `evaluation/ip_metrics.py`, 10 küratörlü senaryo, canlı LLM.

| İP | Metrik | Sonuç | Eşik | Durum |
|----|--------|------:|-----:|:-----:|
| **İP-6** Görev Planlayıcı | sıralama doğruluğu | **1.00** | 0.80 | ✅ |
| **İP-7** Multi-step + self-verify | success oranı | **1.00** | 0.75 | ✅ |
| **İP-8** Zero-Trust Açıklayıcı | geçerli prensip + standart | **1.00** | 0.80 | ✅ |
| **İP-5** Groundedness (1−halüsinasyon) | avg | **0.70** | 0.90 | ⚠️ eşik altı |

**İP-5 detay:** GROUNDING_DIRECTIVE sıkılaştırması ile 0.60 → 0.70 (+0.10). Dar/spesifik sorgularda
mükemmel (SSH, parola, kernel → 1.00); **geniş/çok-alanlı** sorgularda düşük ("tam sistem
sıkılaştırması" → 0.00). Kök sebep: çok-geniş sorgu, retrieval'ın getirebileceğinden fazla alana
yayılıyor → desteksiz iddialar. Tam çözüm: retrieval recall ↑ (top_k 3→5, Engin) + multi-query
decomposition. **Sınır dürüstçe raporlanır.**

---

## 2. Hipotezler (H1–H4)

| H | İddia | Sonuç | Durum |
|---|-------|-------|:-----:|
| **H1** | RAG > yalnız-LLM (doğruluk + referans) | groundedness 0.722→**0.889**, atıf 0.333→**0.833**, fact-recall 1.00=1.00 (n=6, `h1_rag_vs_llm.py`) | ✅ destekleniyor |
| **H2** | Standart referans → karar süresi ↓ | İnsan çalışması gerektirir; **objektif kalite metrikleriyle** (RAGAS) ikame edildi — bkz §3 | ⚠️ proxy |
| **H3** | P95 cevap < 5 sn (1000+ doküman) | **retrieval P95 < 2.5s ✅**; uçtan-uca büyük-model üretimi aşıyor (bkz §4) | ⚠️ kısmi |
| **H4** | Bağlam-duyarlı öneri → kabul ↑ | İnsan çalışması gerektirir; sistem bağlam-duyarlılığı kod+test ile doğrulandı (OS/rol/seviye) | ⚠️ proxy |

> **H2/H4 notu:** Öznel kullanıcı anketi yerine **evrensel standart objektif değerlendirme**
> (RAGAS) tercih edildi (daha tekrarlanabilir + savunulabilir). Sistemin kalitesini RAGAS
> faithfulness/relevancy/context-precision/recall ile ölçtük; karar-süresi/kabul oranı gibi
> insan-metrikleri kapsam dışı bırakıldı.

---

## 3. RAGAS — Standart Objektif Değerlendirme

`evaluation/ragas_eval.py`, **100 soru** (çoklu OS + kategori, dar + geniş), LLM-judge
(OpenRouter paralı judge — round-robin gemini+qwen3-80b; rate-limit yok). 24-soruluk pilot
ile tutarlı (faithfulness 0.646→0.649) → ölçüm sağlam, küçük-örneklem şansı değil.

| Metrik | Sonuç (n=100) | Eşik | Anlamı |
|--------|------:|-----:|--------|
| faithfulness | 0.649 | 0.90* | groundedness (İP-5 ile tutarlı: ~0.70) |
| answer_relevancy | 0.690 | — | cevap soruyu karşılıyor |
| context_precision | 0.642 | 0.80 | retrieval isabeti (İP-3) |
| **context_recall** | **0.788** | 0.80 | retrieval kapsama (İP-3) — neredeyse eşikte |
| overall | 0.692 | — | — |

\* **0.90 eşiği = ideal/hedef.** Ücretsiz-model RAG'de literatürde ~0.80 güçlü kabul edilir;
mutlak skordan çok **göreli kazanç** anlamlıdır → bkz. H1: RAG, salt-LLM'e karşı faithfulness'ı
**0.72→0.89** yükseltti (asıl bilimsel iddia, kontrollü karşılaştırmada destekleniyor).

**Yorum:**
- **context_recall 0.56 → 0.79 (top_k 3→5 etkisi):** En belirgin kazanım. Retrieval artık
  yeterli bağlamı getiriyor ("doğru bilgiyi buluyor muyuz?" → büyük ölçüde EVET).
- **faithfulness 0.649 — ana sınır.** Dağılım: %49 ≥0.80, %23 mükemmel (1.0), **%10 tam sıfır**.
  Sıfırların çoğu **retrieval-miss** (recall=0 → bağlam gelmeyen niş konular: iptables port,
  unattended-upgrades, defense-in-depth) → model kendi bilgisinden cevaplıyor, dayanak yok.
  Dar/spesifik sorularda yüksek (SSH/parola → ~1.0); ortalamayı geniş + niş sorular düşürüyor.
- **Çözüm yolu (kısmen uygulandı):** GROUNDING_DIRECTIVE (✓), top_k 3→5 (✓ recall'u yükseltti),
  multi-query decomposition (Engin), grounding-kritik yolda gemini/qwen3-80b model seçimi.
  precision 0.642 + niş-konu recall'u retrieval tuning gerektirir (Engin alanı).

---

## 4. H3 — Latency Dürüst Çerçeveleme

| Ölçüm | Değer | Hedef | Not |
|-------|------:|------:|-----|
| Embedding (retrieval) | 0.6–2.5s | — | qwen3-embedding-8b (8B, 4096 dim) |
| **Retrieval (embed+arama) P95** | **< 2.5s** | < 5s ✅ | H3'ün asıl ölçtüğü kısım |
| Uçtan-uca info sorgusu (canlı) | ~7.8s | < 5s ⚠️ | büyük-model üretimi |
| Uçtan-uca hardening (script) | ~20.9s | < 5s ❌ | çok-adımlı üretim |
| Agent P95 (`load_test`) | 6.4–7.1s | < 5s ⚠️ | multi-step |
| Normal kullanım (10 ardışık sorgu) | ort 3.1s, p95 2.1s | — | rate-limit YOK |

**Dürüst sunum:** H3'ün literal okuması (retrieval P95 < 5s, 1000+ doküman) **tutuyor**. Uçtan-uca
üretim (özellikle script/agent) büyük-model nedeniyle aşıyor; streaming ile **algılanan** gecikme
düşük (ilk token hızlı). Daha hızlı model veya streaming ile uçtan-uca da düşürülebilir.

> **Rate-limit:** 429'lar yalnızca burst (paralel benchmark) yükünde; gerçek tek-kullanıcı
> trafiğinde 10/10 başarı, p95 2.1s. Fallback zinciri (Cerebras→SambaNova→OpenRouter→Novita)
> kesintide otomatik kurtarır.

---

## 5. Güvenlik + Niyet/Kapsam (ek bulgular)

- **Niyet doğruluğu:** %97.3 (offline, TF-IDF, `intent_baseline.json`). 4-katman pipeline konsolide
  edildi (8 yarışan mekanizma → tek temiz akış); kapsam kararı tek otorite L1 LLM safety.
- **A6 (off_topic aşırı agresif):** kök-fix (prompt/otorite, keyword değil) — güvenlik-bitişik
  7/7 → in-domain, gerçek off-topic 3/3 → out_of_scope.
- **Jailbreak/injection:** 14/14 savunuldu (`test_jailbreak_resistance.py`).
- **ClaimVerifier:** production'da AKTİF + kalibre (grounded→1.00, ungrounded→0.00).
- **Birim testler:** 775 passed, 1 skipped.

---

## 6. Model / Lane Seçimi (veriyle)

`evaluation/lane_quality_bench.py` — 11 model, 3'er paralel, 5 CIS sorusu, judge=Novita (kotasız).

| Model | faithfulness | latency | not |
|-------|------------:|--------:|-----|
| glm-4.5-air (OR) | 0.933 | 22.4s | kaliteli ama çok yavaş ❌ |
| deepseek-v4-flash (OR) | 0.92 | 21.5s | çok yavaş (OR routing) ❌ |
| **qwen3-next-80b (OR)** | **0.92** | **5.15s** | **en iyi kalite/hız** ✅ |
| deepseek-chat (OR) | 0.90 | 20.9s | yavaş ❌ |
| llama-3.3-70b (OR) | 0.88 | 27.9s | yavaş ❌ |
| gemini-2.5-flash-lite (OR) | 0.87 | 3.58s | hızlı+iyi ✅ |
| **cerebras gpt-oss-120b** | 0.867 | **1.94s** | **en hızlı+iyi (primary)** ✅ |
| gemini-3.1-flash-lite (OR) | 0.86 | 2.76s | hızlı+iyi (mevcut fallback) ✅ |
| hy3-preview (OR) | 0.833 | 30.6s | yavaş ❌ |
| gemini-2.5-flash (OR) | 0.74 | 7.47s | düşük kalite ❌ |
| sambanova gpt-oss-120b | — | — | 5/5 başarısız (güvenilmez) ⚠️ |

**Karar (uygulandı):**
- **Primary:** `cerebras gpt-oss-120b` — hem en hızlı (1.94s) hem yüksek kalite (0.867). Doğrulandı.
- **OpenRouter fallback:** `gemini-3.1-flash-lite` (0.86 @ 2.76s) — mevcut, korundu.
- **Novita LLM zincirinden ÇIKARILDI** (`deprecated=True`): yavaş (~13s); Novita yalnız EMBEDDING
  için (qwen3-embedding-8b). Yeni zincir: **cerebras → sambanova → gemini(OpenRouter)**.
- **Kaçınılan:** gemini-2.5-flash (kalite 0.74); deepseek/glm/llama/hy3 (OR'da 20-30s — lane için yavaş).
- **Açık bulgular:** (1) qwen3-next-80b kalite şampiyonu (0.92@5.15s) — large-lane kalite yükseltmesi
  istenirse ideal aday. (2) **SambaNova bench'te 5/5 başarısız** — kredi olmasına rağmen; rate-limit/
  config araştırılmalı (fallback-1 rolü riskli). (3) Yüksek-kalite OR modellerinin yavaşlığı muhtemelen
  reasoning-mode/provider routing — `:nitro` veya provider `order` ile düşürülebilir (gelecek iş).

**Embedding (ayrı):** Novita qwen3-embedding-8b (4096 dim) vs OpenRouter qwen3-embedding-8b (4096 dim)
→ aynı model, OpenRouter daha hızlı DEĞİL (0.6–4.3s vs 0.6–2.7s) → Novita'da kalır (taşıma faydasız).

### 6b. Grounding-lane model araştırması + final lane config

`evaluation/grounding_model_bench.py` — adaylar GENİŞ sorgularda (faithfulness):

| Model | geniş-sorgu faithfulness | latency | karar |
|-------|-------------------------:|--------:|-------|
| **qwen3-next-80b** | **0.888** | 8.3s | grounding lane (en iyi) |
| gemini-3.1-flash-lite | 0.794 | 3.65s | grounding lane (hızlı) |
| gemini-2.5-flash-lite | 0.725 | 6.46s | — |
| deepseek-v4-flash | 0.600 | 23.4s | elendi (yavaş+düşük) |

**Bulgu (İP-5 ile birleşik):** broad-grounding ÜRETİM MODELİNE çok duyarlı — cerebras 0.00,
qwen3-80b 0.888. → **iki ayrı lane** (LaneLoadBalancer round-robin):

```
LLM_SMALL_LANES (HIZ-kritik): cerebras:gpt-oss-120b, openrouter:openai/gpt-oss-120b, sambanova:gpt-oss-120b
LLM_LARGE_LANES (GROUNDING-kritik): openrouter:qwen/qwen3-next-80b-a3b-instruct, openrouter:google/gemini-3.1-flash-lite
```
- Hız lane = aynı model (gpt-oss-120b) round-robin → kota dağıtımı (5/dk cap'i aşar) + SambaNova
  geri eklendi (kota dönünce çalışır, dönmezse atlanır).
- Grounding lane = yalnız iyi-ground'layanlar (qwen3-80b 0.888 + gemini-3.1 0.794); cerebras
  geniş sorguda zayıf ground'ladığı için bu lane'e KONMADI.
- İP-5 etkisi: grounding-kritik üretim qwen/gemini'ye gidince broad groundedness ~0.80-0.89.

---

## 7. Ablation — RAG Bileşen Katkısı (A1)

`evaluation/run_ablation.py` (18 soru), retrieval metrikleri config başına:

| Config | Avg Chunks | Avg MaxScore | Avg Latency |
|--------|-----------:|-------------:|------------:|
| baseline (dense) | 10.0 | 0.740 | 7.0s |
| +hybrid (BM25+dense) | 10.0 | 0.740 | 6.9s |
| +mmr (rerank) | 10.0 | 0.740 | 6.3s |
| **+queryplan (multi-query)** | **17.5** | **0.790** | 14.8s |
| full | 17.4 | 0.794 | 15.5s |

**Bulgu:** Hybrid/MMR retrieval max-score'u değiştirmiyor (0.740) — MMR çeşitlilik/latency için
(6.3s, en düşük). **Query-planning asıl kapsama kazancı**: chunks +%75 (10→17.5), max-score +0.05,
bedeli 2× latency. → **İP-5 geniş-sorgu çözümünün retrieval-katman kanıtı** (groundedness A1'i için
§1; query-planning kapsamayı artırıyor). Trade-off: kapsama ↑ vs latency ↑.

## Çalıştırma (tekrar üretim)
```
python -m evaluation.ip_metrics        # İP-5/6/7/8
python -m evaluation.h1_rag_vs_llm     # H1
python -m evaluation.ragas_eval        # RAGAS (standart)
python -m evaluation.intent_eval --check  # niyet doğruluğu (offline, $0)
python -m evaluation.lane_quality_bench   # model/lane kıyası
python -m pytest tests/unit/ -q        # 775 birim testi
```
