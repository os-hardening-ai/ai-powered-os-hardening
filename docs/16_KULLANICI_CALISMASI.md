# 16 — Kullanıcı Çalışması Protokolü (İP-12 / H2 / H4)

**Amaç:** Öneri formundaki üç maddeyi **tek** küçük kullanıcı çalışmasıyla kapatmak:

| Madde | İddia | Ölçüm | Eşik/Yön |
|-------|-------|-------|----------|
| **İP-12** | Kullanıcı memnuniyeti | Likert (1-5) ≥4 yanıt oranı | **>%70** |
| **H2** | Sistem karar süresini kısaltır | Araçla vs araçsız ortalama süre | **azalma (>0)** |
| **H4** | Öneriler kabul görür | accept/modify/reject ağırlıklı oran | yüksek |

> **Neden tek çalışma?** Üçü de aynı oturumda, aynı katılımcıdan toplanabilir →
> verimli ve tutarlı. Bu çalışma **gerçek kullanıcı** gerektirir (kodla uydurulamaz);
> enstrüman (form + skorlama) hazırdır, ekip pilotu koşar.

---

## Katılımcılar

- **Hedef:** n = 5-10 (ekip + danışman + birkaç sınıf arkadaşı / sistem yöneticisi adayı).
- **Rol çeşitliliği:** sysadmin / developer / security / öğrenci — `role` alanına yazılır.
- n < 5 ise sonuç **gösterge** (pilot) niteliğindedir; skorlama bunu otomatik işaretler.
- **Onam:** Katılımcıya çalışmanın amacı + verinin anonim (yalnızca `P1`, `P2`… kimliği)
  toplandığı sözlü olarak belirtilir.

## Görevler (her katılımcı 2-3 senaryo)

Gerçekçi OS sıkılaştırma senaryoları, örn:
1. **SSH sıkılaştırma** (root login, MaxAuthTries, idle timeout)
2. **Parola politikası** (min uzunluk, max gün)
3. **Firewall / ağ kuralları** (default-deny, yalnızca gerekli portlar)

## Prosedür (her görev için)

1. **Baseline (araçsız):** Katılımcı görevi **yalnızca manuel** (CIS dokümanı / arama motoru)
   ile çözer. Karara varma süresini ölç → `decision_time_baseline_s`.
2. **Araçla:** Aynı/eşdeğer görevi **RAG karar-destek aracıyla** çözer. Süreyi ölç →
   `decision_time_with_tool_s`. *(Sıra etkisini azaltmak için katılımcıların yarısında
   önce-araç / yarısında önce-baseline uygulanabilir.)*
3. **Öneri kararı (H4):** Aracın verdiği her öneri için katılımcı işaretler:
   `accept` (olduğu gibi uygula) · `modify` (uyarlayarak uygula) · `reject` (kullanma).
4. **Anket (İP-12):** Oturum sonunda 5 Likert sorusu (1=kesinlikle katılmıyorum … 5=kesinlikle katılıyorum):
   - `usefulness` — Araç görevi çözmemde işe yaradı.
   - `trust` — Önerilere güvendim (kaynak/standart gösterimi yeterliydi).
   - `clarity` — Çıktılar anlaşılırdı.
   - `would_use_again` — Tekrar kullanırdım.
   - `overall_satisfaction` — Genel memnuniyetim yüksek.

## Veri toplama

1. `evaluation/survey_template.json` dosyasını `evaluation/results/survey_responses.json`
   olarak kopyalayın.
2. Şablondaki `example: true` satırlarını **silin**; her katılımcı için bir kayıt doldurun.
3. Likert 1-5; süreler **saniye**; `verdict` ∈ {accept, modify, reject}.

## Skorlama (deterministik, otomatik)

```bash
python -m evaluation.survey_eval evaluation/results/survey_responses.json
```

Üretir: `evaluation/results/survey_report.md` + `survey_results.json`. Hesaplama:

- **İP-12 memnuniyet** = tüm Likert yanıtları içinde ≥4 olanların oranı (eşik 0.70).
- **H2 azalma** = (ort_araçsız − ort_araçla) / ort_araçsız.
- **H4 kabul** = ağırlıklı (accept=1.0, modify=0.5, reject=0.0) ortalama.

Skorlama mantığı saf fonksiyonlardır ve `tests/unit/test_survey_eval.py` ile test edilir
(insandan gelen veri hariç her şey doğrulanır).

## Dürüstlük / sınırlar

- Küçük örneklem (n<5) **istatistiksel genelleme yapmaz**; rapor bunu açıkça işaretler.
  Bitirme savunması için n=5-10 **gösterge kanıt** olarak yeterli, ideal n daha büyüktür.
- Baseline ve araçla görevlerin **eşdeğer zorlukta** olmasına dikkat edin (öğrenme etkisini
  azaltmak için görev sırasını dönüşümlü uygulayın).
