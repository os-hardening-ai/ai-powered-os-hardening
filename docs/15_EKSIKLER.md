# 15 — Eksikler ve Yapılacaklar (Kalan İş Listesi)

**Güncelleme:** 2026-05-30
**Kaynak:** Bitirme Proje Öneri Formu (İP 1-13 + H1-H4), ara raporlar (Kasım'25 / Ocak'26 / Mart'26), kod incelemesi.

Bu belge, **gerçek kod durumu** ile vaatleri karşılaştırarak kalan işleri önceliklendirir.
İşaretler: ✅ tamam · ⚠️ kısmen/yarım · ❌ eksik.

---

## A) Öneri Formu — ZORUNLU (hoca notu için bağlayıcı)

Bunlar öneri formunda yazılı; tamamlanmadan proje "tam" sayılmaz.

| # | İş | Form ref | Durum | Not |
|---|----|----------|-------|-----|
| A1 | **Web Arayüzü (React+TS)** | İP-10 | ❌ | Chat UI, OS/rol seçimi, öneri görüntüleme, geri bildirim. *Frontend ayrı repoda ise bu madde oradan kapanır.* |
| A2 | **Değerlendirme / ölçüm harness'i** | İP-5/6/7/8 | ✅⚠️ | **Ölçüldü** (`evaluation/ip_metrics.py`, bkz. [14_DEGERLENDIRME.md](14_DEGERLENDIRME.md)): İP-6 %100, İP-7 %100, İP-8 %100 (eşik üstü ✅). İP-5 groundedness **0.59** ⚠️ (önce 0.41 — ölçüm hatası düzeltildi: claim extraction + bağlam kesme + OS filtresi). Somut sorularda H1'de 0.89; soyut hedeflerde hâlâ düşük. |
| A3 | **H1 — RAG vs saf-LLM** | H1 | ✅ | Kanıt toplandı (bkz. [14_DEGERLENDIRME.md](14_DEGERLENDIRME.md) / `evaluation/h1_rag_vs_llm.py`): groundedness 0.72→0.89, CIS atıf 0.33→0.83. n=6, büyütülebilir. |
| A4 | **H3 — P95 < 5sn** | H3 | ✅⚠️ | **ÇÖZÜLDÜ** (`load_test.py` + `provider_benchmark.py`, ~10 sağlayıcı ampirik kıyas): doğru sağlayıcı (**Cerebras gpt-oss-120b**, özel donanım) + **fail-fast fallback** (`max_retries=0`) ile **128-148s → tek çağrı 1.36s; agent_plan 3.55s, agent_harden 4.62s medyan**. Tek-çağrılı yollar <5s ✅; çok-adımlı agent borderline (~4.6s; P95 RPM+n=3 gürültüsü). RAG retrieval zaten ~1s. Detay [14_DEGERLENDIRME.md](14_DEGERLENDIRME.md). |
| A5 | **H2 / H4 — karar süresi & kabul oranı** | H2, H4 | ⚠️ | Kullanıcı çalışması gerektirir. **Enstrüman hazır** (`evaluation/survey_eval.py` + [16_KULLANICI_CALISMASI.md](16_KULLANICI_CALISMASI.md)); ekip pilotu (n~5-10) koşunca kapanır. |
| A6 | **İP-12 — performans testi + kullanıcı anketi** | İP-12 | ⚠️ | Perf testi ✅ (`evaluation/load_test.py`). Memnuniyet >%70 anketi: **enstrüman hazır** (A5 ile aynı çalışma), pilot bekliyor. |

> **Öneri Formunda VAR ve TAMAM olanlar:** İP-1 doküman, İP-2 chunking, İP-3 embedding+Qdrant,
> İP-4 RAG pipeline, İP-5 LLM entegrasyon (4 sağlayıcı + fallback), İP-6 Görev Planlayıcı,
> İP-7 Tool-Use/multi-step + self-verify, İP-8 ZT açıklayıcı (CIS-NIST-ISO + rollback),
> İP-9 FastAPI, İP-11 gözlemlenebilirlik (OTel+Prometheus). Artifact üretici (Bash/PS/Ansible/REG/GPO) ✅.

---

## B) Değer Katan — Opsiyonel (formda zorunlu değil ama projeyi güçlendirir)

| # | İş | Durum | Not |
|---|----|-------|-----|
| B1 | Windows Server 2025 YAML kuralları | ❌ | Dosya var, **0 kural (boş)**. Win11 ✅ 516 kural. |
| B2 | Compliance Report (PDF/HTML/MD) | ❌ | Öneri formu "rapor çıktısı"na değiniyor; raporlama modülü yok. |
| B3 | JWT + RBAC | ⚠️ | **API-key auth var** (eklendi); JWT login/logout + rol-bazlı (sysadmin/developer/security/end_user) yok. Form'da "RBAC" anahtar kelimesi geçiyor. |
| B4 | Gerçek SSE token streaming | ⚠️ | Mevcut `/api/chat/stream` cevabı `.split()` ile böler — **gerçek LLM token-stream değil**. Düzeltilmeli. |
| B5 | Audit Log (kim-ne-zaman) | ❌ | Request log var ama denetim tablosu yok. |
| B6 | User-based rate limiting | ⚠️ | Redis rate limiter IP-bazlı var; kullanıcı-bazlı için auth (B3) gerekir. |
| B7 | Ground-truth dataset 12 → 50-100 | ⚠️ | Şu an H1 için 12 Q/A. Genişletme akademik gücü artırır. |
| B8 | RAGAS + Ablation **runner + gerçek koşum** | ⚠️ | `evaluation/ragas_evaluator.py` + `ablation_study.py` sınıfları var, CLI runner + sonuç yok. **Not:** `ragas` paketi kurulu değil → custom implementasyon (akademik dürüstlük için belirtilmeli). |

---

## C) Temizlik — TAMAMLANDI ✅

| # | İş | Durum |
|---|----|-------|
| C1 | Embedding cache ölü import (`rag/cache` yok) | ✅ `embedding.cache_enabled=false` → başlangıçta "no module" uyarısı durdu. Kod guard'lı, downstream etkilenmez. |
| C2 | CORS/TrustedHost prod kilidi | ✅ Env-driven (`ALLOWED_HOSTS`, config CORS) + startup uyarısı + wildcard'da credentials kapalı. Production notu [13_GUVENLIK.md](13_GUVENLIK.md)'de. |

---

## D) İPTAL EDİLEN — Kapsam Dışı

docs/09 (Gelecek İyileştirmeler) maddeleri değerlendirildi. Öneri formunda **zorunlu olmayan** ve
projeye **belirgin değer katmayan** maddeler iptal edildi (docs/09 dosyası kaldırıldı):

| İptal edilen | Gerekçe |
|--------------|---------|
| Redis **Response** Cache | Formda yok; H3 latency zaten hedefte. |
| RAG Pre-warming (hot query) | Mikro-optimizasyon, düşük değer. |
| Error Retry Logic (tenacity) | Zaten kapalı: SDK `max_retries` + sağlayıcı fallback zinciri mevcut. |
| Fine-tuned Intent (%95) | %90.48 yeterli; yüksek emek/düşük getiri. |
| Multi-agent (coordinator+uzman) | Form İP-6/7 = tek-ajan agentic (zaten var); çok yüksek emek, sadece araştırma. |
| A/B Testing Framework | Akademik kapsam için gereksiz. |
| Kubernetes Horizontal Scaling | Tek-instance demo yeterli. |
| Multi-language | Düşük öncelik; ertelendi. |
| User Feedback auto-retrain | Frontend'in küçük "geri bildirim" parçası A1 kapsamında; otomatik yeniden-eğitim iptal. |

---

## Özet Öncelik

1. **A1 Frontend** (form-zorunlu, en görünür) — *ayrı repo durumu netleştirilmeli*
2. **A2 Ölçüm harness'i** (form-zorunlu, en zayıf nokta — İP-5/6/7/8 + H2/H3/H4 sayısal kanıt)
3. **A6 / A4** yük testi + anket
4. **B1-B8** değer katan opsiyoneller (zaman kalırsa)
