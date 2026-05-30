# Değerlendirme (Evaluation) — İş Paketleri & Hipotezler

Bu belge, öneri formundaki **iş paketlerinin sayısal başarı ölçütlerini** (İP-5/6/7/8)
ve **hipotezleri** (H1, H3) kanıtlamak için kullanılan değerlendirme harness'lerini ve
**gerçek koşum sonuçlarını** içerir.

> Tüm sayılar `evaluation/results/*.json` dosyalarından alınmıştır —
> **uydurma/placeholder değildir.** Tekrar üretmek için ilgili komutları çalıştırın.

Harness'ler:
- `evaluation/ip_metrics.py` — İP-5/6/7/8 sayısal başarı ölçümü
- `evaluation/h1_rag_vs_llm.py` — H1 (RAG vs saf-LLM) kontrollü A/B
- `evaluation/load_test.py` — H3 (P95 gecikme) yük testi

---

## İP-5/6/7/8 — İş Paketi Başarı Ölçümü

**Yöntem:** 8 küratörlü senaryo üzerinde gerçek modüller (TaskPlanner, HardeningAgent,
ZeroTrustEnricher, ClaimVerifier) koşturulur; çıktılar saf (deterministik) skorlama
fonksiyonlarıyla ölçülür. Sağlayıcı: Novita (kotasız). Komut:
`LLM_PROVIDER=novita IP_SAMPLE=8 python -m evaluation.ip_metrics`

| İP | Form ölçütü | Ölçülen | Eşik | Durum |
|----|-------------|--------:|-----:|:-----:|
| **İP-6 Görev Planlayıcı** | ≥%80 doğru sıralama | **%100** (seçim isabeti %100) | %80 | ✅ |
| **İP-7 Multi-step ajan** | ≥%75 success + self-verify | **%100** (verify-gate %100, adım-tamlık %100) | %75 | ✅ |
| **İP-8 ZT Açıklayıcı** | ≥%80 doğru ZT eşleşme | **%100** (geçerli prensip + standart referans) | %80 | ✅ |
| **İP-5 Groundedness** | halüsinasyon <%10 | **0.41** (halüsinasyon ≈ %59) | 0.90 | ⚠️ |

### Dürüst Yorum

- **İP-6/7/8 eşiklerin üzerinde:** Görev planlayıcı kuralları doğru sıralıyor ve hedefe
  uygun seçiyor; multi-step ajan her senaryoda plan→collect→generate→**verify** zincirini
  tamamlıyor (self-verify gate %100 çalışıyor); ZT açıklayıcı her öneride geçerli Zero-Trust
  prensibi + NIST/CIS/ISO standart referansı üretiyor.
- **İP-5 groundedness düşük ve değişken (0.00–1.00):** Bu, ölçülen **gerçek** bir sınırdır.
  Somut/spesifik hedeflerde (örn. ağ-kernel, yazılım servis) groundedness 0.75–1.00; soyut
  hedeflerde (audit, parola politikası, yama) 0.00'a kadar düşüyor — LLM bağlam-dışı genel
  bilgi üretiyor veya iddialar chunk'larla örtüşmüyor. **Sınır:** İP-8 "doğru eşleşme"
  semantik bir yargıdır; harness *geçerli prensip + standart varlığını* proxy ölçer.
- **İyileştirme yönü:** İP-5'i güçlendirmek için prompt'a "yalnızca bağlamdaki bilgiyi
  kullan" kısıtı + claim verification eşiği ayarı; H1'de (somut sorular) groundedness 0.89'a
  ulaşıyor, bu da soruların somutluğunun belirleyici olduğunu gösteriyor.

---

## H1 Hipotezi

## H1 Hipotezi

> **H1:** RAG ile CIS bağlamı enjekte edilen yanıtlar, saf-LLM yanıtlarına göre
> daha doğru (fact-recall) ve daha gerekçelidir (groundedness).

## Yöntem — Kontrollü A/B

`evaluation/h1_rag_vs_llm.py` H1'i **kontrollü** ölçer: aynı üretim modeli + aynı
prompt şablonu iki kez çalışır, **tek değişken CIS bağlamıdır**:
- **PURE:** bağlam YOK (modelin parametrik bilgisi)
- **RAG:** retrieve edilen CIS chunk'ları prompt'a enjekte

Böylece ölçülen fark doğrudan RAG'in katkısıdır. Metrikler:
- **fact_recall:** küratörlü CIS ground-truth gerçeklerinin yanıtta bulunma oranı
- **groundedness:** `ClaimVerifier`'ın iddiaların *aynı* chunk'larca desteklenme oranı (simetrik)
- **CIS atıf oranı** ve **latency**

## Çalıştırma

```bash
# Kotasız sağlayıcı ile (önerilen — 429 yok):
LLM_PROVIDER=novita H1_SAMPLE=6 H1_MAX_CLAIMS=3 python -m evaluation.h1_rag_vs_llm

# Ücretsiz alternatifler:
LLM_PROVIDER=ollama  python -m evaluation.h1_rag_vs_llm     # yerel (önce: ollama pull)
LLM_INCLUDE_CHEAP=1  python -m evaluation.h1_rag_vs_llm     # groq→…→novita fallback
```
Çıktı: `evaluation/results/h1_report.md` + `h1_results.json`.

## Gerçek Sonuçlar (n=6, Novita primary — kotasız, 0 rate-limit)

| Metrik | PURE (saf-LLM) | RAG | Δ |
|---|---:|---:|---:|
| Fact-recall (doğruluk) | 1.000 | 1.000 | +0.000 |
| **Groundedness** | 0.722 | **0.889** | **+0.167** |
| **CIS atıf oranı** | 0.333 | **0.833** | **+0.500** |
| Latency (s) | 5.45 | 8.39 | +2.95 |

**Fact-recall karşılaştırması:** RAG 0 kazandı, **6 berabere**, 0 kaybetti (n=6).

### Dürüst Yorum

- **Fact-recall ikisinde de 1.000:** Bu 6 soru, modelin parametrik bilgisinde
  zaten güçlü olduğu temel CIS direktifleri (PermitRootLogin, MaxAuthTries,
  PASS_MIN_DAYS vb.). Bu yüzden saf-LLM de tam skor aldı → bu örneklem RAG'in
  **doğruluk** avantajını ayırt edemiyor. Daha zor/spesifik sorularla (versiyon
  farkları, az bilinen kurallar) fark açılması beklenir.
- **Asıl kazanç gerekçelendirmede:** RAG, **CIS atıf oranını %33 → %83'e**
  (kaynak gösterme) ve **groundedness'ı 0.722 → 0.889'a** çıkardı. Yani RAG'li
  yanıtlar yalnızca doğru değil, **kaynağa dayalı ve denetlenebilir** — savunma
  amaçlı güvenlik sıkılaştırmasında kritik olan tam budur.
- **Maliyet:** RAG ~3s ek gecikme getiriyor (retrieval + daha uzun prompt).

### Kısıtlar / Sonraki Adım

- Örneklem küçük (n=6) ve sorular "kolay" uçta. Tez sunumu için **n=12** (tüm
  `H1_DATASET`) + birkaç **zor/spesifik** soru eklenip tekrar koşulmalı.

---

## H3 Hipotezi — P95 Gecikme < 5 sn

**Yöntem:** `evaluation/load_test.py` — in-process FastAPI (TestClient) + eşzamanlı
istek; percentile `api/metrics._percentile`'dan. Komut:
`LLM_PROVIDER=<sağlayıcı> OTEL_SDK_DISABLED=true python -m evaluation.load_test`

**Bulgu — latency tamamen LLM sağlayıcısına bağlı:**

| İş | Sağlayıcı | Süre | H3 (<5s) |
|----|-----------|-----:|:--------:|
| TaskPlanner.plan() (tekil) | Groq llama-3.1-8b | **~0.71s** | ✅ |
| HardeningAgent.run() (tekil, plan→üret→verify→refine) | Groq | **~2.76s** | ✅ |
| Novita-large (deepseek-v3) tek LLM çağrısı | Novita | ~4.5s | ⚠️ |
| agent/plan (Novita-large, zincirde 2+ çağrı) | Novita | ~16s | ❌ |
| agent/harden (Novita-large) | Novita | ~21s | ❌ |

### Dürüst Yorum

- **H3, hedef sağlayıcı (Groq) ile karşılanıyor:** TaskPlanner 0.71s, HardeningAgent
  2.76s — ikisi de <5s. Bu, formdaki birincil sağlayıcı konfigürasyonudur.
- **Novita-large yavaş:** deepseek-v3 doğru/kapsamlı ama tek çağrısı ~4.5s; agent uçları
  2+ büyük-model çağrısı zincirlediği için 16–23s'ye çıkıyor. Yani **latency kod kaynaklı
  değil, model seçimi kaynaklı** — Novita kalite/maliyet için, Groq hız için.
- **Ortam notları:** OTel collector (Jaeger) erişilemezken her span ~1s export-timeout
  yiyordu → `OTEL_SDK_DISABLED` ile çözüldü. Eşzamanlı ilk isteklerde lazy-init yarışı
  500 veriyordu → load_test'te ısınma isteğiyle giderildi.
- **Sınır:** Groq ücretsiz-tier kotası gündüz dolduğu için Groq ile yük testi bu koşumda
  tekrarlanamadı; Groq tekil ölçümleri (0.71/2.76s) daha önceki kotalı pencereden gerçek.

## 429 / Kota Notu

Harness yoğun LLM çağrısı yapar; **Groq ücretsiz tier** kotası buna dar gelir
(dolunca SDK uzun `Retry-After` ile bekleyip eval'i kilitler). Bu koşumda
`LLM_PROVIDER=novita` (düşük ücretli, **kotasız**) kullanıldı → 6/6 tamamlandı,
0 rate-limit. Sağlayıcı mimarisi için bkz. [13_GUVENLIK.md](13_GUVENLIK.md) ve
`llm/clients/registry.py` (ücretsiz-first sıra + maliyet katmanları).
