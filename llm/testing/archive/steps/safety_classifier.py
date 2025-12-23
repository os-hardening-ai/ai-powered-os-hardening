# steps/safety_classifier.py

from __future__ import annotations

import json
from typing import Callable, TypedDict, Optional

from context import RequestContext, SafetyResult, SafetyCategory


LLMCallable = Callable[[str], str]


class SafetyRawResult(TypedDict, total=False):
    category: str
    reason: Optional[str]


def _build_safety_prompt(ctx: RequestContext) -> str:
    return f"""
Aşağıdaki kullanıcı mesajını güvenlik açısından sınıflandır.

Mesaj:
\"\"\"{ctx.user_question}\"\"\"


Sınıflandırma kuralları:

- "defensive_security":
    - Kullanıcı savunma amaçlı, güvenlik iyileştirmesi, hardening, log analizi,
      saldırı tespiti, güvenlik bilgilendirmesi vb. istiyorsa.

- "offensive_illegal":
    - Kullanıcı saldırı, exploit yazma, zafiyet istismarı, sisteme izinsiz giriş,
      veri sızdırma vb. amaçlı yardım istiyorsa.
    - Genel veya teorik açıklama değil, pratik saldırı adımları istiyorsa.

- "generic_it":
    - Genel IT, sistem veya ağ soruları, doğrudan siber saldırı veya savunma
      kapsamında olmayan teknik sorular.

- "ambiguous":
    - Mesajın niyeti net anlaşılmıyorsa, gri alandaysa.


ÇIKTI FORMATIN:

Sadece geçerli bir JSON döndür.
Ek açıklama, yorum, markdown ekleme.

ÖRNEK:
{
  "category": "defensive_security",
  "reason": "Kullanıcı SSH güvenliğini artırmak istiyor."
}
"""  # noqa: E501


def _parse_safety_response(raw: str) -> SafetyRawResult:
    try:
        # Markdown code block varsa temizle
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # ```json ... ``` formatını temizle
            lines = cleaned.split("\n")
            if len(lines) > 2:
                cleaned = "\n".join(lines[1:-1])

        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("LLM response is not a JSON object")

        category = str(data.get("category", "generic_it"))
        reason = data.get("reason")

        return SafetyRawResult(
            category=category,
            reason=reason,
        )
    except json.JSONDecodeError as e:
        # JSON parse hatası - debug için log
        import warnings
        warnings.warn(f"Safety classifier JSON parse error: {e}\nRaw: {raw[:100]}...")
        return SafetyRawResult(
            category="generic_it",
            reason=None,
        )
    except Exception as e:
        # Diğer hatalar
        import warnings
        warnings.warn(f"Safety classifier unexpected error: {e}")
        return SafetyRawResult(
            category="generic_it",
            reason=None,
        )


def run_safety_classifier(llm: LLMCallable, ctx: RequestContext) -> RequestContext:
    """
    Kullanıcı isteğini güvenlik kategorisine göre sınıflandırır.

    - offensive_illegal ise:
        - ctx.safety.category = "offensive_illegal"
        - ctx.final_answer içinde kibar bir red ve genel güvenlik tavsiyesi bulunur.
        - Pipeline bu noktadan sonra normal security akışına devam etmemelidir.

    - Diğer durumlarda sadece ctx.safety doldurulur ve sonraki adımlara geçilir.
    """
    prompt = _build_safety_prompt(ctx)
    raw_response = llm(prompt)

    parsed = _parse_safety_response(raw_response)

    valid_categories: tuple[SafetyCategory, ...] = (
        "defensive_security",
        "offensive_illegal",
        "generic_it",
        "ambiguous",
    )

    category_str = parsed.get("category", "generic_it")
    if category_str not in valid_categories:
        category_str = "generic_it"

    safety_result = SafetyResult(
        category=category_str,  # type: ignore[arg-type]
        reason=parsed.get("reason"),
    )
    ctx.safety = safety_result

    if safety_result.category == "offensive_illegal":
        refusal_message = """
Bu talep güvenlik açısından uygun değildir.

Ben savunma amaçlı, sistemlerin daha güvenli ve dayanıklı hale getirilmesine
yardımcı olmak için tasarlandım. Saldırı, yetkisiz erişim veya kanuna aykırı
faaliyetlerle ilgili teknik destek veremem.

İstersen sana:
- Güvenlik farkındalığı,
- Savunma teknikleri,
- Zero Trust yaklaşımı,
- Sistemlerini nasıl daha iyi koruyabileceğin

konularında yardımcı olabilirim.
""".strip()
        ctx.final_answer = refusal_message

    return ctx
