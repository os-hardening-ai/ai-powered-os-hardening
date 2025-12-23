# steps/planner.py
from __future__ import annotations

"""
Görev Planlayıcı (Planner)
--------------------------
Intent, target_area, Zero Trust prensipleri ve standart referanslarına göre
cevap üretiminde izlenecek adımları (plan.steps) belirler.

Örnek plan adımları:
- Basit kavramsal açıklama
- Risklerin listelenmesi
- Somut öneri ve kontroller
- İzleme / loglama / iyileştirme adımları
"""

import json
from typing import Callable, TypedDict, List

from context import RequestContext, Plan, PlanStep


LLMCallable = Callable[[str], str]


class PlanRawStep(TypedDict, total=False):
    id: int
    goal: str
    detail: str


class PlanRawResult(TypedDict, total=False):
    steps: list[PlanRawStep]


def _build_planner_prompt(ctx: RequestContext) -> str:
    """
    LLM'e gönderilecek görev planlayıcı prompt'unu üretir.
    """
    intent = ctx.intent or "generic_qna"
    target_area = ctx.target_area or "general"
    os_name = ctx.os or "bilinmiyor"

    zt_list = ctx.zt_principles or []
    std_list = ctx.standards or []

    zt_str = ", ".join(zt_list) if zt_list else "belirtilmedi"
    std_str = ", ".join(std_list) if std_list else "belirtilmedi"

    return f"""
Aşağıdaki güvenlik isteği için, mantıklı bir cevap üretme planı oluştur.

Kullanıcı mesajı:
\"\"\"{ctx.user_question}\"\"\"


Bağlam:
- Intent: {intent}
- Hedef alan (target_area): {target_area}
- İşletim sistemi / platform: {os_name}
- Güvenlik seviyesi: {ctx.security_level}
- Zero Trust olgunluk: {ctx.zt_maturity}
- Zero Trust prensipleri: {zt_str}
- Standart referansları: {std_str}


Amaç:
- Cevap üretirken izlenecek adımları belirlemek.
- Bu adımlar, daha sonra başka bir model tarafından takip edilerek
  detaylı ve güvenlik odaklı bir cevap üretilmesini sağlayacak.

Örnek step türleri (sadece örnek, ihtiyaca göre uyarlayabilirsin):
- "Sorunun netleştirilmesi ve kapsam tanımı"
- "İlgili risklerin ve saldırı yüzeylerinin listelenmesi"
- "Zero Trust prensiplerine göre önerilerin sıralanması"
- "Somut komut / konfigürasyon iskeletlerinin verilmesi"
- "Loglama, izleme ve sürekli iyileştirme önerileri"


ÇIKTI FORMATIN:

Sadece geçerli bir JSON döndür.
Ek açıklama, yorum, markdown ekleme.

Format:
{{
  "steps": [
    {{
      "id": 1,
      "goal": "Kullanıcının isteğini özetle ve güvenlik kapsamını netleştir",
      "detail": "Örneğin hangi servis/port/uygulama için geçerli olduğunu belirt."
    }},
    {{
      "id": 2,
      "goal": "İlgili Zero Trust prensiplerini uygula",
      "detail": "least_privilege, continuous_verification gibi prensipleri bağlama oturt."
    }}
  ]
}}
""".strip()


def _parse_planner_response(raw: str) -> PlanRawResult:
    """
    LLM'den gelen ham string'i JSON'a parse eder.

    Hata durumunda defansif bir default plan döner.
    """
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("LLM response is not a JSON object")

        steps_raw = data.get("steps", [])
        if not isinstance(steps_raw, list):
            steps_raw = []

        cleaned_steps: List[PlanRawStep] = []
        for idx, item in enumerate(steps_raw, start=1):
            if not isinstance(item, dict):
                continue

            goal = str(item.get("goal", "")).strip()
            detail = str(item.get("detail", "")).strip()

            if not goal:
                continue

            step_id = item.get("id")
            if not isinstance(step_id, int):
                step_id = idx

            cleaned_steps.append(
                PlanRawStep(
                    id=step_id,
                    goal=goal,
                    detail=detail,
                )
            )

        return PlanRawResult(steps=cleaned_steps)

    except Exception:
        # Basit bir fallback plan
        return PlanRawResult(
            steps=[
                PlanRawStep(
                    id=1,
                    goal="Kullanıcının isteğini özetle ve güvenlik kapsamını netleştir",
                    detail="İlgili sistem, servis ve riskleri kısaca çıkar.",
                ),
                PlanRawStep(
                    id=2,
                    goal="Zero Trust prensiplerine göre önerileri sırala",
                    detail="least_privilege, continuous_verification gibi prensipleri bağlama uygula.",
                ),
                PlanRawStep(
                    id=3,
                    goal="Somut adımlar ve öneriler ver",
                    detail="Gerekirse komut veya konfigürasyon iskeleti de ver.",
                ),
            ]
        )


def run_planner(llm: LLMCallable, ctx: RequestContext) -> RequestContext:
    """
    Görev planlayıcı adımı.

    1. Intent, target_area, Zero Trust ve standart bilgileriyle prompt oluşturur.
    2. llm(prompt) ile küçük/orta boy modeli çağırır.
    3. Dönen JSON'u parse eder, hata olursa anlamlı default plan üretir.
    4. Sonuçları RequestContext.plan içine yazar.

    Bu adım, cevap üreticinin (answer_generator) daha tutarlı ve
    adım adım düşünmesini sağlamak için kullanılır.
    """
    prompt = _build_planner_prompt(ctx)
    raw_response = llm(prompt)

    parsed = _parse_planner_response(raw_response)

    steps_models: List[PlanStep] = []
    for raw_step in parsed.get("steps", []):
        step_model = PlanStep(
            id=raw_step.get("id", 0),
            goal=raw_step.get("goal", ""),
            detail=raw_step.get("detail"),
        )
        steps_models.append(step_model)

    ctx.plan = Plan(steps=steps_models)
    return ctx
