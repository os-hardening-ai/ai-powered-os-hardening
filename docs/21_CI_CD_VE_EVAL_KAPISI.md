# 21 — CI/CD ve Eval-Regresyon Kapısı

**Güncelleme:** 2026-06
**İlgili kod:** `.github/workflows/ci.yml`, `evaluation/intent_eval.py`, `evaluation/intent_baseline.json`, `tests/unit/`
**İlgili ölçüm:** [14_DEGERLENDIRME.md](14_DEGERLENDIRME.md), [DEGERLENDIRME_SONUCLARI_2026-06.md](DEGERLENDIRME_SONUCLARI_2026-06.md)

Bu belge, projenin **"önce eval, sonra kod"** ilkesini makineyle zorlayan CI/CD altyapısını belgeler.

---

## 1. İlke: Eval direksiyonu otomatikleştir

Demir kural: *"intent/routing/scope doğruluğunu düşüren hiçbir commit merge edilmez."* Bu kural
GitHub Actions ile **her PR ve push'ta otomatik** uygulanır. Reaktif (soru sor → bug çıkar → yama)
yerine ölçüm-güdümlü geliştirme sağlanır.

## 2. CI iş akışı (`ci.yml`) — tek job, tamamen OFFLINE ($0)

```
on: [push:main, pull_request:main]
job: test-and-eval (ubuntu-latest, Python 3.11)
  1) pip install -r requirements-python311.txt
  2) Birim testleri:  pytest tests/unit/ -q        → 790 test (sahte LLM, deterministik)
  3) Eval REGRESYON KAPISI:  python -m evaluation.intent_eval --check
```

- **Offline/deterministik:** Testler sahte LLM + TF-IDF kullanır → gerçek API anahtarı GEREKMEZ,
  $0, ağ yok. `INTENT_ROUTER=tfidf` sabit.
- **Dummy env:** Config import-time birincil sağlayıcı için boş-olmayan anahtar ister; CI'da
  `*-dummy-not-used` değerleri verilir (gerçek çağrıda kullanılmaz, yalnız config geçsin diye).
- **Lane kapalı:** `LLM_SMALL_LANES=""`/`LLM_LARGE_LANES=""` → fake LLM yolu.

## 3. Eval-regresyon kapısı (`intent_eval --check`)

`evaluation/intent_baseline.json` dondurulmuş baseline'dır (in-domain niyet doğruluğu ~%97,3).
`--check` modu:
- Mevcut intent doğruluğunu offline (TF-IDF) ölçer.
- Baseline'ın altına düşerse **veya** bir örnek DOĞRU→YANLIŞ olursa → `exit 1` → CI kırmızı → merge bloke.

## 4. Test evrimi (kümülatif)

| Dönem | Birim testi | Kapsam |
|-------|------------:|--------|
| Kasım 2025 | — | prototip |
| Ocak 2026 | 112 | 4-katman + intent |
| Mayıs 2026 | 112 | korundu |
| **Haziran 2026** | **790** | + eval/RAGAS altyapısı, chat-history, auth, secret-scanner, reranker |

## 5. PR akışı (uygulanan disiplin)
Her değişiklik: feature branch → PR → CI (790 test + eval kapısı) yeşil → squash-merge → branch sil.
Bu dönemde bu akışla onlarca PR merge edildi; CI kapısı dependency bump'larının ve refactor'ların
güvenliğini doğruladı (örn. langchain kaldırma 781/781 testle doğrulandı).

## 6. Tez için anlam
Bu altyapı, bir lisans bitirme projesinde nadir görülen **mühendislik olgunluğudur**: sonuçlar
sezgiyle değil, otomatik regresyon kapısı + standart metriklerle (RAGAS) desteklenir.
