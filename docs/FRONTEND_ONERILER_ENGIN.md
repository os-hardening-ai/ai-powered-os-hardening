# Frontend Önerileri (Engin) — #4 inline atıf + #6 feedback

> Bu iki iyileştirme FRONTEND (Engin'in alanı). Backend tarafı HAZIR — ek API gerekmez.
> (Best-practice araştırması: izlenebilir atıf + güven rozeti güveni artırır; feedback sürekli eval sinyali.)

## #4 — Inline atıf [n] + grounding rozeti

**Veri zaten response'ta:** `rag_sources: RagSource[]` (id/score/source/section) + `verification_confidence: float|null`.

**Yapılacak (`src/components/chat/MessageBubble.tsx`):**
1. **Grounding rozeti:** asistan yanıtının üstüne, `verification_confidence` varsa belirgin bir
   rozet: ör. `grounded %{Math.round(conf*100)}` (≥0.8 yeşil, 0.5-0.8 sarı, <0.5 kırmızı/uyarı).
   (`EvidencePanel` zaten kaynakları listeliyor; bu rozet özet güven sinyali.)
2. **Inline atıf [n]:** yanıt metnindeki `[1]`, `[2]` işaretlerini `rag_sources[n-1]`'e tıklanır
   yap (hover'da source/section göster, tıkla → EvidencePanel'de ilgili kaynağı vurgula).
   - Üretim prompt'u zaten atıf üretiyor (ClaimVerifier `[n]` görüyor); frontend bunları link'le.

## #6 — Kullanıcı feedback (👍/👎)

**Yapılacak (`MessageBubble.tsx` asistan yanıtı altına):**
- Küçük 👍/👎 butonları (lucide `ThumbsUp`/`ThumbsDown`).
- Tıklayınca `localStorage`'a kayıt: `{ts, rating, answer.slice(0,200), question}` listesine ekle
  (anahtar `hardening_feedback`). Görsel onay ("teşekkürler"). Backend endpoint GEREKMEZ (client-side log).
- İstenirse ileride `/api/feedback` endpoint + eval sinyali (sürekli değerlendirme) — şimdilik client-only yeter.

**Not:** İkisi de saf frontend, backend değişikliği yok. Tahmini 1-2 saatlik iş. Hazır referans
implementasyon (taslak) mevcuttu; istersen iletebilirim.
