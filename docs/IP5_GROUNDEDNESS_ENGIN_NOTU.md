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

**2. RAG retrieval tarafı (SENİN alanın — öneri):**
- **`top_k`'yi geniş sorgularda artır** (10 → 20). Çok-alanlı hedef ("tam sistem sıkılaştırması")
  daha fazla dayanak chunk'ı ister; 10 yetmiyor. Bu **re-index GEREKTİRMEZ** (sadece retrieval
  parametresi) → düşük riskli.
- Alternatif: **multi-query retrieval** — geniş hedefi alt-konulara böl (SSH / parola / audit /
  ağ...) ve her biri için ayrı retrieve + birleştir. Çok-alanlı kapsamayı kökten çözer.
- İlgili dosya: `rag/retrieval/rag_retriever.py` (`embed_query` + query). `RAGContextBuilder(top_k=...)`
  çağrısı `evaluation/ip_metrics.py::_measure_ip5`'te top_k=5; production `info_pipeline`'da da
  top_k ayarlı — geniş sorguda dinamik artırılabilir.

## Doğrulama
Değişiklikten sonra `LLM_PROVIDER=novita python -m evaluation.ip_metrics` (veya yalnız İP-5)
ile yeniden ölç; geniş senaryoların (yazılım/servis, tam sistem) groundedness'i 0.00'dan
yükselmeli. Hedef: avg ≥ 0.90.
