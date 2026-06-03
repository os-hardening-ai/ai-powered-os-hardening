# İP-5 Groundedness — RAG retrieval önerisi (Engin)

**Tarih:** 2026-06-03 | **Ölçüm:** `evaluation/ip_metrics.py`, 10 senaryo, canlı LLM (novita)

## Bulgu

İP-5 (groundedness = 1 − halüsinasyon) **avg 0.60**, eşik 0.90'ın altında. Senaryo kırılımı net bir desen gösteriyor:

| groundedness | senaryo |
|---|---|
| 1.00 | SSH sıkılaştır / ağ-kernel / dosya sistemi / sistem bakımı |
| 0.75 | SSH + parola (birlikte) |
| 0.50 | parola/PAM · audit |
| 0.25 | güvenlik yamaları + erişim kontrolü |
| **0.00** | **yazılım/servis yapılandırması · TAM sistem sıkılaştırması (çok-alanlı)** |

**Desen:** Dar/tek-alanlı hedefler → 1.00 (mükemmel). Geniş/çok-alanlı hedefler → 0.00-0.50.
Tüm senaryolar 10 chunk çekti (retrieval boş değil). Sorun **geniş sorguda cevabın, çekilen
top-10 chunk'ın kapsamadığı alanlara yayılması** → desteksiz iddialar → düşük groundedness.

## İki taraflı çözüm

**1. Generation tarafı (BEN yaptım — `llm/prompts/simple_prompts.py::GROUNDING_DIRECTIVE`):**
Direktife "yalnız bağlamın KAPSADIĞI maddeleri say, genel bilginle GENİŞLETME/DOLDURMA;
kapsanmayan alanları belirt" kısıtı eklendi. (Eval'le doğrulandı — bu dosyayla birlikte commit'lendi.)

**2. RAG retrieval tarafı (SENİN alanın — öneri, tek taraflı değiştirmedim çünkü quota trade-off'u senin):**

**ÖLÇÜLEN SOMUT VERİ (2026-06-03):**
- Production default: `ChatRequest.rag_top_k=3` (kaynak başına → **6 chunk toplam**) — senin
  quota optimizasyonun (docs/18). RAGContextBuilder default'u ise 5.
- RAGAS (24 soru, top_k=5/10-chunk): **context_recall 0.563**, faithfulness 0.646 → retrieval
  KAPSAMA zaten sınırda. Production top_k=3 (6 chunk) bundan da DÜŞÜK recall demek.
- top_k deneyi (geniş senaryolar): top_k=5→10 (10→20 chunk) groundedness **+0.08** (0.25→0.33).
  Ama "tam sistem sıkılaştırma" 20 chunk'la bile 0.00 → çok-geniş sorgu doğasında tavan var.

**ÖNERİ (quota vs groundedness trade-off — senin kararın):**
- **`rag_top_k` default 3→5** (6→10 chunk): recall'i benim eval seviyeme çeker, +0.05-0.08
  groundedness; bedeli +context/latency + quota. `api/router_chat.py:114`. Re-index GEREKMEZ.
- Çok-geniş sorgular için kökten çözüm: **multi-query** (hedefi SSH/parola/audit alt-sorgulara
  böl, ayrı retrieve+birleştir). `rag/retrieval/`. Daha fazla iş ama tavanı kaldırır.

## 3. Cross-encoder reranker (BEN ekledim — etkinleştirme SENDE)

`rag/retrieval/reranker.py::CrossEncoderReranker` eklendi (test'li, default KAPALI, lazy model).
Araştırma: cross-encoder reranking halüsinasyonu ~%35 azaltır (İP-5 groundedness'e doğrudan).

**Etkinleştirme (RAG retrieval — SENİN alanın):**
- Desen: GENİŞ aday çek (top-20) → `CrossEncoderReranker.rerank(query, candidates, top_n=5)` → top-5 LLM'e.
- `RAGContextBuilder`'a `use_cross_encoder` toggle ekle; açıkken MMR yerine/sonrasında cross-encoder.
- **Ops:** model ağırlığı (~100-500MB) ilk çağrıda indirilir → Docker image'a önceden çek veya
  ilk-istek gecikmesini kabul et. Çok dilli varsayılan (TR sorgu + EN CIS): `mmarco-mMiniLMv2`.
- Yeni dep YOK (sentence-transformers zaten kurulu).

## Doğrulama
Değişiklikten sonra `LLM_PROVIDER=novita python -m evaluation.ragas_eval` (veya `ip_metrics`)
ile yeniden ölç; context_recall + faithfulness yükselmeli. Hedef: faithfulness ≥ 0.90.
