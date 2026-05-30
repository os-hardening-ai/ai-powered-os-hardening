# Değerlendirme (Evaluation) — H1 Hipotezi

Bu belge, projenin **H1 hipotezini** kanıtlamak için kullanılan değerlendirme
harness'ini ve **gerçek koşum sonuçlarını** içerir.

> Tüm sayılar `evaluation/results/h1_results.json` dosyasından alınmıştır —
> **uydurma/placeholder değildir.** Tekrar üretmek için aşağıdaki komutu çalıştırın.

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
- Latency: agent uçları optimize edildi (<5s); chat/RAG yolu için yük altında
  istatistiksel P95 ayrıca ölçülmeli (H3).

## 429 / Kota Notu

Harness yoğun LLM çağrısı yapar; **Groq ücretsiz tier** kotası buna dar gelir
(dolunca SDK uzun `Retry-After` ile bekleyip eval'i kilitler). Bu koşumda
`LLM_PROVIDER=novita` (düşük ücretli, **kotasız**) kullanıldı → 6/6 tamamlandı,
0 rate-limit. Sağlayıcı mimarisi için bkz. [13_GUVENLIK.md](13_GUVENLIK.md) ve
`llm/clients/registry.py` (ücretsiz-first sıra + maliyet katmanları).
