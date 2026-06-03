# Çalışma Dokümantasyonu (2026-06) — İntent Konsolidasyonu + Değerlendirme Kampanyası

> Bu doküman bu çalışma turunda **yazılan/değişen kodu, yeni yapıyı, karşılaşılan zorlukları,
> testleri ve sonuç metriklerini** kaydeder. Sayısal sonuç tablosu: `DEGERLENDIRME_SONUCLARI_2026-06.md`.
> Eval-kapısı ilkesi: **önce eval, sonra kod** — her değişiklik regresyon kapısından geçti.

---

## 1. Özet — ne yapıldı

1. **İntent katmanı konsolidasyonu** (whack-a-mole kök fix): 8 yarışan mekanizma → tek temiz akış.
2. **Eval-driven altyapı**: 6 yeni değerlendirme harness'i + 53-soruluk dataset + regresyon kapısı.
3. **Güvenlik/groundedness**: A6 (off_topic) kök fix, GROUNDING_DIRECTIVE, ClaimVerifier doğrulama.
4. **Lane optimizasyonu (veriyle)**: Novita + SambaNova zincirden çıkarıldı; cerebras primary doğrulandı.
5. **Temizlik**: ölü kod (intent_detector.py, llm/tests/) kaldırıldı.
6. **Güncel main ile merge** (Engin'in streaming'i) + 775 test yeşil + PR #53.

---

## 2. Yeni / değişen kod ve yapı

### İntent / pipeline
- `llm/pipelines/layers/hybrid_intent_detector.py` — `detect()` tek temiz akışa indirildi
  (smalltalk → TF-IDF ML info-vs-action + tek imperatif tiebreak + tek güven eşiği). 8 mekanizma
  → ~3 adım. **out_of_scope ÜRETMEZ** (kapsam artık L1 gate'in).
- `llm/pipelines/secure_v2.py` — "semantik kapsam kapısı" tek scope otoritesi
  (`off_topic → out_of_scope`); ölü rescue dalı kaldırıldı.
- `llm/pipelines/layers/info_pipeline.py` — `_should_use_rag` niyete bağlı 3 net dala indirildi.
- `llm/pipelines/layers/safety_classifier.py` — **A6**: off_topic prompt'u IT/sysadmin-bitişik
  konuları açıkça in-domain sayacak şekilde güçlendirildi (keyword listesi DEĞİL).
- `llm/prompts/simple_prompts.py` — GROUNDING_DIRECTIVE: "yalnız bağlamın kapsadığını say".

### LLM lane / registry
- `llm/clients/registry.py` — **Novita** (yavaş ~13s, embedding'lik) ve **SambaNova** (5/5 rate-limit)
  `deprecated=True` → otomatik fallback zincirinden çıktı. Yeni zincir: **cerebras → gemini(OpenRouter)**.
  (Explicit `LLM_PROVIDER=<x>` ile hâlâ kullanılabilir.)

### Değerlendirme harness'leri (YENİ — `evaluation/`)
| Dosya | Ne ölçer | LLM |
|-------|----------|-----|
| `intent_eval.py` | offline intent doğruluğu + `--check` regresyon kapısı | hayır ($0) |
| `eval_dataset.py` | 53-soruluk paylaşımlı dataset (Ubuntu/Win11/Server) | — |
| `ragas_eval.py` | RAGAS (faithfulness/relevancy/context-prec/recall) | evet |
| `lane_quality_bench.py` | 11 model kalite+latency (3'er paralel) | evet |
| `run_ablation.py` | RAG bileşen ablation (baseline→+hybrid→+mmr→+queryplan→full) | evet |
| `ip5_queryplan_ab.py` | İP-5 çözüm kanıtı: balanced vs multi-query groundedness | evet |

### Temizlik
- Silindi: `llm/pipelines/layers/intent_detector.py` (eski pattern-only), tüm `llm/tests/` (ölü/broken).
- Doküman düzeltmeleri: CLAUDE.md (ClaimVerifier durumu), docs/13 (anahtar rotasyon runbook).

---

## 3. Yeni yapı (mimari)

```
Kullanıcı
  ↓
L1 Safety (LLM) ── fast_local_safety hızlı-yol ── off_topic? → out_of_scope (TEK kapsam otoritesi)
  ↓ safe
L2 Intent (HybridIntentDetector) — smalltalk | info | action (ALAN-İÇİ; oos üretmez)
  ↓
L3 Routing — 3A smalltalk / 3B info(+RAG) / 3C action(script)
  ↓
L4 Enrichment (ZT) + OutputValidator + ClaimVerifier (groundedness)

LLM lane (FallbackLLM): cerebras gpt-oss-120b → gemini-3.1-flash-lite (OpenRouter)
Embedding (ayrı): Novita qwen3-embedding-8b (4096) → Qdrant
```

İlke değişimi: kapsam/niyet kararı **dağıtık keyword'lerden tek-otoriteye** (L1 LLM kategorisi +
TF-IDF info/action). Eval **direksiyon** (regresyon kapısı).

---

## 4. Karşılaşılan zorluklar + çözümler

| Zorluk | Çözüm |
|--------|-------|
| **Whack-a-mole** — niyet/kapsam 8 yerde çelişkili karar | Tek temiz akış + tek scope otoritesi (L1 gate). Eval + 775 test korudu. |
| **429-confound** — model bench'leri burst'te rate-limit yiyip yanlış sonuç (cerebras "kötü" göründü) | Kotasız judge (Novita) + ardışık/throttle'lı koşum + izole ping. Sequential'da 10/10, p95 2.1s. |
| **OpenRouter :free güvenilmez** (503/rate-limit) | Ücretli havuz ($5) doğrulandı (9/9); :free lane'e konmadı. |
| **SambaNova** izole de 5/5 rate-limit | Zincirden çıkarıldı (deprecated). |
| **Novita yavaş** (~13s) | LLM zincirinden çıkarıldı; embedding'de kaldı (ayrı modül). |
| **İP-5 geniş-sorgu groundedness düşük** (tam sistem → 0.00) | Kök: tek retrieve_balanced kapsamı yetersiz. Çözüm: **query-planning/multi-query** (kodda var, ablation kanıtladı: chunks +%75) + GROUNDING_DIRECTIVE + top_k↑. |
| **A6 off_topic aşırı agresif** | Keyword EKLEMEDEN (whack-a-mole'a dönmeden) safety prompt/otorite düzeltildi. |
| **Engin'in streaming'i ile çakışma** | merge (ort) temiz; 4 çekirdek dosyada conflict yok; 775 test korundu. |
| **Eskimiş doküman** (ClaimVerifier "kapalı/bug") | Gerçek durumla doğrulandı (aktif+kalibre) + düzeltildi. |

---

## 5. Testler

- **Birim/sözleşme:** 775 passed, 1 skipped (deterministik, sahte-LLM, $0).
  - CRITICAL set: test_intent_routing, test_intent_detector, test_pipeline_routes_matrix,
    test_jailbreak_resistance (14 adversarial), test_safety_classifier, test_llm_registry.
- **Eval kapısı:** `intent_eval.py --check` → regresyon yok (%97.3 alan-içi).
- **Yeni testler:** intent "out_of_scope üretmez" sözleşmesi; A6 (security-adjacent → in-domain);
  registry deprecated-chain (cerebras→gemini); güncellenen route-matrix (gate-tabanlı oos).

---

## 6. Sonuç metrikleri (özet)

| Alan | Metrik | Sonuç | Durum |
|------|--------|------:|:-----:|
| Agentic | İP-6 / İP-7 / İP-8 | 1.00 / 1.00 / 1.00 | ✅ |
| LLM groundedness | İP-5 (RAGAS faithfulness) | 0.70 (0.646) | ⚠️ <0.90 |
| RAG | H1 (RAG vs salt-LLM) | grounded 0.72→0.89, atıf 0.33→0.83 | ✅ |
| RAG | context_recall | 0.563 | ⚠️ |
| Latency | retrieval P95 / e2e | <2.5s / 7.8-20.9s | retrieval ✅ |
| Intent | offline doğruluk | %97.3 | ✅ |
| Güvenlik | jailbreak | 14/14 | ✅ |
| Lane | cerebras kalite/hız | 0.867 @ 1.94s | ✅ |

Detay + grafik/tablo: `DEGERLENDIRME_SONUCLARI_2026-06.md`.

---

## 7. Açık konular + yol

1. **İP-5 ≥0.90**: multi-query'yi geniş sorguda üretim+eval'de etkinleştir (ablation kanıtladı) +
   top_k 3→5 (Engin). Tutmazsa dürüst sınır olarak raporla.
2. **SambaNova**: kota açılırsa geri al; aksi halde zincir cerebras→gemini yeterli.
3. **Dürüst sınırlar (tez)**: H3 e2e latency (retrieval hedefi tutuyor), H2/H4 objektif-proxy.
4. **Engin (Track B)**: top_k, Win Server kuralları, TLS deploy, Compliance Report.
