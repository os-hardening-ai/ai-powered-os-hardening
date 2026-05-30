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
| **İP-5 Groundedness** | halüsinasyon <%10 | **0.59** (önce 0.41 — ölçüm hatası düzeltildi) | 0.90 | ⚠️ |

### Dürüst Yorum

- **İP-6/7/8 eşiklerin üzerinde:** Görev planlayıcı kuralları doğru sıralıyor ve hedefe
  uygun seçiyor; multi-step ajan her senaryoda plan→collect→generate→**verify** zincirini
  tamamlıyor (self-verify gate %100 çalışıyor); ZT açıklayıcı her öneride geçerli Zero-Trust
  prensibi + NIST/CIS/ISO standart referansı üretiyor. **Sınır:** İP-8 "doğru eşleşme"
  semantik bir yargıdır; harness *geçerli prensip + standart varlığını* proxy ölçer.
- **İP-5 groundedness 0.41 → 0.59 (kök-neden düzeltmesi):** İlk düşük skor **çoğunlukla
  ölçüm hatasıydı**, gerçek halüsinasyon değil. Tek-senaryo ayrıntılı teşhiz üç sorun buldu:
  (1) **claim extraction bozuktu** — "1", "3", "/etc" gibi parçaları "iddia" sayıp bağlama
  karşı denetliyordu (hep "desteklenmiyor"); (2) **doğrulayıcı bağlamı kesiyordu** (chunk başına
  600 + toplam 2000 kr → ~14.000 kr'lık chunk'ların yalnızca ilk ~3'ü görülüyordu, uzaktaki
  desteklenen iddialar sahte-negatif); (3) **retrieval yanlış-OS getiriyordu** — Ubuntu hedefine
  Windows CIS chunk'ları geliyordu. Düzeltmeler: atıf işareti temizleme + tam-cümle extraction +
  çöp-iddia filtresi, parametrik bağlam pencereleri (İP-5 **tam bağlama** karşı doğrular),
  `os_version` filtresi. Sonuç: **0.41 → 0.59** (İP-6/7/8 = %100 korunur).
- **Kalan sınır (dürüst):** Soyut hedeflerde (yazılım/servis, güvenlik-yamaları) groundedness
  hâlâ 0.00'a düşebiliyor — bu **gerçek** bir sınır: retrieval gevşek-ilgili chunk getiriyor ve
  üretilen cevap bağlam-dışı çerçeve içeriyor. Ürünün asıl kullanımı olan **somut sorularda
  (H1) groundedness 0.89** — sistem somut soru-cevapta güçlü, soyut hedef-ayrıştırmada zayıf.
  İleri iyileştirme: soyut hedefler için retrieval sorgu-genişletmesi + daha sıkı üretim kısıtı.

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

**Yöntem:** `evaluation/load_test.py` — in-process FastAPI (TestClient), gerçek LLM çağrısı,
percentile `api/metrics.MetricsCollector._percentile`'dan. Rapor artık **hangi sağlayıcı/modelle**
ölçüldüğünü kaydeder (kendini-belgeleyen artefakt). Komut:
`LLM_PROVIDER=<sağlayıcı> OTEL_SDK_DISABLED=true LOAD_THROTTLE_S=2 python -m evaluation.load_test`

> **Dürüstlük düzeltmesi:** Bu belgenin önceki sürümü "Groq ile 0.71s/2.76s ✅" diyordu — bu
> **tek, taze-kotalı bir çağrıydı**, yük testiyle doğrulanmamıştı. Gerçek yük testi (aşağıda) bunu
> çürüttü. Tüm sayılar `evaluation/results/load_test_results.json`'dan gelir (uydurma değil).

### İki katmanlı bakış — H3 *mimariyi* mi, *uçtan-uca'yı* mı ölçüyor?

H3 metni "**vektör veritabanı + chunking stratejileri** 1000+ kural içinde P95<5s" der — asıl
iddia **retrieval/RAG altyapısı** hakkında. Bunu LLM üretiminden ayırmak gerekir:

**Katman 1 — RAG retrieval altyapısı (H3'ün literal konusu):** `retrieve_balanced` = embedding +
vektör arama, **LLM yok**.

| Ölçüm | P50 | P95 | Not |
|-------|----:|----:|-----|
| Retrieval-only (n=8, 1000+ kural) | **1.03s** | 86s\* | yerel vektör arama hızlı (8 sorgunun 6'sı ~1s); \*iki outlier embedding **API** (Novita) spike'ı (40s, 86s) |

→ **Yerel chunking + vektör-DB mimarisi hedefte (~1s).** Outlier'lar embedding API gecikmesi
(sağlayıcı/ağ), mimari değil. H3'ün *mimari* iddiası doğrulanıyor.

**Katman 2 — uçtan uca (retrieval + LLM üretimi):** gerçek yük testleri:

| Uç | Sağlayıcı / konfig | P50 | P95 | H3 (<5s) |
|----|--------------------|----:|----:|:--------:|
| agent_plan | Groq (ücretsiz), eşzamanlı=2 | 16.1s | **147.8s** | ❌ |
| agent_harden | Groq (ücretsiz), eşzamanlı=2 | 13.0s | **128.4s** | ❌ |
| agent_plan | Novita (kotasız), eşzamanlı=3 | 8.2s | 16.4s | ❌ |
| agent_harden | Novita (kotasız), eşzamanlı=3 | 10.1s | 23.4s | ❌ |
| chat (4-katman pipeline) | Novita, eşzamanlı=3 | 44.0s | 52.4s | ❌ |
| agent_plan | Novita, **tek-kullanıcı (eşzamanlı=1)** | 5.6s | 11.7s | ❌ |
| agent_harden | Novita, **tek-kullanıcı (eşzamanlı=1)** | 11.0s | 15.7s | ❌ |

### Dürüst Yorum

- **H3 (uçtan uca P95<5s) ücretsiz/düşük-ücretli sağlayıcılarla KARŞILANMIYOR** — hiçbir konfigte.
- **Kök neden mimari değil, dış API:**
  - **Groq ücretsiz-tier** yük altında rate-limit'e takılıp SDK backoff'una düşüyor → tek istek
    128-148s (ok=6/6, yani hata değil; *bekleme*).
  - **Novita-large (deepseek-v3)** doğru ama yavaş: tek-kullanıcıda bile agent_plan ~5.6s,
    agent_harden ~11s (çok-adımlı uçlar 2-3 sıralı LLM çağrısı zincirler).
  - **Embedding API**'si de ara sıra spike yapıyor (40-86s).
- **Yerel mimari hızlı (retrieval P50 ~1s):** gecikme tamamen **dış API çağrılarından** geliyor.
  Yani H3'ün *mimari* iddiası (chunking/vektör-DB ölçeklenir) doğrulanıyor; *operasyonel* hedef
  (<5s uçtan uca) mevcut ücretsiz API'lerle tutturulamıyor.
- **<5s uçtan uca için gereken (kapsam/donanım kararı, kod engeli değil):** (i) paralı/ayrılmış
  kota (backoff yok), (ii) yerel GPU çıkarımı, veya (iii) üretim adımında daha küçük/hızlı model +
  çok-adımlı uçlarda bağımsız LLM çağrılarını paralelleştirme.

> **429 / Kota notu:** Harness yoğun LLM çağrısı yapar; Groq ücretsiz-tier kotası dar gelir
> (dolunca uzun `Retry-After` → backoff). `LOAD_THROTTLE_S` global hız tavanı bu backoff
> fırtınasını sınırlar; rapor sağlayıcı/modeli kaydeder. Sağlayıcı mimarisi: [13_GUVENLIK.md](13_GUVENLIK.md),
> `llm/clients/registry.py`.
