# H1 Kanıtı — RAG vs Saf-LLM (Kontrollü A/B)

**Hipotez (H1):** RAG ile CIS bağlamı enjekte edilen yanıtlar, saf-LLM yanıtlarına göre daha doğru (fact-recall) ve daha gerekçelidir (groundedness).

**Yöntem:** Aynı üretim modeli + aynı prompt şablonu; tek değişken CIS bağlamı. Groundedness her iki mod için *aynı* retrieve edilen chunk'lara karşı ölçülür.

**Örneklem:** 0 OS sıkılaştırma sorusu (CIS Ubuntu Benchmark ground-truth).

## Toplu Sonuçlar

| Metrik | PURE (LLM) | RAG | Δ |
|---|---:|---:|---:|
| Fact-recall (doğruluk) | 0.000 | 0.000 | +0.000 |
| Groundedness | 0.000 | 0.000 | +0.000 |
| CIS atıf oranı | 0.000 | 0.000 | +0.000 |
| Latency (s) | 0.00 | 0.00 | +0.00 |

**Karşılaştırma (fact-recall):** RAG kazandı **0**, berabere 0, kaybetti 0 (n=0).

## Soru Bazında

| # | Soru | PURE recall | RAG recall | PURE ground | RAG ground |
|---|---|---:|---:|---:|---:|
