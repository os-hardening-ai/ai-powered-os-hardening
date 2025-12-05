# steps/zt_mapper.py
from __future__ import annotations

"""
Enhanced ZT Mapper - Proje Gereksinimlerine Uygun
-------------------------------------------------
Kullanıcı isteğini analiz ederek:

1. İlgili Zero Trust prensiplerini (zt_principles)
2. Spesifik standart referanslarını (standards) - CIS madde numaralı
3. Risk seviyesini (impact_level)
4. Rollback stratejisini (rollback_approach)

ile etiketler.

PROJE GEREKSİNİMİ:
"Öneriler; gerekçe, risk etkisi, zero-trust prensibi ile ilişkisi 
(ör. identity-centric access, least privilege, micro-segmentation) 
ve geri alma (rollback) yaklaşımlarıyla birlikte sunulacaktır."
"""

import json
from typing import Callable, TypedDict, List, Optional

from context import RequestContext


LLMCallable = Callable[[str], str]


class ZTRawResult(TypedDict, total=False):
    """LLM'den gelen ham JSON'un beklenen alanları."""
    zt_principles: list[str]
    standards: list[str]
    impact_level: str  # low, medium, high, critical
    rollback_approach: str  # Geri alma stratejisi


def _build_enhanced_zt_prompt(ctx: RequestContext) -> str:
    """
    Proje gereksinimlerine uygun, detaylı ZT haritalama prompt'u.
    
    Özellikler:
    - Spesifik CIS madde numaraları
    - Zero Trust prensip eşleştirme
    - Risk seviyesi
    - Rollback stratejisi
    """
    intent = ctx.intent or "generic_qna"
    target_area = ctx.target_area or "general"
    os_name = ctx.os or "ubuntu_22_04"
    role = ctx.role or "sysadmin"

    return f"""
Aşağıdaki güvenlik isteği için **detaylı Zero Trust ve standart analizi** yap.

KULLANICI MESAJI:
\"\"\"{ctx.user_question}\"\"\"

BAĞLAM:
- Intent: {intent}
- Hedef alan: {target_area}
- İşletim sistemi: {os_name}
- Kullanıcı rolü: {role}
- Güvenlik seviyesi: {ctx.security_level}
- Zero Trust olgunluk: {ctx.zt_maturity}


GÖREV:
Bu isteği analiz ederek şunları belirle:

1) **Zero Trust Prensipleri** (zt_principles):
   - least_privilege (en az ayrıcalık)
   - continuous_verification (sürekli doğrulama)
   - assume_breach (ihlal varsayımı)
   - micro_segmentation (mikro segmentasyon)
   - strong_identity (güçlü kimlik doğrulama)
   - device_posture (cihaz duruş kontrolü)
   - secure_access (güvenli erişim)
   - visibility_and_analytics (görünürlük ve analitik)

2) **Standart Referansları** (standards):
   FORMAT: "FRAMEWORK:SPECIFIC_CONTROL"
   
   CIS Benchmark Örnekleri:
   - "CIS_Ubuntu_22_04:5.2.5" (SSH PermitRootLogin)
   - "CIS_Ubuntu_22_04:5.3.1" (Password complexity)
   - "CIS_Windows_Server_2022:2.3.7.8" (Account lockout)
   
   NIST Örnekleri:
   - "NIST_800-207:3.2" (Zero Trust Architecture)
   - "NIST_800-53:AC-2" (Account Management)
   - "NIST_800-53:IA-5" (Authenticator Management)
   
   ISO 27001 Örnekleri:
   - "ISO_27001:A.9.2.3" (Management of privileged access)
   - "ISO_27001:A.13.1.1" (Network controls)
   - "ISO_27001:A.12.4.1" (Event logging)

3) **Risk/Etki Seviyesi** (impact_level):
   - "low": Düşük risk, sistem kararlılığına minimal etki
   - "medium": Orta risk, dikkatli uygulama gerekir
   - "high": Yüksek risk, test ortamında denenmeli
   - "critical": Kritik sistem bileşeni, rollback planı zorunlu

4) **Rollback Yaklaşımı** (rollback_approach):
   Kısa açıklama (1-2 cümle):
   - Hangi dosyaların yedeklenmesi gerekir?
   - Geri alma komutu/adımı nedir?
   - Örnek: "Önce /etc/ssh/sshd_config yedekle. Sorun olursa: 
     'sudo cp /etc/ssh/sshd_config.bak /etc/ssh/sshd_config && sudo systemctl restart sshd'"


ÇIKTI FORMATI:

Sadece geçerli bir JSON döndür. Ek açıklama, yorum, markdown ekleme.

ÖRNEK:
{{
  "zt_principles": [
    "least_privilege",
    "continuous_verification",
    "strong_identity"
  ],
  "standards": [
    "CIS_Ubuntu_22_04:5.2.5",
    "CIS_Ubuntu_22_04:5.2.10",
    "NIST_800-53:AC-17",
    "ISO_27001:A.9.2.3"
  ],
  "impact_level": "high",
  "rollback_approach": "SSH config dosyasını yedekle: 'sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak'. Geri almak için yedekten geri yükle ve servisi yeniden başlat."
}}


ÖNEMLİ:
- Standart referansları MUTLAKA spesifik madde numaralı olmalı
- Genel referans yerine (örn: "CIS Ubuntu" ❌) spesifik madde ver (örn: "CIS_Ubuntu_22_04:5.2.5" ✅)
- OS ve intent'e uygun referanslar seç
- Rollback açıklaması pratik ve uygulanabilir olmalı
""".strip()


def _parse_enhanced_zt_response(raw: str) -> ZTRawResult:
    """
    LLM'den gelen ham string'i JSON'a parse eder.
    
    Proje gereksinimleri için zenginleştirilmiş parser.
    """
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("LLM response is not a JSON object")

        # ZT Principles
        zt_principles_raw = data.get("zt_principles", [])
        if not isinstance(zt_principles_raw, list):
            zt_principles_raw = []
        zt_principles: List[str] = [
            str(item).strip()
            for item in zt_principles_raw
            if str(item).strip()
        ]

        # Standards (spesifik madde numaralı)
        standards_raw = data.get("standards", [])
        if not isinstance(standards_raw, list):
            standards_raw = []
        standards: List[str] = [
            str(item).strip()
            for item in standards_raw
            if str(item).strip() and ":" in str(item)  # MUTLAKA madde numarası olmalı
        ]

        # Impact Level
        impact_level_raw = str(data.get("impact_level", "medium")).lower()
        valid_impacts = ("low", "medium", "high", "critical")
        impact_level = impact_level_raw if impact_level_raw in valid_impacts else "medium"

        # Rollback Approach
        rollback = str(data.get("rollback_approach", "")).strip()
        if not rollback:
            rollback = "Değişiklik öncesi ilgili dosyaları yedekleyin. Sorun durumunda yedekten geri yükleyin."

        return ZTRawResult(
            zt_principles=zt_principles,
            standards=standards,
            impact_level=impact_level,
            rollback_approach=rollback,
        )

    except Exception:
        # Fallback: En azından temel değerler dönsün
        return ZTRawResult(
            zt_principles=["least_privilege", "continuous_verification"],
            standards=["CIS_Ubuntu_22_04:5.2.5"],  # Genel SSH hardening
            impact_level="medium",
            rollback_approach="Değişiklik öncesi ilgili config dosyalarını yedekleyin.",
        )


def run_enhanced_zt_mapper(llm: LLMCallable, ctx: RequestContext) -> RequestContext:
    """
    Enhanced Zero Trust & Standart Haritalama.
    
    Proje gereksinimlerine göre:
    - Spesifik CIS/NIST/ISO madde referansları
    - Risk seviyesi
    - Rollback stratejisi
    
    ekler.
    """
    prompt = _build_enhanced_zt_prompt(ctx)
    
    try:
        raw_response = llm(prompt)
    except Exception:
        # LLM çağrısı başarısız, fallback kullan
        raw_response = "{}"  # Parser default değerleri kullanacak

    parsed = _parse_enhanced_zt_response(raw_response)

    # Context'e yaz
    ctx.zt_principles = parsed.get("zt_principles", [])
    ctx.standards = parsed.get("standards", [])
    
    # Yeni alanlar (context.py'a eklenecek)
    ctx.extra["impact_level"] = parsed.get("impact_level", "medium")
    ctx.extra["rollback_approach"] = parsed.get("rollback_approach", "")

    return ctx


# Backward compatibility için eski fonksiyon adını tut
run_zt_mapper = run_enhanced_zt_mapper