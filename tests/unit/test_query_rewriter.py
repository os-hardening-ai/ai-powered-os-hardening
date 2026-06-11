"""
Unit tests for rag.query.query_rewriter — follow-up → standalone yeniden yazma.

ODAK: yeni tetik mantığı (zamir + önceki asistan '?' + kısa mesaj). Bu, info
teklifi "hangi OS?" sonrası gelen bare cevabın ("ubuntu") KAPSAM DIŞI'na düşmesi
bug'ını düzeltir. `needs_rewrite` saf mantık (LLM'siz); `rewrite` sahte LLM ile.
"""

from __future__ import annotations

from rag.query.query_rewriter import (
    needs_rewrite,
    _last_assistant_content,
    QueryRewriter,
)


def _hist(*pairs):
    """[(role, content), ...] → [{'role':..,'content':..}] (kronolojik, en yeni sonda)."""
    return [{"role": r, "content": c} for r, c in pairs]


class TestLastAssistant:
    def test_finds_most_recent_assistant(self):
        h = _hist(("user", "a"), ("assistant", "b"), ("user", "c"))
        assert _last_assistant_content(h) == "b"

    def test_empty(self):
        assert _last_assistant_content([]) == ""
        assert _last_assistant_content(None) == ""


class TestNeedsRewrite:
    def test_no_history_never(self):
        assert needs_rewrite("linux ubuntu", []) is False
        assert needs_rewrite("linux ubuntu", None) is False

    def test_coreference_triggers(self):
        h = _hist(("user", "ssh sıkılaştır"), ("assistant", "tamam"))
        assert needs_rewrite("bunu nasıl geri alırım acaba ben", h) is True

    def test_prev_assistant_question_triggers(self):
        # REGRESYON: asistan "hangi OS?" sordu → kullanıcının (uzun) cevabı follow-up'tır.
        h = _hist(
            ("user", "zero trust nedir"),
            ("assistant", "Zero trust bir modeldir. ... hangi işletim sistemi için?"),
        )
        # 7 kelime (≤4 değil) + zamir yok → yalnız 'önceki ? ' sinyali tetiklemeli
        assert needs_rewrite("benim icin ubuntu 24.04 sunucu olsun lutfen", h) is True

    def test_short_message_triggers(self):
        # REGRESYON: bare cevap "linux ubuntu" (≤4 kelime) → follow-up say.
        h = _hist(("user", "zero trust nedir"), ("assistant", "Zero trust bir modeldir."))
        assert needs_rewrite("linux ubuntu", h) is True

    def test_long_standalone_no_trigger(self):
        # Geçmiş var AMA: zamir yok + önceki asistan '?'le bitmedi + mesaj uzun → standalone.
        h = _hist(("user", "zero trust nedir"), ("assistant", "Zero trust bir guvenlik modelidir."))
        assert needs_rewrite("ubuntu firewall nasil yapilandirilir detayli sekilde anlat", h) is False


class TestRewrite:
    def test_merges_bare_os_answer(self):
        # "hangi OS?" sonrası "linux ubuntu" → geçmişle birleşip standalone olur.
        h = _hist(
            ("user", "zero trust nedir?"),
            ("assistant", "Zero trust... hangi işletim sistemi için?"),
        )
        fake = lambda _p: "Zero trust'i linux ubuntu icin adim adim komutlarla acikla"
        out = QueryRewriter(llm_fn=fake).rewrite("linux ubuntu", h)
        assert "ubuntu" in out.lower() and out != "linux ubuntu"

    def test_keeps_standalone_without_calling_llm(self):
        # Tetik yok (uzun + zamir yok + önceki '.' ) → LLM ÇAĞRILMAZ, orijinal korunur.
        h = _hist(("user", "zero trust nedir?"), ("assistant", "Zero trust bir modeldir."))
        def boom(_p):
            raise AssertionError("LLM çağrılmamalıydı (standalone)")
        out = QueryRewriter(llm_fn=boom).rewrite("firewall nasil yapilandirilir detayli anlat bana", h)
        assert out == "firewall nasil yapilandirilir detayli anlat bana"

    def test_llm_unchanged_returns_original(self):
        # Tetik (kısa) ateşlense de LLM "standalone" deyip aynı döndürürse → orijinal.
        h = _hist(("user", "x"), ("assistant", "y"))
        out = QueryRewriter(llm_fn=lambda _p: "firewall nedir").rewrite("firewall nedir", h)
        assert out == "firewall nedir"

    def test_llm_failure_returns_original(self):
        h = _hist(("user", "x"), ("assistant", "y?"))
        def boom(_p):
            raise RuntimeError("provider down")
        assert QueryRewriter(llm_fn=boom).rewrite("linux ubuntu", h) == "linux ubuntu"
