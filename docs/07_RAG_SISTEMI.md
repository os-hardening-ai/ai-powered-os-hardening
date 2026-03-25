# RAG (Retrieval-Augmented Generation) Sistemi

## Genel Bakış

RAG, **LLM'lerin bilgi tabanını genişletmek** için kullanılan bir tekniktir. LLM'in eğitim datasında olmayan veya güncel olmayan bilgileri **dış kaynaklardan (CIS Benchmark dokümanları + hardening kuralları) çekerek** yanıtlara dahil eder.

```
┌──────────────────────────────────────────────────────────────┐
│                     RAG PIPELINE                              │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  1. USER QUESTION                                             │
│     "Ubuntu 24.04 SSH hardening best practices?"             │
│                      │                                        │
│                      ▼                                        │
│  2. EMBEDDING (Novita qwen3-embedding-8b)                    │
│     Text → 4096-dimensional vector                           │
│     [0.123, -0.456, 0.789, ...]                              │
│                      │                                        │
│                      ▼                                        │
│  3. SEMANTIC SEARCH (Qdrant Cloud)                           │
│     Find similar chunks from CIS Benchmarks + YAML rules     │
│     ├─ Chunk 1 (score: 0.91) - CIS PDF Section 5.2.4        │
│     ├─ Chunk 2 (score: 0.87) - YAML Rule sshd_config        │
│     └─ Chunk 3 (score: 0.82) - CIS PDF Section 5.2.3        │
│                      │                                        │
│                      ▼                                        │
│  4. CONTEXT CONSTRUCTION                                      │
│     Combine retrieved chunks                                  │
│     "CIS Ubuntu 24.04 Section 5.2.4: PermitRootLogin no..." │
│                      │                                        │
│                      ▼                                        │
│  5. LLM GENERATION (Groq Llama 70B / Novita Qwen)           │
│     Prompt: Context + User Question                           │
│     Output: Detailed, source-backed answer                    │
│                                                               │
└──────────────────────────────────────────────────────────────┘
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

| Dosya | OS | Chunk Yöntemi |
|-------|----|---------------|
| `CIS_Ubuntu_Linux_24.04_LTS_Benchmark_v1.0.0.pdf` | Ubuntu 24.04 | `cis_section` |
| `CIS_Microsoft_Windows_Server_2025_Benchmark_v2.0.0.pdf` | Windows Server 2025 | `cis_section` |

PDF'ler CIS section yapısına göre bölünür. Her chunk: başlık, açıklama, rationale, audit prosedürü, remediation adımları içerir.

### 2. YAML Kural Dosyaları (`data/rules/`)

| Dosya | OS | Kural Sayısı | Chunk Yöntemi |
|-------|----|-------------|---------------|
| `ubuntu_24_04_rules.yaml` | Ubuntu 24.04 | 312 kural | `yaml_rules` |

YAML dosyaları PDF'leri **tamamlar** — her CIS kuralı için:
- Tam bash audit script'i
- Tam bash remediation script'i
- Yapılandırılmış metadata (section, level, tags, config_files)
- auto_remediate / manual_review flag'leri

> **windows_2025_rules.yaml** şu an boş; Windows hardening için sadece PDF kaynak kullanılmaktadır.

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
- **Fallback**: Cohere (`rag/embeddings/cohere_embeddings.py`)

#### Vector Store Upload

**Teknoloji**: Qdrant Cloud
- **Collection**: `cis_ubuntu_24_04_and_cis_windows_2025_benchmarks`
- **Distance metric**: Cosine similarity
- **Vector dim**: 4096
- **Implementasyon**: `rag/vector_store/qdrant_store.py`

**Index İstatistikleri (yaklaşık):**
```
PDF chunks (Ubuntu 24.04):   ~800-1200 chunk
PDF chunks (Windows 2025):   ~1000-1500 chunk
YAML chunks (Ubuntu rules):  312 chunk (1 kural = 1 chunk)
Toplam:                      ~2100-3000 chunk
Embedding dim:               4096
```

---

### 2. Online Phase — Query Time

**Implementasyon**: `rag/retrieval/rag_retriever.py` + `llm/rag/integration.py`

#### Query Embedding

Kullanıcı sorusu aynı Novita modeli ile embed edilir:

```python
query_vector = embed_client.embed_texts(["Ubuntu SSH root login nasıl devre dışı bırakılır?"])
# → 4096-dim vector
```

#### Semantic Search

```python
results = qdrant_store.search(
    query_vector=query_vector,
    top_k=5,              # config: rag.retrieval.top_k
    min_score=0.5         # config: rag.retrieval.min_score
)
```

Sonuçlar her iki kaynaktan (PDF + YAML) karma gelebilir. RAG en alakalı chunk'ları döndürür.

#### Smart RAG Triggering

RAG **her sorguda çalışmaz** — `info_pipeline.py` (Layer 3B) ve `action_pipeline.py` (Layer 3C) RAG context ister. Pattern Responder (selamlama, teşekkür) RAG'ı bypass eder. Bu sayede sorguların ~%45'i RAG'ı atlar, gecikme ve maliyet azalır.

#### Context Construction

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
      "top_k": 5,
      "min_score": 0.5,
      "max_results": 10
    }
  }
}
```

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

## Mevcut Durum ve Eksiklikler

### Çalışır Durumda
- Ubuntu 24.04 CIS PDF indexleme
- Windows Server 2025 CIS PDF indexleme
- Ubuntu 24.04 YAML kurallar indexleme (312 kural)
- Novita 4096-dim embedding
- Qdrant Cloud vector store
- Smart RAG triggering (%45 bypass)

### Eksik / Gelecek İyileştirmeler

| Eksik | Etki | Öneri |
|-------|------|-------|
| `windows_2025_rules.yaml` boş | Windows kurallar için tam script yok | YAML doldurulmalı |
| Redis embedding cache | Her sorguda re-embed (~2.1s) | Redis ile cache |
| Hybrid search | Exact keyword match zayıf | Semantic + BM25 |
| OS bazlı filtreleme | Windows sorusuna Ubuntu chunk gelebilir | Metadata filter |
| Re-ranking | İlk retrieval sıralaması optimal değil | Cross-encoder |

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
| **Collection** | `cis_ubuntu_24_04_and_cis_windows_2025_benchmarks` |
| **Kaynak Türleri** | PDF (CIS Benchmarks) + YAML (Hardening Rules) |
| **Indexlenen Kaynaklar** | 2 PDF + 1 YAML (312 kural) |
| **Toplam Chunk (yaklaşık)** | ~2500 |
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
| `rag/retrieval/rag_retriever.py` | RAG retrieval logic |
| `llm/rag/integration.py` | Pipeline'a context enjeksiyonu |
| `rag/indexing/index_pipeline.py` | Index oluşturma pipeline |
| `scripts/build_index.py` | Index oluşturma script |
| `config/config.json` | RAG ve embedding ayarları |
| `data/source/` | CIS Benchmark PDF'leri |
| `data/rules/` | YAML hardening kural dosyaları |

---

## Sonraki Adımlar

- [LLM Uygulamaları](06_LLM_UYGULAMALARI.md) - RAG + LLM entegrasyonu
- [Kurulum ve Kullanım](03_KURULUM_VE_KULLANIM.md) - Index oluşturma adımları
- [Gelecek İyileştirmeler](09_GELECEK_IYILESTIRMELER.md) - Hybrid search, Redis cache
