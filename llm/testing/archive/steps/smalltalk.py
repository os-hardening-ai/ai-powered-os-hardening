# steps/smalltalk.py
from __future__ import annotations

"""
Smalltalk handler
-----------------
Selamlama, vedalaşma ve hafif sohbet (teşekkür vb.) intentleri için
ağır güvenlik pipeline'ına girmeden hızlı ve hafif cevap üretir.

Intent tipleri (context.IntentType içinden):
- smalltalk_greeting
- smalltalk_farewell
- smalltalk_other
"""

from typing import Callable, Optional
import random

from context import RequestContext, IntentType


# LLM çağrısını temsil eden basit type alias
LLMCallable = Callable[[str], str]


# ─────────────────────────────────────────────
# 1) Sabit template cevaplar
# ─────────────────────────────────────────────

GREETING_TEMPLATES = [
    "Merhaba, ben Zero Trust odaklı siber güvenlik asistanınım. Nasıl yardımcı olabilirim?",
    "Selam! Güvenlik konularında birlikte çalışmaya hazırım. Sorunu anlatmak ister misin?",
    "Merhaba, hoş geldin. Sistemlerini daha güvenli hale getirmek için buradayım.",
]

FAREWELL_TEMPLATES = [
    "Görüşmek üzere, güvenli kal. Yeni bir sorunda yine buradayım.",
    "Hoşça kal, sistemlerini korumayı unutma. Dilediğin zaman geri gelebilirsin.",
    "İyi günler, Zero Trust bakış açısını aklında tut. Tekrar görüşmek üzere.",
]

OTHER_TEMPLATES = [
    "Rica ederim, her zaman yardımcı olmaya hazırım. Güvenlikle ilgili başka bir sorun varsa sorabilirsin.",
    "Teşekkür ederim, ben de buradayım. Dilersen sistemlerini nasıl daha güvenli hale getireceğimizi konuşabiliriz.",
    "Ne güzel, o zaman sıradaki güvenlik sorunu veya merak ettiğin konuya geçebiliriz.",
]


# ─────────────────────────────────────────────
# 2) Yardımcı fonksiyonlar
# ─────────────────────────────────────────────

def _pick_template(intent: IntentType) -> str:
    """
    Intent türüne göre uygun bir sabit metin template'i seçer.
    Küçük rastgelelik ile cevapların tekdüze olmasını engeller.
    """
    if intent == "smalltalk_greeting":
        return random.choice(GREETING_TEMPLATES)
    if intent == "smalltalk_farewell":
        return random.choice(FAREWELL_TEMPLATES)
    # smalltalk_other dahil her şey buraya düşer
    return random.choice(OTHER_TEMPLATES)


def _build_greeting_prompt() -> str:
    """
    LLM kullanmak istenirse, selamlama için gönderilecek prompt'u üretir.
    """
    return """
Kullanıcıya Türkçe, kısa, samimi ve profesyonel bir selamlama mesajı yaz.

Gereksinimler:
- Zero Trust ve siber güvenlik odaklı olduğunu hissettir.
- 1–2 cümle olsun.
- Örneğin "Merhaba, ben Zero Trust güvenlik asistanın. Nasıl yardımcı olabilirim?" benzeri bir ton kullan.
- Markdown, emoji, liste kullanma. Sadece düz metin.
""".strip()


def _build_farewell_prompt() -> str:
    """
    LLM kullanmak istenirse, vedalaşma için gönderilecek prompt'u üretir.
    """
    return """
Kullanıcıya Türkçe, kısa, samimi ve profesyonel bir vedalaşma mesajı yaz.

Gereksinimler:
- Güvenlik temasını hafifçe vurgulayabilirsin (örneğin "güvenli kal").
- 1–2 cümle olsun.
- Örneğin "Görüşmek üzere, güvenli kal. Bir sorunda yine buradayım." benzeri bir ton kullan.
- Markdown, emoji, liste kullanma. Sadece düz metin.
""".strip()


def _build_other_prompt(user_message: str) -> str:
    """
    LLM kullanmak istenirse, teşekkür / hafif sohbet için gönderilecek prompt'u üretir.
    """
    return f"""
Aşağıdaki kullanıcı mesajına Türkçe, kısa ve samimi bir cevap yaz.

Mesaj:
\"\"\"{user_message}\"\"\"

Gereksinimler:
- Gereksiz teknik detaya girme.
- Dilersen güvenlikle ilgili yardımcı olabileceğini nazikçe belirtebilirsin.
- 1–2 cümle olsun.
- Markdown, emoji, liste kullanma. Sadece düz metin.
""".strip()


# ─────────────────────────────────────────────
# 3) Ana smalltalk handler
# ─────────────────────────────────────────────

def handle_smalltalk(
    ctx: RequestContext,
    llm_small: Optional[LLMCallable] = None,
) -> RequestContext:
    """
    Smalltalk intentlerini (selamlama, vedalaşma, teşekkür vb.) işler.

    Davranış:
      - Eğer llm_small verilmişse:
          - LLM'e küçük, kontrollü prompt göndererek cevap üretmeye çalışır.
          - LLM cevabı boş/uygunsuz ise sabit template'lere geri düşer (fallback).
      - Eğer llm_small verilmemişse:
          - Sadece sabit template listelerinden rastgele bir cevap döner.

    Sonuç:
      - ctx.final_answer alanı doldurulur.
      - ctx aynı instance olarak geri döner.
    """
    # Intent yoksa default olarak smalltalk_other kabul edelim
    intent: IntentType = ctx.intent or "smalltalk_other"  # type: ignore[assignment]

    # LLM kullanılmak istenmiyorsa doğrudan template kullan
    if llm_small is None:
        ctx.final_answer = _pick_template(intent)
        return ctx

    # LLM kullanılacaksa intent'e göre uygun prompt hazırlanır
    if intent == "smalltalk_greeting":
        prompt = _build_greeting_prompt()
    elif intent == "smalltalk_farewell":
        prompt = _build_farewell_prompt()
    else:
        prompt = _build_other_prompt(ctx.user_question)

    # LLM'den cevap almaya çalış
    try:
        raw = llm_small(prompt).strip()
    except Exception:
        # Herhangi bir LLM hatasında template fallback
        ctx.final_answer = _pick_template(intent)
        return ctx

    # LLM cevabı boş veya çok kısa ise fallback kullan
    if not raw or len(raw) < 3:
        ctx.final_answer = _pick_template(intent)
        return ctx

    ctx.final_answer = raw
    return ctx
