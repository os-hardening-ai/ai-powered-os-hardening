# steps/intent_classifier.py
from __future__ import annotations

"""
Intent Classifier
-----------------
Kullanıcı mesajının niyetini (intent) ve hedef alanını (target_area) belirler.

Intent türleri:
- Security: os_hardening, script_or_config, incident_analysis, 
  conceptual_explanation, generic_qna
- Smalltalk: smalltalk_greeting, smalltalk_farewell, smalltalk_other

Target area örnekleri:
- ssh, firewall, rdp, logging, windows_gpo, network_segmentation vb.
"""

import json
from typing import Callable, TypedDict, Optional

from context import RequestContext, IntentType


LLMCallable = Callable[[str], str]


class IntentRawResult(TypedDict, total=False):
    """LLM'den gelen ham JSON'un beklenen alanları."""
    intent: str
    target_area: Optional[str]
    needs_script: bool


def _build_intent_prompt(ctx: RequestContext) -> str:
    """LLM'e gönderilecek intent classification prompt'unu üretir."""
    return f"""
Aşağıdaki kullanıcı mesajının niyetini (intent) ve hedef alanını belirle.

Mesaj:
\"\"\"{ctx.user_question}\"\"\"


Intent kategorileri:

**Security İntentleri:**
- "os_hardening": OS/servis sıkılaştırma (SSH, firewall, RDP hardening...)
- "script_or_config": Script, komut veya config dosyası isteği
- "incident_analysis": Log analizi, olay inceleme, saldırı tespiti
- "conceptual_explanation": Kavramsal güvenlik açıklaması
- "generic_qna": Genel IT/güvenlik sorusu

**Smalltalk İntentleri:**
- "smalltalk_greeting": Selamlama (merhaba, selam, nasılsın)
- "smalltalk_farewell": Vedalaşma (görüşürüz, hoşçakal, güle güle)
- "smalltalk_other": Teşekkür, hafif sohbet, hava durumu vb.


Target Area örnekleri:
- ssh, firewall, rdp, logging, windows_gpo, network_segmentation,
  web_server, database, cloud_security, endpoint, identity_management


ÇIKTI FORMATIN:

Sadece geçerli bir JSON döndür.
Ek açıklama, yorum, markdown ekleme.

ÖRNEK:
{{
  "intent": "os_hardening",
  "target_area": "ssh",
  "needs_script": false
}}

Smalltalk için target_area null olabilir:
{{
  "intent": "smalltalk_greeting",
  "target_area": null,
  "needs_script": false
}}
""".strip()


def _parse_intent_response(raw: str) -> IntentRawResult:
    """
    LLM'den gelen ham string'i JSON'a parse eder.

    Hata durumunda defansif default döner:
      intent = "generic_qna"
      target_area = None
      needs_script = False
    """
    try:
        # Markdown code block varsa temizle
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if len(lines) > 2:
                cleaned = "\n".join(lines[1:-1])

        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("LLM response is not a JSON object")

        intent = str(data.get("intent", "generic_qna")).strip()
        target_area_raw = data.get("target_area")
        needs_script = bool(data.get("needs_script", False))

        # target_area null veya boş string olabilir
        target_area: Optional[str] = None
        if target_area_raw and str(target_area_raw).strip():
            target_area = str(target_area_raw).strip()

        return IntentRawResult(
            intent=intent,
            target_area=target_area,
            needs_script=needs_script,
        )

    except json.JSONDecodeError as e:
        import warnings
        warnings.warn(f"Intent classifier JSON parse error: {e}\nRaw: {raw[:100]}...")
        return IntentRawResult(
            intent="generic_qna",
            target_area=None,
            needs_script=False,
        )
    except Exception as e:
        import warnings
        warnings.warn(f"Intent classifier unexpected error: {e}")
        return IntentRawResult(
            intent="generic_qna",
            target_area=None,
            needs_script=False,
        )


def run_intent_classifier(llm: LLMCallable, ctx: RequestContext) -> RequestContext:
    """
    Intent classifier adımı.

    1. Kullanıcı mesajına göre intent classification prompt'u oluşturur.
    2. Küçük LLM modelini (llm) çağırarak intent ve target_area belirler.
    3. Dönen JSON'u parse eder, hata olursa generic_qna default'u kullanır.
    4. Sonuçları RequestContext içine yazar:
        - ctx.intent
        - ctx.target_area
        - ctx.needs_script

    Bu adım pipeline'ın geri kalanının hangi yolu izleyeceğini belirler:
      - Smalltalk intentleri -> handle_smalltalk()
      - Security intentleri -> tam pipeline (zt_mapper, planner, answer, judge)
    """
    # Eğer safety step offensive_illegal dönmüşse, intent'e gerek yok
    if ctx.safety and ctx.safety.category == "offensive_illegal":
        # Bu durumda zaten final_answer dolmuş, intent'i generic_qna yapalım
        ctx.intent = "generic_qna"
        return ctx

    prompt = _build_intent_prompt(ctx)
    
    try:
        raw_response = llm(prompt)
    except Exception:
        # LLM çağrısı başarısız, default değerlerle devam et
        ctx.intent = "generic_qna"
        ctx.target_area = None
        ctx.needs_script = False
        return ctx

    parsed = _parse_intent_response(raw_response)

    # Intent validasyonu
    valid_intents: tuple[str, ...] = (
        "os_hardening",
        "script_or_config",
        "incident_analysis",
        "conceptual_explanation",
        "generic_qna",
        "smalltalk_greeting",
        "smalltalk_farewell",
        "smalltalk_other",
    )

    intent_str = parsed.get("intent", "generic_qna")
    if intent_str not in valid_intents:
        intent_str = "generic_qna"

    # Type-safe cast - we verified it's in valid_intents
    ctx.intent = intent_str  # type: ignore[assignment]  # Literal type narrowing not supported
    ctx.target_area = parsed.get("target_area")
    ctx.needs_script = parsed.get("needs_script", False)

    return ctx