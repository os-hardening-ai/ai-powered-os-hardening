# steps/output_judge.py
from __future__ import annotations

"""
Output Judge / Self-Check
-------------------------
Bu adım, draft_answer çıktısını küçük bir LLM modeliyle değerlendirerek:

- Güvenlik açısından sakıncalı mı?
- Halüsinasyon riski yüksek mi?
- Yeniden yazılması gerekiyor mu?
- Hangi problemler tespit edildi?

sorularına cevap verir.

Girdi (RequestContext içinden):
- user_question
- draft_answer
- intent, target_area
- zt_principles, standards

Çıktı:
- ctx.judge_result (JudgeResult modeli)
"""

import json
from typing import Callable, TypedDict, List

from context import RequestContext, JudgeResult


LLMCallable = Callable[[str], str]


class JudgeRawResult(TypedDict, total=False):
    """
    LLM'den gelen ham JSON'un beklenen alanları.
    total=False -> bazı alanlar eksik gelebilir, biz default vereceğiz.
    """
    safety: str
    hallucination_risk: float
    needs_rewrite: bool
    issues: list[str]


def _build_judge_prompt(ctx: RequestContext) -> str:
    """
    LLM'e gönderilecek judge/self-check prompt'unu üretir.
    """
    user_question = ctx.user_question
    draft_answer = ctx.draft_answer or ""
    intent = ctx.intent or "generic_qna"
    target_area = ctx.target_area or "general"

    zt_list = ctx.zt_principles or []
    std_list = ctx.standards or []

    zt_str = ", ".join(zt_list) if zt_list else "belirtilmedi"
    std_str = ", ".join(std_list) if std_list else "belirtilmedi"

    return f"""
Aşağıda bir siber güvenlik asistanı tarafından üretilmiş taslak bir cevap var.
Senin görevin bu cevabı KONTROL ETMEK (judge / self-check) ve riskleri tespit etmek.

Kullanıcı mesajı:
\"\"\"{user_question}\"\"\"


Taslak cevap:
\"\"\"{draft_answer}\"\"\"


Bağlam:
- Intent: {intent}
- Hedef alan (target_area): {target_area}
- Zero Trust prensipleri: {zt_str}
- Standart referansları: {std_str}

Değerlendirme başlıkları:

1) Güvenlik / etik durum (safety):
   - "safe"          : Savunma odaklı, saldırı/istismar yönlendirmiyor, uygun.
   - "minor_issues"  : Genel olarak savunma odaklı ama ifade/odak sorunları var, iyileştirilmeli.
   - "unsafe"        : Saldırı, exploit, yetkisiz erişim, kötüye kullanım riski içeriyor
                       veya teknik olarak çok ciddi şekilde yanlış.

2) Halüsinasyon riski (hallucination_risk):
   - 0.0 ile 1.0 arasında bir float.
   - 0.0: risk yok / çok düşük
   - 1.0: cevap büyük oranda uydurma / güvensiz

3) Yeniden yazma ihtiyacı (needs_rewrite):
   - true  : Cevap mutlaka yeniden yazılmalı (örneğin "unsafe" veya ciddi teknik hata).
   - false : Küçük iyileştirmeler dışında değişmesine gerek yok.

4) Tespit edilen problemler (issues):
   - Bir string listesi.
   - Örnekler:
       - "Saldırı adımlarını gereğinden fazla detaylandırıyor."
       - "Zero Trust prensiplerine çok az değinilmiş."
       - "Standart referansları zayıf veya muğlak."
       - "Teknik açıklama eksik veya yanıltıcı."


ÇIKTI FORMATIN:

Sadece GEÇERLİ bir JSON döndür.
Ek açıklama, yorum, markdown ekleme.

Format:
{{
  "safety": "safe" | "minor_issues" | "unsafe",
  "hallucination_risk": 0.25,
  "needs_rewrite": true,
  "issues": [
    "Zero Trust prensiplerine yeterince atıf yapılmamış.",
    "Bazı teknik ifadeler muğlak."
  ]
}}
""".strip()


def _parse_judge_response(raw: str) -> JudgeRawResult:
    """
    LLM'den gelen ham string'i JSON'a parse eder.

    Hata durumunda defansif bir default değerlendirme döner:
      safety = "minor_issues"
      hallucination_risk = 0.5
      needs_rewrite = False
      issues = ["Judge LLM yanıtı parse edilemedi, varsayılan değerlendirme kullanıldı."]
    """
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("LLM response is not a JSON object")

        safety = str(data.get("safety", "minor_issues"))
        hallucination_risk_raw = data.get("hallucination_risk", 0.5)
        needs_rewrite_raw = data.get("needs_rewrite", False)
        issues_raw = data.get("issues", [])

        if not isinstance(issues_raw, list):
            issues_raw = []

        issues: List[str] = [
            str(item).strip()
            for item in issues_raw
            if str(item).strip()
        ]

        try:
            hallucination_risk = float(hallucination_risk_raw)
        except (TypeError, ValueError):
            hallucination_risk = 0.5

        # 0.0–1.0 aralığına clamp et
        if hallucination_risk < 0.0:
            hallucination_risk = 0.0
        if hallucination_risk > 1.0:
            hallucination_risk = 1.0

        needs_rewrite = bool(needs_rewrite_raw)

        return JudgeRawResult(
            safety=safety,
            hallucination_risk=hallucination_risk,
            needs_rewrite=needs_rewrite,
            issues=issues,
        )

    except Exception:
        return JudgeRawResult(
            safety="minor_issues",
            hallucination_risk=0.5,
            needs_rewrite=False,
            issues=[
                "Judge LLM yanıtı parse edilemedi, varsayılan değerlendirme kullanıldı."
            ],
        )


def run_output_judge(llm: LLMCallable, ctx: RequestContext) -> RequestContext:
    """
    Output judge / self-check adımı.

    1. user_question, draft_answer ve güvenlik bağlamına göre prompt oluşturur.
    2. Küçük LLM modelini (llm) çağırarak taslak cevabı değerlendirir.
    3. Dönen JSON'u parse eder; parse hatasında anlamlı default değerlendirme kullanır.
    4. Sonuçları RequestContext.judge_result içine yazar.

    Bu adım:
      - Final cevabın güvenlik/etik standartlara uygunluğunu artırmak,
      - Gerekirse correction adımına sinyal göndermek için kullanılır.
    """
    # draft_answer yoksa yine de minimal bir değerlendirme üretelim
    if not ctx.draft_answer:
        # Çok erken çağrıldıysa veya önceki step hata verdiyse
        judge = JudgeResult(
            safety="minor_issues",
            hallucination_risk=0.7,
            needs_rewrite=True,
            issues=[
                "draft_answer boş veya üretilmemiş görünüyor; önce cevap üretici adımının çalışması gerekir."
            ],
        )
        ctx.judge_result = judge
        return ctx

    prompt = _build_judge_prompt(ctx)
    try:
        raw_response = llm(prompt)
    except Exception:
        # LLM tamamıyla hata verirse de default değerlendirme kullanalım
        judge = JudgeResult(
            safety="minor_issues",
            hallucination_risk=0.5,
            needs_rewrite=False,
            issues=[
                "Judge LLM çağrısında hata oluştu, varsayılan değerlendirme kullanıldı."
            ],
        )
        ctx.judge_result = judge
        return ctx

    parsed = _parse_judge_response(raw_response)

    # Güvenli safety değerleri seti
    valid_safety_values = ("safe", "minor_issues", "unsafe")
    safety_val = parsed.get("safety", "minor_issues")
    if safety_val not in valid_safety_values:
        safety_val = "minor_issues"

    judge_result = JudgeResult(
        safety=safety_val,  # type: ignore[arg-type]
        hallucination_risk=parsed.get("hallucination_risk", 0.5),
        needs_rewrite=bool(parsed.get("needs_rewrite", False)),
        issues=parsed.get("issues", []),
    )
    ctx.judge_result = judge_result

    return ctx
