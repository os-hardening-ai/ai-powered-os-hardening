# prompts/cot_prompts.py
"""
Chain-of-Thought (CoT) Prompting for Single-Shot Analysis

Bu modül tüm pipeline adımlarını tek bir akıllı prompt'ta birleştirir.
6-7 LLM çağrısı yerine 1 çağrı ile aynı kaliteyi sağlar.
"""

from __future__ import annotations

from typing import Optional
import re

from llm.core.context import RequestContext
from .few_shot_examples import FEW_SHOT_EXAMPLES


class CoTSecurityAnalyzer:
    """
    Chain-of-Thought yaklaşımıyla güvenlik analizi.

    6 adımlı reasoning chain:
    1. Güvenlik değerlendirmesi (safety)
    2. Niyet analizi (intent)
    3. Zero Trust prensipleri (zt_mapper)
    4. Risk değerlendirmesi (risk/rollback)
    5. Uygulama planı (planner)
    6. Detaylı kullanıcı cevabı (answer_generator)
    """

    def __init__(self, use_few_shot: bool = True):
        """
        Args:
            use_few_shot: Few-shot examples dahil edilsin mi?
        """
        self.use_few_shot = use_few_shot

    def build_cot_prompt(self, ctx: RequestContext) -> str:
        """
        CoT prompt oluştur.

        Args:
            ctx: Request context (user_question, os, role, vb.)

        Returns:
            Tam CoT prompt string
        """

        # Few-shot examples (optional)
        few_shot_section = ""
        if self.use_few_shot:
            few_shot_section = FEW_SHOT_EXAMPLES + "\n\n"

        # Main prompt
        prompt = f"""{few_shot_section}═══════════════════════════════════════════════════════════════════
🎯 SENİN GÖREVİN: Aşağıdaki kullanıcı sorusunu 6 ADIMDA analiz et
═══════════════════════════════════════════════════════════════════

Sen bir Zero Trust siber güvenlik uzmanısın. Kullanıcının sorusunu
sistematik olarak analiz edip, savunma odaklı, uygulanabilir öneriler sun.

KULLANICI SORUSU:
\"\"\"{ctx.user_question}\"\"\"

BAĞLAM:
- OS: {ctx.os or 'belirtilmemiş'}
- Rol: {ctx.role or 'sysadmin'}
- Security Level: {ctx.security_level}
- ZT Maturity: {ctx.zt_maturity}

─────────────────────────────────────────────────────────────────

📋 GÖREV: Aşağıdaki 6 ADIMI TAM OLARAK takip et ve her adımı düşünerek ilerle.

═══════════════════════════════════════════════════════════════════
ADIM 1: GÜVENLİK DEĞERLENDİRMESİ
═══════════════════════════════════════════════════════════════════

Bu talep güvenlik açısından nasıl sınıflandırılır?

✅ **defensive_security**: Savunma, hardening, monitoring, risk azaltma
⚠️  **ambiguous**: Belirsiz, daha fazla bağlam gerekli
❌ **offensive_illegal**: Saldırı, exploit, yetkisiz erişim, kötüye kullanım

**DÜŞÜNCE SÜRECİN:**
[Soruyu analiz et - hangi amaçla sorulmuş? Savunma mı saldırı mı?]

**SONUÇ:** [defensive_security / ambiguous / offensive_illegal]

─────────────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════════════
ADIM 2: NİYET ANALİZİ
═══════════════════════════════════════════════════════════════════

Kullanıcı tam olarak ne istiyor?

**İntent Kategorileri:**
- os_hardening: Sistem/servis sıkılaştırma
- script_or_config: Otomasyon script'i veya config dosyası
- incident_analysis: Log analizi, olay inceleme
- conceptual_explanation: Kavramsal açıklama, öğrenme

**DÜŞÜNCE SÜRECİN:**
[Sorunun odak noktası ne? Pratik uygulama mı teorik bilgi mi?]

**Intent:** [os_hardening / script_or_config / incident_analysis / conceptual_explanation]
**Hedef Alan:** [ssh / firewall / rdp / network / endpoint / vb.]
**Script Gerekli mi?:** [Evet / Hayır]

─────────────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════════════
ADIM 3: ZERO TRUST PRENSİPLERİ VE STANDARTLAR
═══════════════════════════════════════════════════════════════════

Bu talep hangi Zero Trust prensipleriyle ilişkili?

**Mevcut ZT Prensipleri:**
- least_privilege (en az yetki)
- continuous_verification (sürekli doğrulama)
- assume_breach (ihlal varsayımı)
- micro_segmentation (mikro bölümleme)
- strong_identity (güçlü kimlik doğrulama)
- device_posture (cihaz duruş kontrolü)
- secure_access (güvenli erişim)
- visibility_and_analytics (görünürlük ve analitik)

**DÜŞÜNCE SÜRECİN:**
[Her bir prensibi ele al ve bu soruyla ilişkisini düşün]

**İlgili Prensipler:**
[Liste halinde 2-4 prensip seç ve NEDEN ilgili olduğunu açıkla]

**Standart Referansları:**
[CIS/NIST/ISO referansları - SADECE eminsen ve MADDE NUMARALI olarak ver]
[Örnek: CIS_Ubuntu_22_04:5.2.5, NIST_800-53:AC-17]

─────────────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════════════
ADIM 4: RİSK VE ETKİ DEĞERLENDİRMESİ
═══════════════════════════════════════════════════════════════════

Bu değişikliğin sistem üzerindeki etkisi ve riski nedir?

**Risk Seviyesi:** [low / medium / high / critical]

**Etki Analizi:**
- Sistem kararlılığına etkisi nedir?
- Servis kesintisi olacak mı?
- Geri dönülemez mi, yoksa kolayca rollback yapılabilir mi?
- Test ortamında denenmesi kritik mi?

**Rollback Stratejisi:**
[Pratik, adım adım geri alma yaklaşımı]
- Hangi dosyalar yedeklenmeli?
- Sorun olursa ne yapılmalı?
- Acil durum erişim yolu var mı?

─────────────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════════════
ADIM 5: UYGULAMA PLANI
═══════════════════════════════════════════════════════════════════

Mantıklı, adım adım bir uygulama planı oluştur:

1. [İlk hazırlık adımı - genellikle backup/test]
2. [Ana yapılandırma adımı]
3. [Doğrulama/test adımı]
4. [Finalizasyon - restart/reload vb.]
...

Her adım SMAART olmalı (Specific, Measurable, Achievable, Actionable, Realistic, Testable)

─────────────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════════════
ADIM 6: DETAYLI KULLANICI CEVABI
═══════════════════════════════════════════════════════════════════

Şimdi yukarıdaki analizine dayanarak kullanıcı için tam bir cevap yaz.

**ZORUNLU FORMAT:**

## 📋 ÖZET
[1-2 cümle: Ne yapılacak ve neden?]

## 🎯 GEREKÇE
[Neden bu öneri gerekli? Hangi tehditlere/risklere karşı koruma sağlıyor?]

## 🔐 ZERO TRUST İLİŞKİSİ
[Bu öneri hangi ZT prensiplerini destekliyor? Her prensip için 1-2 cümle açıklama]

Örnek:
- **Least Privilege**: Root erişimini kısıtlayarak sadece gerekli yetkiler verilir...
- **Continuous Verification**: Her erişimde kimlik doğrulama yapılır...

## ⚠️ RİSK ETKİSİ
- **Seviye**: [risk seviyesi]
- **Açıklama**: [Bu değişiklik sistem üzerinde nasıl bir etki yaratır? Dikkat edilmesi gerekenler]

## ✅ ÖNERİLEN ADIMLAR

### Adım 1: [Başlık]
[Detaylı açıklama ve komutlar]

### Adım 2: [Başlık]
[Detaylı açıklama ve komutlar]

[Gerektiği kadar adım ekle...]

## 💻 ÖRNEK KOMUTLAR/KONFİGÜRASYONLAR

**Bash Script Örneği:** (Linux için)
```bash
#!/bin/bash
# [Script açıklaması]

[Çalışan, test edilmiş komutlar]
```

**PowerShell Script Örneği:** (Windows için)
```powershell
# [Script açıklaması]

[Çalışan, test edilmiş komutlar]
```

**Not:** Komutlar gerçek ortamınıza göre uyarlanmalıdır.

## 📚 STANDART REFERANSLARI

[Her referans için madde numarası ve kısa açıklama]

Örnek:
- **CIS_Ubuntu_22_04:5.2.5**: SSH PermitRootLogin disabled
  → Root hesabı ile doğrudan SSH erişimini engeller

- **NIST_800-53:AC-17**: Remote Access
  → Uzaktan erişim kontrollerinin uygulanması

## 🔄 ROLLBACK YAKLAŞIMI

[Pratik, adım adım rollback talimatları]

**Rollback Komutları:**
```bash
# [Somut geri alma komutları]
```

**Acil Durum:** [Alternatif erişim yolları]

═══════════════════════════════════════════════════════════════════

⚠️  KRİTİK KURALLAR:

1. **Her adımı MUTLAKA tamamla** - Atlama yapma
2. **Saldırgan içerik üretme** - Sadece savunma odaklı ol
3. **Emin olmadığın detayları uydurma** - "Genel olarak..." de
4. **ZT prensiplerine sadık kal** - Her öneride ZT'yi vurgula
5. **Pratik ve uygulanabilir ol** - Teorik değil, actionable öneriler sun
6. **Rollback her zaman belirt** - Kullanıcı geri alma yolu bilmeli

Yukarıdaki 6 ADIMI ve ADIM 6'daki FORMAT'ı TAM OLARAK takip et.
Kullanıcıya gönderilmeye hazır, temiz bir çıktı üret.
"""

        return prompt

    def parse_cot_response(self, raw_response: str, ctx: RequestContext) -> RequestContext:
        """
        CoT response'unu parse et ve context'e yaz.

        Args:
            raw_response: LLM'den gelen tam yanıt
            ctx: Request context (update edilecek)

        Returns:
            Updated context
        """

        # ADIM 1: Safety classification
        safety_match = re.search(
            r'\*\*SONUÇ:\*\*\s*\[?(defensive_security|ambiguous|offensive_illegal)',
            raw_response,
            re.IGNORECASE
        )
        if safety_match:
            from context import SafetyResult
            ctx.safety = SafetyResult(category=safety_match.group(1))  # type: ignore

        # ADIM 2: Intent
        intent_match = re.search(
            r'\*\*Intent:\*\*\s*\[?(os_hardening|script_or_config|incident_analysis|conceptual_explanation)',
            raw_response,
            re.IGNORECASE
        )
        if intent_match:
            ctx.intent = intent_match.group(1)  # type: ignore

        target_match = re.search(r'\*\*Hedef Alan:\*\*\s*\[?([^\]]+)', raw_response)
        if target_match:
            ctx.target_area = target_match.group(1).strip()

        # ADIM 3: ZT Principles (basit regex - gerçekte daha robust olmalı)
        zt_section = re.search(
            r'ADIM 3:.*?\*\*İlgili Prensipler:\*\*(.*?)─{5,}',
            raw_response,
            re.DOTALL | re.IGNORECASE
        )
        if zt_section:
            zt_text = zt_section.group(1)
            # Extract principle names
            principles = re.findall(r'(least_privilege|continuous_verification|assume_breach|micro_segmentation|strong_identity)', zt_text, re.IGNORECASE)
            ctx.zt_principles = list(set(p.lower() for p in principles))

        # Standards
        standards = re.findall(r'(CIS_[A-Za-z0-9_]+:\S+|NIST_[0-9-]+:\S+|ISO_[0-9]+:\S+)', raw_response)
        if standards:
            ctx.standards = list(set(standards))

        # ADIM 4: Risk level
        risk_match = re.search(r'\*\*Risk Seviyesi:\*\*\s*\[?(low|medium|high|critical)', raw_response, re.IGNORECASE)
        if risk_match:
            ctx.extra["impact_level"] = risk_match.group(1).lower()

        # Rollback approach
        rollback_match = re.search(
            r'\*\*Rollback Stratejisi:\*\*(.*?)(?:─{5,}|ADIM 5)',
            raw_response,
            re.DOTALL | re.IGNORECASE
        )
        if rollback_match:
            ctx.extra["rollback_approach"] = rollback_match.group(1).strip()

        # ADIM 6: Final answer (Kullanıcıya gösterilecek kısım)
        final_answer_match = re.search(
            r'ADIM 6:.*?(?:## 📋 ÖZET.*)',
            raw_response,
            re.DOTALL | re.IGNORECASE
        )
        if final_answer_match:
            # "## 📋 ÖZET" ile başlayan kısmı al
            answer_start = final_answer_match.group(0).find("## 📋 ÖZET")
            if answer_start != -1:
                final_answer = final_answer_match.group(0)[answer_start:]
                # Sondaki gereksiz kısımları temizle
                final_answer = re.sub(r'═{10,}.*', '', final_answer, flags=re.DOTALL)
                ctx.final_answer = final_answer.strip()
        else:
            # Fallback: Tüm yanıtı kullan
            ctx.final_answer = raw_response

        return ctx


# Convenience function
def run_cot_analysis(
    llm_large,
    ctx: RequestContext,
    use_few_shot: bool = True
) -> RequestContext:
    """
    CoT analysis çalıştır (single LLM call).

    Args:
        llm_large: Büyük LLM model instance
        ctx: Request context
        use_few_shot: Few-shot examples kullan

    Returns:
        Updated context with final_answer
    """

    analyzer = CoTSecurityAnalyzer(use_few_shot=use_few_shot)

    # Prompt oluştur
    prompt = analyzer.build_cot_prompt(ctx)

    # LLM çağrısı (TEK ÇAĞRI!)
    raw_response = llm_large(prompt)

    # Parse ve context'e yaz
    ctx = analyzer.parse_cot_response(raw_response, ctx)

    return ctx
