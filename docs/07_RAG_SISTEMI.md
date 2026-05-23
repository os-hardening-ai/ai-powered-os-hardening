# RAG (Retrieval-Augmented Generation) Sistemi

## Genel Bakış

RAG, **LLM'lerin bilgi tabanını genişletmek** için kullanılan bir tekniktir. LLM'in eğitim datasında olmayan veya güncel olmayan bilgileri **dış kaynaklardan (CIS Benchmark dokümanları + hardening kuralları) çekerek** yanıtlara dahil eder.

```
┌──────────────────────────────────────────────────────────────────┐
│                  ENHANCED RAG PIPELINE (v1.1)                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  1. USER QUESTION                                                  │
│     "Ubuntu 24.04 SSH hardening best practices?"                  │
│                      │                                             │
│                      ▼                                             │
│  2. QUERY PLANNING (QueryPlanner — opsiyonel)                     │
│     Original + Subquery + HyDE passage + Stepback                 │
│     → 4-5 farklı sorgu stratejisi                                 │
│                      │                                             │
│                      ▼                                             │
│  3. FAN-OUT EMBEDDING (Novita qwen3-embedding-8b)                │
│     Her sorgu için 4096-dim vektör                                │
│                      │                                             │
│                      ▼                                             │
│  4. PER-SOURCE SEMANTIC SEARCH (Qdrant Cloud)                    │
│     YAML rules + CIS PDF benchmark ayrı ayrı aranır              │
│     Fail-open: 0 sonuçta min_score otomatik düşer                │
│     ├─ YAML hit 1 (score: 0.91) - sshd_config rule              │
│     ├─ YAML hit 2 (score: 0.88) - PermitRootLogin               │
│     ├─ PDF hit 1  (score: 0.87) - CIS Section 5.2.4             │
│     └─ PDF hit 2  (score: 0.82) - CIS Section 5.2.3             │
│                      │                                             │
│                      ▼                                             │
│  5. HYBRID SCORING (InContextHybridScorer — opsiyonel)           │
│     BM25 + Dense RRF füzyonu                                      │
│     Exact keyword match: /etc/ssh/sshd_config, PermitRootLogin   │
│                      │                                             │
│                      ▼                                             │
│  6. MMR RERANKING (MMRReranker — opsiyonel)                      │
│     Jaccard çeşitlilik + Relevance dengesi                        │
│     Tekrarlayan chunk'ları elemek → top-N seç                    │
│                      │                                             │
│                      ▼                                             │
│  7. CONTEXT CONSTRUCTION                                           │
│     "CIS Ubuntu 24.04 Section 5.2.4: PermitRootLogin no..."     │
│                      │                                             │
│                      ▼                                             │
│  8. LLM GENERATION (Groq Llama 70B / Novita Qwen)               │
│     Prompt: Context + User Question                               │
│                      │                                             │
│                      ▼                                             │
│  9. CLAIM VERIFICATION (ClaimVerifier — opsiyonel)               │
│     Her iddia → chunk'lara karşı doğrulama                       │
│     Düşük güven → uyarı disclaimer eklenir                       │
│                      │                                             │
│                      ▼                                             │
│  10. OUTPUT  (kaynaklı, doğrulanmış yanıt)                       │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Neden RAG?

### Problem: LLM'lerin Sınırları

**1. Eğitim Tarihi Kesintisi (Knowledge Cutoff)**
- Llama 3.3 eğitim tarihi: 2023
- CIS Ubuntu 24.04 Benchmark: 2024'te yayınlandı
- **Sonuç**: LLM Ubuntu 24.04 CIS önerilerini bilmiyor

**2. Domain-Specific Bilgi Eksikliği**
- LLM'ler genel amaçlı eğitilir
- CIS Benchmark section numaraları, spesifik audit/remediation script'leri eksik temsil edilir
- **Sonuç**: Halüsinasyon riski

**3. Hallucination (Yanılsama)**
- LLM bazen bilmediği şeyleri uydurur
- Güvenlik kritik → Yanlış bilgi tehlikeli
- **Sonuç**: Güvenilir, kaynak destekli bilgi gerekli

### Çözüm: RAG

**RAG ile:**
- En güncel CIS Benchmark bilgisi (2024-2025)
- Doğru section numaraları ve referanslar
- Kaynak destekli yanıtlar (verifiable)
- Tam audit + remediation script'leri (YAML kurallarından)

**RAG olmadan:**
- Eski veya genel bilgi
- Hallucination riski
- Kaynak belirtilmez

---

## Kaynak Dokümanlar

Sistem üç farklı kaynak türünü indexler:

### 1. CIS Benchmark PDF'leri (`data/source/`)

| Dosya | OS | Chunk Yöntemi | Durum |
|-------|----|---------------|-------|
| `CIS_Ubuntu_Linux_24.04_LTS_Benchmark_v1.0.0.pdf` | Ubuntu 24.04 | `cis_section` | ✅ Aktif |
| `CIS_Microsoft_Windows_Server_2025_Benchmark_v2.0.0.pdf` | Windows Server 2025 | `cis_section` | ✅ Aktif |
| `CIS_Microsoft_Windows_11_Stand-alone_Benchmark_v4.0.0.pdf` | Windows 11 Desktop | `cis_section` | ✅ Aktif |

PDF'ler CIS section yapısına göre bölünür. Her chunk: başlık, açıklama, rationale, audit prosedürü, remediation adımları içerir.

### 2. YAML Kural Dosyaları (`data/rules/`)

| Dosya | OS | Kural Sayısı | Chunk Yöntemi | Durum |
|-------|----|-------------|---------------|-------|
| `ubuntu_24_04_rules.yaml` | Ubuntu 24.04 | 312 kural | `yaml_rules` | ✅ Aktif |
| `windows_11_desktop_rules.yaml` | Windows 11 Desktop | — | `yaml_rules` | ✅ Aktif |
| `windows_server_2025_rules.yaml` | Windows Server 2025 | — | `yaml_rules` | ⛔ Devre dışı |

YAML dosyaları PDF'leri **tamamlar** — her CIS kuralı için:
- Tam bash audit script'i
- Tam bash remediation script'i
- Yapılandırılmış metadata (section, level, tags, config_files)
- auto_remediate / manual_review flag'leri

> **windows_server_2025_rules.yaml** şu an boş ve devre dışı; Windows Server hardening için sadece PDF kaynak kullanılmaktadır.

---

## RAG Mimarisi

### Gerçek Implementasyon

```
Kaynak Dokümanlar
  ├── PDF (CIS Ubuntu 24.04)  →  CISSectionChunker  →  chunks
  ├── PDF (CIS Windows 2025)  →  CISSectionChunker  →  chunks
  └── YAML (ubuntu rules)     →  YamlRulesChunker   →  chunks (1 kural = 1 chunk)
                                          │
                                          ▼
                           Novita qwen3-embedding-8b
                           (4096-dim dense vectors)
                                          │
                                          ▼
                           Qdrant Cloud Vector Store
                    collection: cis_ubuntu_24_04_and_cis_windows_2025_benchmarks
                                          │
                              (query time: semantic search)
                                          │
                                          ▼
                              RAG Context → LLM Prompt
```

---

### 1. Offline Phase — Index Oluşturma

**Script**: `scripts/build_index.py`

```bash
# Tüm enabled source'ları indexler (PDF + YAML)
python scripts/build_index.py
```

`config/config.json`'daki `rag.source_documents` listesindeki `enabled: true` olan tüm kaynaklar otomatik olarak işlenir.

#### Chunker Türleri

**CISSectionChunker** (`rag/chunking/cis_section_chunker.py`):
- CIS Benchmark PDF'lerini section bazlı böler
- Her CIS kontrol maddesi ayrı chunk
- Metadata: section numarası, başlık, OS, kaynak

**YamlRulesChunker** (`rag/chunking/yaml_rules_chunker.py`):
- YAML kural dosyasını okur, her kural için 1 chunk üretir
- Her chunk şunları içerir: Rule ID, Title, Description, Audit Command, Remediation Command, tam Audit Script, tam Remediation Script (max 3000 char)
- Metadata: rule_id, section, category, level, auto_remediate, tags, kernel_module, config_files

**Örnek YAML Chunk metni:**
```
Rule ID: 5.2.4
Title: Ensure SSH root login is disabled
Section: 5.2 | Category: Access, Authentication and Authorization | Level: 1

Description:
'PermitRootLogin' SSH directive 'no' olarak ayarlanmalıdır.

SSH Directive: PermitRootLogin
Config Files: /etc/ssh/sshd_config, /etc/ssh/sshd_config.d
Remediation: automated
Tags: ssh, access-control, root

Audit Command: grep -Psi "^\h*PermitRootLogin\h+yes\h*$" ...

Remediation Script:
#!/usr/bin/env bash
# CIS 5.2.4 Remediation - Ensure SSH root login is disabled
...
```

#### Embedding

**Model**: Novita `qwen/qwen3-embedding-8b`
- **Dimension**: 4096
- **Provider**: Novita API (`https://api.novita.ai/openai`)
- **Batch size**: 100 chunk/request
- **Implementasyon**: `rag/embeddings/novita_embeddings.py`
- **Alternatif client**: `rag/embeddings/cohere_embeddings.py` (config ile değiştirilebilir, aktif değil)

#### Vector Store Upload

**Teknoloji**: Qdrant Cloud
- **Collection**: `cis_ubuntu_2404_windows11_winserver2025_with_rules`
- **Distance metric**: Cosine similarity
- **Vector dim**: 4096
- **Implementasyon**: `rag/vector_store/qdrant_store.py`

**Index İstatistikleri (yaklaşık):**
```
PDF chunks (Ubuntu 24.04):       ~800-1200 chunk
PDF chunks (Windows Server 2025): ~1000-1500 chunk
PDF chunks (Windows 11 Desktop):  ~900-1300 chunk
YAML chunks (Ubuntu rules):       312 chunk (1 kural = 1 chunk)
YAML chunks (Windows 11 rules):   ~ chunk (aktif)
Toplam:                           ~3000-4500 chunk
Embedding dim:                    4096
```

---

### 2. Online Phase — Query Time

**Implementasyon**: `rag/retrieval/rag_retriever.py` + `llm/rag/integration.py`

#### 2a. Query Planning (Opsiyonel — `rag.enhanced.use_query_planning: true`)

`rag/query/query_planner.py` — `QueryPlanner`

Kullanıcı sorusu tek bir query yerine 4-5 stratejiye bölünür:

| Strateji | Amaç | Örnek |
|----------|------|-------|
| **Original** | Orijinal sorgu | "Ubuntu 24.04 SSH hardening nasıl?" |
| **Subquery** | Atomik alt sorular | "SSH PermitRootLogin nasıl kapatılır?" |
| **HyDE** | Hipotetik cevap metni | "PermitRootLogin no olarak /etc/ssh/sshd_config..." |
| **Stepback** | Genel/soyut sorgu | "Linux SSH servis güvenliği genel prensipleri" |

Her strateji ayrı embed edilip aranır → sonuçlar birleştirilir (deduplication).

```python
plan = query_planner.plan("Ubuntu 24.04 SSH hardening nasıl?")
# plan.all_queries() → [original, subq1, subq2, hyde1, stepback1]
```

#### 2b. Per-Source Embedding + Search

Kullanıcı sorusu (veya genişletilmiş sorgular) aynı Novita modeli ile embed edilir:

```python
query_vector = embed_client.embed_query("Ubuntu SSH root login nasıl devre dışı bırakılır?")
# → 4096-dim vector
```

Her kaynak ayrı ayrı aranır — YAML ve PDF dengeli chunk getirir:

```python
yaml_results = qdrant_store.search(query_vector, top_k=3, doc_type="yaml_rule")
pdf_results  = qdrant_store.search(query_vector, top_k=3, doc_type="cis_benchmark")
```

**Fail-Open**: 0 sonuç gelirse `search_with_fallback()` min_score'u otomatik düşürür (%70 → %50), sorgu ölü sonuçla bitmez.

#### 2c. Hybrid Scoring (Opsiyonel — `rag.enhanced.use_hybrid: true`)

`rag/retrieval/hybrid_retriever.py` — `InContextHybridScorer`

Qdrant'ın dense sonuçları üzerinde BM25 re-scoring uygulanır. CIS'e özgü tam token eşleşmelerini yakalar:

```
/etc/ssh/sshd_config, PermitRootLogin, auditd, UFW, PAM → dense search kaçırabilir, BM25 yakalar
```

Reciprocal Rank Fusion (RRF) ile dense ve sparse skorlar birleştirilir:

```
fused_score = 0.6 / (60 + dense_rank) + 0.4 / (60 + bm25_rank)
```

#### 2d. MMR Reranking (Opsiyonel — `rag.enhanced.use_mmr: true`)

`rag/retrieval/reranker.py` — `MMRReranker`

Aynı CIS bölümünün PDF ve YAML versiyonu sık sık top-K'ya birlikte girer. MMR bu tekrarı elimine eder — **relevance × diversity** dengesi:

```
MMR(i) = λ × relevance(i) − (1−λ) × max_similarity(i, seçilenler)
```

- `λ = 0.7` → relevance ağırlıklı, ama diversity korunur
- Çeşitlilik ölçüsü: Jaccard token benzerliği (extra embed çağrısı yok)
- `max_per_source = 3` → tek kaynaktan max 3 chunk

#### 2e. Smart RAG Triggering

RAG **her sorguda çalışmaz** — `info_pipeline.py` (Layer 3B) ve `action_pipeline.py` (Layer 3C) RAG context ister. Pattern Responder (selamlama, teşekkür) RAG'ı bypass eder. Bu sayede sorguların ~%45'i RAG'ı atlar, gecikme ve maliyet azalır.

#### 2f. Context Construction

`llm/rag/integration.py` — `RAGContextBuilder`:

```python
# LLM prompt'una enjekte edilen context formatı
"""
[Kaynak 1 - Skor: 0.91]
Doküman: CIS Ubuntu 24.04 Benchmark
Bölüm: 5.2.4
İçerik: PermitRootLogin no olarak ayarlanmalıdır...
"""
```

API yanıtında `rag_sources` alanı olarak da döner:
```json
{
  "rag_sources": [
    {"id": "cis_ubuntu_24_04-p42", "score": 0.91, "source": "CIS Ubuntu 24.04", "section": "5.2.4", "text": "..."},
    {"id": "ubuntu_rules_yaml-5.2.4", "score": 0.88, "source": "ubuntu_24_04_rules", "section": "5.2", "text": "..."}
  ]
}
```

---

## RAG Parametreleri

### API'den Kontrol

```json
{
  "question": "SSH root login nasıl devre dışı bırakılır?",
  "use_rag": true,
  "rag_top_k": 5,
  "rag_min_score": 0.7
}
```

### config.json Ayarları

```json
{
  "rag": {
    "retrieval": {
      "top_k": 3,
      "min_score": 0.5,
      "max_results": 6
    },
    "enhanced": {
      "enabled": true,
      "use_hybrid": true,
      "dense_weight": 0.6,
      "sparse_weight": 0.4,
      "use_mmr": true,
      "mmr_lambda": 0.7,
      "mmr_max_per_source": 3,
      "use_query_planning": true,
      "subqueries": true,
      "hyde": true,
      "stepback": true,
      "max_subqueries": 2,
      "use_claim_verification": true,
      "min_verification_confidence": 0.6
    }
  }
}
```

### Enhanced RAG Özelliklerini Ayrı Ayrı Açma

| Flag | Açıklama | Ekstra Maliyet | Öneri |
|------|----------|----------------|-------|
| `use_hybrid` | BM25 + RRF füzyonu | Yok (CPU) | Önce aç |
| `use_mmr` | Diversity reranking | Yok (CPU) | Sonra aç |
| `use_query_planning` | Subquery + HyDE + Stepback | +3-4 LLM çağrısı | Demo için aç |
| `use_claim_verification` | İddia doğrulama | +2-6 LLM çağrısı | Seçici kullan |

### Top-K Trade-off

| K | Avantaj | Dezavantaj |
|---|---------|------------|
| 1-3 | Hızlı, odaklı | Bilgi kaybı riski |
| 5 (default) | Dengeli | Optimal çoğu senaryoda |
| 10+ | Kapsamlı | Yavaş, alakasız chunk riski |

---

## PDF vs YAML — Tamamlayıcı Kaynaklar

| Özellik | CIS PDF | YAML Kurallar |
|---------|---------|---------------|
| Genel açıklama | ✅ Detaylı | ✅ Özet |
| Rationale / Neden? | ✅ Detaylı | ❌ |
| Tam audit script | ❌ Sadece komut | ✅ Tam bash script |
| Tam remediation script | ❌ Sadece adımlar | ✅ Tam bash script |
| Yapılandırılmış metadata | ❌ | ✅ (level, tags, config_files) |
| auto_remediate flag | ❌ | ✅ |
| Semantic search kalitesi | ✅ Yüksek (zengin metin) | ✅ Yüksek (structured) |

**Sonuç**: Her iki kaynağı birlikte indexlemek en iyi retrieval sonucunu verir. PDF bağlam/rationale, YAML ise çalışabilir script sağlar.

---

## Yeni Kaynak Ekleme

### YAML Kural Dosyası Eklemek

1. `data/rules/` altına YAML dosyası yerleştir (mevcut `ubuntu_24_04_rules.yaml` formatını takip et)
2. `config/config.json`'a source ekle:

```json
{
  "id": "windows_rules_yaml",
  "name": "Windows Server 2025 CIS Hardening Rules",
  "type": "yaml",
  "path": "data/rules/windows_2025_rules.yaml",
  "enabled": true,
  "chunker": "yaml_rules",
  "priority": 4
}
```

3. `python scripts/build_index.py` çalıştır

### PDF Eklemek

```json
{
  "id": "cis_centos_9",
  "name": "CIS CentOS 9 Benchmark",
  "type": "pdf",
  "path": "data/source/CIS_CentOS_9_Benchmark.pdf",
  "enabled": true,
  "chunker": "cis_section",
  "priority": 5
}
```

---

## Performans

| İşlem | Süre | Maliyet |
|-------|------|---------|
| Query embedding (Novita) | ~100ms | ~$0.0001 |
| Vector search (Qdrant) | ~30-50ms | $0 |
| Context construction | <1ms | $0 |
| **Toplam RAG** | **~150ms** | **~$0.0001** |

**Index oluşturma (one-time):**

| İşlem | Miktar | Süre | Maliyet |
|-------|--------|------|---------|
| PDF chunking | 2 PDF | ~2-3 dk | $0 |
| YAML chunking | 312 kural | ~1 dk | $0 |
| Embedding (Novita) | ~2500 chunk | ~5-8 dk | ~$0.01 |
| Qdrant upload | ~2500 chunk | ~1-2 dk | $0 |
| **Toplam** | | **~10-15 dk** | **~$0.01** |

---

## Mevcut Durum

### Çalışır Durumda (v1.1)
- Ubuntu 24.04 CIS PDF indexleme ✅
- Windows Server 2025 CIS PDF indexleme ✅
- Windows 11 Desktop CIS PDF indexleme ✅
- Ubuntu 24.04 YAML kurallar indexleme (312 kural) ✅
- Windows 11 YAML kurallar indexleme ✅
- Novita 4096-dim embedding ✅
- Qdrant Cloud vector store
- Smart RAG triggering (%45 bypass)
- **✅ Hybrid BM25 + Dense RRF scoring** (`rag.enhanced.use_hybrid`)
- **✅ MMR Reranking** (Jaccard çeşitlilik) (`rag.enhanced.use_mmr`)
- **✅ Query Planning** (Subquery + HyDE + Stepback) (`rag.enhanced.use_query_planning`)
- **✅ Claim Verification** (halüsinasyon kontrolü) (`rag.enhanced.use_claim_verification`)
- **✅ Fail-Open Search** (0 sonuçta min_score otomatik gevşer)

### Kalan İyileştirmeler

| Eksik | Etki | Öneri |
|-------|------|-------|
| `windows_server_2025_rules.yaml` boş | Windows Server için tam script yok | YAML doldurulmalı |
| Redis embedding cache | Her sorguda re-embed (~2.1s) | Redis ile cache |
| OS bazlı metadata filtreleme | Windows sorusuna Ubuntu chunk gelebilir | Qdrant metadata filter |

---

## Troubleshooting

### Problem 1: Düşük Retrieval Kalitesi

**Belirti**: Alakasız chunk'lar dönüyor

**Çözümler:**
1. `rag_min_score`'u artır (0.5 → 0.7)
2. `rag_top_k`'yı azalt (10 → 5)
3. Index'i yeniden oluştur: `python scripts/build_index.py`

### Problem 2: Hiç Sonuç Dönmüyor

**Belirti**: `rag_sources` boş

**Çözümler:**
1. `rag_min_score`'u düşür (0.7 → 0.5)
2. Qdrant collection var mı kontrol et
3. `NOVITA_API_KEY` ve `QDRANT_API_KEY` .env'de tanımlı mı kontrol et

### Problem 3: Index Oluşturma Hatası

**Belirti**: `build_index.py` hata veriyor

**Çözümler:**
1. `PYTHONPATH` ayarla: `export PYTHONPATH="${PYTHONPATH}:$(pwd)"`
2. Qdrant collection boyutunu kontrol et (4096-dim olmalı)
3. Eski collection'ı sil ve yeniden oluştur

---

## Özet

| Özellik | Değer |
|---------|-------|
| **Embedding Modeli** | Novita `qwen/qwen3-embedding-8b` |
| **Embedding Boyutu** | 4096 |
| **Vector Database** | Qdrant Cloud |
| **Collection** | `cis_ubuntu_2404_windows11_winserver2025_with_rules` |
| **Kaynak Türleri** | PDF (CIS Benchmarks) + YAML (Hardening Rules) |
| **Indexlenen Kaynaklar** | 3 PDF + 2 YAML (Ubuntu 312 kural + Windows 11) |
| **Toplam Chunk (yaklaşık)** | ~3000-4500 |
| **Retrieval Süresi** | ~150ms |
| **RAG Bypass Oranı** | ~%45 (greetings, pattern responses) |

---

## İlgili Dosyalar

| Dosya | Amaç |
|-------|------|
| `rag/chunking/cis_section_chunker.py` | CIS PDF section chunker |
| `rag/chunking/yaml_rules_chunker.py` | YAML kural chunker |
| `rag/embeddings/novita_embeddings.py` | Novita embedding client |
| `rag/vector_store/qdrant_store.py` | Qdrant vector store |
| `rag/retrieval/rag_retriever.py` | RAG retrieval logic + fail-open |
| `rag/retrieval/reranker.py` | **MMR Reranker** (Jaccard diversity) |
| `rag/retrieval/hybrid_retriever.py` | **In-context BM25 + RRF hybrid scorer** |
| `rag/query/query_planner.py` | **Query Planner** (subquery, HyDE, stepback) |
| `rag/verify/claim_verifier.py` | **Claim Verifier** (halüsinasyon kontrolü) |
| `llm/rag/integration.py` | Pipeline'a context enjeksiyonu (enhanced) |
| `rag/indexing/index_pipeline.py` | Index oluşturma pipeline |
| `scripts/build_index.py` | Index oluşturma script |
| `config/config.json` | RAG, enhanced RAG ve embedding ayarları |
| `data/source/` | CIS Benchmark PDF'leri |
| `data/rules/` | YAML hardening kural dosyaları |

---

## Sonraki Adımlar

- [LLM Uygulamaları](06_LLM_UYGULAMALARI.md) - RAG + LLM entegrasyonu
- [Kurulum ve Kullanım](03_KURULUM_VE_KULLANIM.md) - Index oluşturma adımları
- [Gelecek İyileştirmeler](09_GELECEK_IYILESTIRMELER.md) - Hybrid search, Redis cache
