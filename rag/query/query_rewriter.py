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


def needs_rewrite(query: str, history: Optional[List[dict]] = None) -> bool:
    """
    Returns True if query likely references prior conversation context.
    History presence is required for additive markers (also/too/ayrıca).
    """
    if not _COREF_RE.search(query):
        return False
    # "also/too/ayrıca" alone don't need rewriting without history
    if history is None or len(history) == 0:
        return False
    return True


class QueryRewriter:
    """
    Follow-up sorguları bağımsız sorgulara dönüştürür.

    Örnek:
        History : "Ubuntu SSH nasıl sıkılaştırılır?"
        Follow-up: "bunu undo nasıl yaparım?"
        Rewritten: "Ubuntu SSH sıkılaştırma ayarları nasıl geri alınır?"

    Strateji:
        1. Coreference işaretlerini kontrol et (regex, <1ms).
        2. İşaret varsa + history mevcutsa LLM ile yeniden yaz.
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
            "Given the conversation history and a follow-up question that uses "
            "pronouns or references ('bunu', 'onu', 'this', 'that', 'undo', etc.), "
            "rewrite the follow-up as a COMPLETE, SELF-CONTAINED question with NO "
            "references to prior context.\n"
            "Rules:\n"
            "  - Keep the same language as the follow-up question (Turkish or English).\n"
            "  - Preserve OS/role specifics mentioned in history if relevant.\n"
            "  - Return ONLY the rewritten question — no explanation, no quotes.\n\n"
            f"CONVERSATION HISTORY:\n{history_text}\n\n"
            f"FOLLOW-UP: {query}\n\n"
            "REWRITTEN QUESTION:"
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
