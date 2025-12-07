# steps/correction.py
from __future__ import annotations

"""
Correction Step
---------------
Bu adım, output_judge tarafından "needs_rewrite = true" olarak işaretlenen
cevapları büyük LLM modeli ile daha güvenli, tutarlı ve Zero Trust odaklı
hale getirmek için kullanılır.

Girdi (RequestContext içinden):
- user_question
- draft_answer
- judge_result (safety, issues, needs_rewrite, hallucination_risk)
- intent, target_area
- zt_principles, standards

Çıktı:
- ctx.final_answer (düzeltilmiş, yayınlanmaya hazır cevap)
"""

from typing import Callable, List

from context import RequestContext, JudgeResult


LLMCallable = Callable[[str], str]


def _format_issues(issues: List[str]) -> str:
    """
    Judge tarafından tespit edilen sorunları prompt içinde
    kullanılabilecek okunur bir formata çevirir.
    """
    if not issues:
        return "- (Belirtilmiş spesifik bir sorun yok.)"

    lines = []
    for i, issue in enumerate(issues, start=1):
        lines.append(f"{i}. {issue}")
    return "\n".join(lines)


def _build_correction_prompt(ctx: RequestContext) -> str:
    """
    Büyük LLM'e gönderilecek correction prompt'unu üretir.
    Judge çıktısındaki sorunları ve güvenlik durumunu rehber olarak kullanır.
    """
    user_question = ctx.user_question
    draft_answer = ctx.draft_answer or ""
    judge: JudgeResult = ctx.judge_result  # type: ignore[assignment]

    intent = ctx.intent or "generic_qna"
    target_area = ctx.target_area or "general"

    zt_list = ctx.zt_principles or []
    std_list = ctx.standards or []

    zt_str = ", ".join(zt_list) if zt_list else "belirtilmedi"
    std_str = ", ".join(std_list) if std_list else "belirtilmedi"
    issues_str = _format_issues(judge.issues)

    return f"""
Aşağıda bir siber güvenlik asistanı tarafından üretilmiş taslak bir cevap
ve bu cevabın judge/self-check değerlendirmesi var.

Senin görevin:
- Bu taslak cevabı, judge değerlendirmesindeki sorunları gidererek
  daha güvenli, tutarlı ve Zero Trust odaklı bir şekilde yeniden yazmak.


KULLANICI MESAJI:
\"\"\"{user_question}\"\"\"


MEVCUT TASLAK CEVAP:
\"\"\"{draft_answer}\"\"\"


JUDGE DEĞERLENDİRMESİ:
- safety: {judge.safety}
- hallucination_risk: {judge.hallucination_risk}
- needs_rewrite: {judge.needs_rewrite}

Tespit edilen sorunlar:
{issues_str}


BAĞLAM:
- Intent: {intent}
- Hedef alan (target_area): {target_area}
- Zero Trust prensipleri: {zt_str}
- Standart referansları: {std_str}


YENİ CEVABI YAZARKEN KURALLAR:

1) Güvenlik ve etik:
   - Saldırı, exploit, yetkisiz erişim veya yasa dışı faaliyetlere ilişkin
     adım adım rehber verme.
   - Savunma, risk azaltma, izleme, alarm ve hardening odaklı ol.
   - Zero Trust prensiplerini (least_privilege, continuous_verification,
     assume_breach vb.) uygun yerlerde vurgula.

2) Teknik doğruluk:
   - Mevcut taslaktaki teknik hataları veya muğlaklıkları gider.
   - Emin olmadığın çok spesifik detaylara mutlak gerçek gibi davranma;
     gerekirse "genel olarak ..." gibi ifadeler kullan.

3) Standartlara atıf:
   - CIS, NIST, ISO 27001 gibi referansları çok iddialı detaylarla uydurma.
   - Genel seviye atıflar kullan (örn: "CIS benchmark'lar genelde ... önerir").

4) Yapı:
   - Türkçe cevap ver.
   - Kısa bir özet paragrafı ile başla (kullanıcının ne istediğini ve cevabın
     ana yönünü göster).
   - Ardından mantıklı başlıklar/alt başlıklarla (Örn: "Önerilen Adımlar",
     "Dikkat Edilmesi Gerekenler") devam et.
   - Çok uzun paragraflar yerine, okunabilir bloklar tercih et.

5) Judge sorunlarını çöz:
   - issues listesinde belirtilen her sorunu ele al ve yeni cevapta düzelt.


ÇIKTI:
- Sadece yeni, düzeltilmiş cevabı yaz.
- Ek JSON, markdown başlık seviyesi, meta yorum veya açıklama ekleme.
- Kullanıcıya gönderilmeye hazır, temiz bir cevap üret.
""".strip()


def run_correction(llm: LLMCallable, ctx: RequestContext) -> RequestContext:
    """
    Correction adımı.

    1. draft_answer ve judge_result bilgileri ile correction prompt'u oluşturur.
    2. Büyük LLM modelini (llm) çağırarak yeni bir cevap üretir.
    3. Yeni cevabı ctx.final_answer içine yazar.
    4. Hata durumunda, en azından draft_answer'ı hafif bir açıklama ile birlikte döndürür.
    """
    # Eğer judge_result yoksa veya needs_rewrite False ise,
    # normalde bu adım çağrılmamalı. Yine de defansif davranalım.
    if not ctx.judge_result:
        # Judge çalışmamışsa, draft_answer'ı doğrudan final_answer yapalım.
        ctx.final_answer = ctx.draft_answer or (
            "Şu anda ayrıntılı bir cevap sağlayamıyorum. "
            "Lütfen sorunuzu biraz daha detaylandırmayı deneyin."
        )
        return ctx

    # Eğer draft_answer yoksa, yapılacak en iyi şey kullanıcıyı bilgilendirmek.
    if not ctx.draft_answer:
        ctx.final_answer = (
            "Önce teknik bir taslak cevap üretilmesi gerekiyor. "
            "Şu anda elimde düzeltebileceğim bir taslak bulunmuyor."
        )
        return ctx

    prompt = _build_correction_prompt(ctx)

    try:
        corrected = llm(prompt).strip()
        if not corrected:
            raise ValueError("Correction LLM'den boş cevap döndü.")

        ctx.final_answer = corrected

    except Exception:
        # Correction adımında hata olursa, draft_answer'ı olduğu gibi döndür
        # ve kullanıcıya ufak bir uyarı notu ekle (çok abartmadan).
        base = ctx.draft_answer or ""
        note = (
            "\n\n(Not: Cevap üzerinde ek doğrulama yapmak üzere tasarlanan "
            "düzeltme adımında bir hata oluştu. Yukarıdaki cevap, ilk taslak "
            "olarak üretilmiş hâlidir; lütfen kritik ortamlarda uygulamadan önce "
            "ek kontrol ve test yapmayı unutma.)"
        )
        ctx.final_answer = (base + note).strip()

    return ctx
