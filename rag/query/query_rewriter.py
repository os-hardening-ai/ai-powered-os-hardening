from __future__ import annotations

import logging
import re
from typing import Callable, List, Optional

_logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]

# Türkçe + İngilizce coreference işaretleri
_COREF_PATTERNS = [
    r"\b(bunu|buna|bunun|bunda|bunları|bu kural|bu komut|bu adım|bu ayar)\b",
    r"\b(onu|ona|onun|onda|onları|o kural|o komut|o adım)\b",
    r"\b(yukarıdaki|aşağıdaki|bahsettiğin|söylediğin|belirttiğin)\b",
    r"\b(undo|geri al|iptal et|kaldır|tersine çevir|revert)\b",
    r"\b(it|this|that|the above|the previous|the last|the mentioned)\b",
    r"\b(also|as well|too|additionally|furthermore)\b",  # additive follow-ups
]

_COREF_RE = re.compile("|".join(_COREF_PATTERNS), re.IGNORECASE)


def _last_assistant_content(history: Optional[List[dict]]) -> str:
    """Geçmişteki EN SON asistan mesajının içeriği (kronolojik liste; en yeni sonda)."""
    if not history:
        return ""
    for turn in reversed(history):
        if turn.get("role") == "assistant":
            return turn.get("content", "") or ""
    return ""


def needs_rewrite(query: str, history: Optional[List[dict]] = None) -> bool:
    """Sorgunun önceki bağlama dayanıp dayanmadığını (follow-up mu) belirler.

    Geçmiş YOKSA asla rewrite gerekmez (ilk mesaj). Geçmiş varsa, şu üç sinyalden
    biri bile follow-up'ı işaret eder → rewrite (LLM bağlamı katsın, standalone ise
    PROMPT zaten değiştirmeden döndürür):
      1. Açık coreference işareti (bunu/onu/it/also...).
      2. Önceki ASİSTAN turu bir SORU sordu ('?' ile bitti) → bu mesaj muhtemelen
         o sorunun CEVABI (ör. asistan 'hangi OS?' dedi, kullanıcı 'ubuntu' yazdı).
      3. Çok kısa mesaj (≤4 kelime) → tek başına bir soru olmaktan çok bir cevap/
         follow-up olma olasılığı yüksek (ör. 'linux ubuntu').
    (2) ve (3) eski 'yalnız zamir' kapısının kaçırdığı bare-cevap durumunu yakalar →
    info teklifi 'hangi OS?' sonrası 'ubuntu' artık KAPSAM DIŞI'na düşmez.
    """
    if not history:
        return False
    q = (query or "").strip()
    if not q:
        return False
    # 1) Açık coreference
    if _COREF_RE.search(q):
        return True
    # 2) Önceki asistan SORU sorduysa → bu cevap
    last_asst = _last_assistant_content(history).rstrip()
    if last_asst.endswith("?"):
        return True
    # 3) Çok kısa mesaj → muhtemelen bare cevap/follow-up
    if len(q.split()) <= 4:
        return True
    return False


class QueryRewriter:
    """
    Follow-up sorguları bağımsız sorgulara dönüştürür.

    Örnek:
        History : "Ubuntu SSH nasıl sıkılaştırılır?"
        Follow-up: "bunu undo nasıl yaparım?"
        Rewritten: "Ubuntu SSH sıkılaştırma ayarları nasıl geri alınır?"

    Strateji:
        1. Follow-up sinyali var mı? (zamir / önceki asistan '?' ile sordu / kısa mesaj).
        2. Varsa + history mevcutsa LLM ile yeniden yaz; standalone ise PROMPT
           değiştirmeden döndürür (bare OS cevabı → birleştir, tam soru → koru).
        3. LLM başarısız olursa veya sonuç çok kısaysa orijinali döndür.
    """

    def __init__(self, llm_fn: LLMCallable) -> None:
        self._llm = llm_fn

    def rewrite(
        self,
        query: str,
        history: List[dict],
    ) -> str:
        """
        Args:
            query:   Mevcut kullanıcı sorusu.
            history: [{"role": "user"|"assistant", "content": str}, ...]
                     Yeni→Eski sırasıyla; en fazla son 4 mesaj kullanılır.

        Returns:
            Yeniden yazılmış standalone sorgu, ya da değişiklik gerekmediyse
            orijinal sorgu.
        """
        if not needs_rewrite(query, history):
            return query

        # Son 4 mesaj (2 tur) yeterli
        recent = history[-4:]
        history_text = "\n".join(
            f"{t['role'].upper()}: {t['content'][:250]}"
            for t in recent
        )

        prompt = (
            "You are a query rewriter for a security hardening assistant.\n"
            "Look at the conversation history and the user's NEW message, then decide:\n"
            "  - If the new message is a FOLLOW-UP that only makes full sense WITH prior "
            "context — e.g. an ANSWER to a question the assistant just asked (a bare OS "
            "name like 'ubuntu'), a reference ('bunu/onu/it'), or a short reply — then "
            "rewrite it as ONE complete, self-contained question that MERGES the needed "
            "context from history.\n"
            "  - If the new message is ALREADY a complete standalone question, return it "
            "UNCHANGED.\n"
            "Rules:\n"
            "  - Keep the same language as the new message (Turkish or English).\n"
            "  - Preserve OS/role specifics from history if relevant.\n"
            "  - Return ONLY the question — no explanation, no quotes.\n\n"
            f"CONVERSATION HISTORY:\n{history_text}\n\n"
            f"NEW MESSAGE: {query}\n\n"
            "STANDALONE QUESTION:"
        )

        try:
            rewritten = self._llm(prompt).strip().strip('"\'').strip()
            if len(rewritten) > 15 and rewritten.lower() != query.lower():
                _logger.info(
                    "[QueryRewriter] '%s' → '%s'",
                    query[:60],
                    rewritten[:60],
                )
                return rewritten
        except Exception as exc:
            _logger.warning("[QueryRewriter] LLM rewrite failed: %s", exc)

        return query
