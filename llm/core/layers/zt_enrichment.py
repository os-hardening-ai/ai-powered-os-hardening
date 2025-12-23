"""
Zero Trust Enrichment Layer
----------------------------
Kullanici isteğini analiz ederek:
- Zero Trust prensiplerini (least_privilege, continuous_verification, vb.)
- Spesifik standart referanslarini (CIS madde numarali)
- Risk seviyesini (low/medium/high/critical)
- Rollback stratejisini

ile zenginlestirir.

PROJE GEREKSINIMI:
"Oneriler; gerekce, risk etkisi, zero-trust prensibi ile iliskisi
ve geri alma (rollback) yaklasimlarryla birlikte sunulacaktir."
"""

from __future__ import annotations
from typing import Callable, Optional, List
from dataclasses import dataclass
import json

from llm.core.context import RequestContext


LLMCallable = Callable[[str], str]


@dataclass
class ZTEnrichment:
    """Zero Trust enrichment result"""
    zt_principles: List[str]  # Zero Trust prensipleri
    standards: List[str]  # Spesifik standart referanslari (CIS_Ubuntu_22_04:5.2.5)
    impact_level: str  # low, medium, high, critical
    rollback_approach: str  # Geri alma stratejisi
    reasoning: str  # Neden bu prensipleri sectik?


class ZeroTrustEnricher:
    """
    Zero Trust & Standards Enrichment Layer

    Kullanici sorusuna uygun:
    - ZT prensiplerini
    - Spesifik CIS/NIST/ISO madde referanslarini
    - Risk seviyesini
    - Rollback stratejisini

    belirler.
    """

    def __init__(self, llm: LLMCallable, debug: bool = False):
        self.llm = llm
        self.debug = debug

    def enrich(self, ctx: RequestContext) -> ZTEnrichment:
        """
        Analyze user question and enrich with ZT principles, standards, risk level
        """
        if self.debug:
            print("\n[ZT Enrichment] Analyzing question...")

        prompt = self._build_prompt(ctx)

        try:
            raw_response = self.llm(prompt)
            enrichment = self._parse_response(raw_response, ctx)
        except Exception as e:
            if self.debug:
                print(f"  [WARNING] ZT enrichment failed: {e}, using fallback")
            enrichment = self._get_fallback(ctx)

        if self.debug:
            print(f"  ZT Principles: {', '.join(enrichment.zt_principles)}")
            print(f"  Standards: {', '.join(enrichment.standards[:3])}...")
            print(f"  Impact Level: {enrichment.impact_level}")

        return enrichment

    def _build_prompt(self, ctx: RequestContext) -> str:
        """Build ZT enrichment prompt"""
        intent = ctx.intent or "generic"
        os_name = ctx.os or "ubuntu_22_04"
        role = ctx.role or "sysadmin"

        return f"""Asagidaki guvenlik istegi icin Zero Trust ve standart analizi yap.

KULLANICI MESAJI:
\"\"\"{ctx.user_question}\"\"\"

BAGLAM:
- Intent: {intent}
- Isletim sistemi: {os_name}
- Kullanici rolu: {role}
- Guvenlik seviyesi: {ctx.security_level}
- Zero Trust olgunluk: {ctx.zt_maturity}

GOREV:
Bu istegi analiz ederek sunlari belirle:

1) Zero Trust Prensipleri (zt_principles):
   - least_privilege (en az ayricalik)
   - continuous_verification (surekli dogrulama)
   - assume_breach (ihlal varsayimi)
   - micro_segmentation (mikro segmentasyon)
   - strong_identity (guclu kimlik dogrulama)
   - device_posture (cihaz durum kontrolu)
   - secure_access (guvenli erisim)
   - visibility_and_analytics (gorunurluk ve analitik)

2) Standart Referanslari (standards):
   FORMAT: "FRAMEWORK:SPECIFIC_CONTROL"

   CIS Benchmark Ornekleri:
   - "CIS_Ubuntu_22_04:5.2.5" (SSH PermitRootLogin)
   - "CIS_Ubuntu_22_04:5.3.1" (Password complexity)
   - "CIS_Windows_Server_2022:2.3.7.8" (Account lockout)

   NIST Ornekleri:
   - "NIST_800-207:3.2" (Zero Trust Architecture)
   - "NIST_800-53:AC-2" (Account Management)
   - "NIST_800-53:IA-5" (Authenticator Management)

   ISO 27001 Ornekleri:
   - "ISO_27001:A.9.2.3" (Management of privileged access)
   - "ISO_27001:A.13.1.1" (Network controls)

3) Risk/Etki Seviyesi (impact_level):
   - "low": Dusuk risk, sistem kararliligina minimal etki
   - "medium": Orta risk, dikkatli uygulama gerekir
   - "high": Yuksek risk, test ortaminda denenmeli
   - "critical": Kritik sistem bileseni, rollback plani zorunlu

4) Rollback Yaklasimi (rollback_approach):
   Kisa aciklama (1-2 cumle):
   - Hangi dosyalarin yedeklenmesi gerekir?
   - Geri alma komutu/adimi nedir?

5) Geceklendirme (reasoning):
   Neden bu ZT prensiplerini ve standartlari sectik? (1 cumle)

CIKTI FORMATI:
Sadece gecerli bir JSON dondur. Ek aciklama, yorum, markdown ekleme.

ORNEK:
{{
  "zt_principles": ["least_privilege", "continuous_verification", "strong_identity"],
  "standards": ["CIS_Ubuntu_22_04:5.2.5", "CIS_Ubuntu_22_04:5.2.10", "NIST_800-53:AC-17"],
  "impact_level": "high",
  "rollback_approach": "SSH config dosyasini yedekle: 'sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak'. Geri almak icin yedekten geri yukle ve servisi yeniden baslat.",
  "reasoning": "SSH root girisini kapatmak least_privilege prensibine uygun ve CIS 5.2.5'te onerilmektedir."
}}

ONEMLI:
- Standart referanslari MUTLAKA spesifik madde numarali olmali
- OS ve intent'e uygun referanslar sec
- Rollback aciklamasi pratik ve uygulanabilir olmali
""".strip()

    def _parse_response(self, raw: str, ctx: RequestContext) -> ZTEnrichment:
        """Parse LLM response"""
        try:
            # Clean markdown code blocks if present
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            data = json.loads(raw)

            # Parse ZT principles
            zt_principles = data.get("zt_principles", [])
            if not isinstance(zt_principles, list):
                zt_principles = []
            zt_principles = [str(p).strip() for p in zt_principles if str(p).strip()]

            # Parse standards (must have colon for specific control)
            standards = data.get("standards", [])
            if not isinstance(standards, list):
                standards = []
            standards = [
                str(s).strip()
                for s in standards
                if str(s).strip() and ":" in str(s)
            ]

            # Parse impact level
            impact_level = str(data.get("impact_level", "medium")).lower()
            valid_impacts = ("low", "medium", "high", "critical")
            if impact_level not in valid_impacts:
                impact_level = "medium"

            # Parse rollback approach
            rollback = str(data.get("rollback_approach", "")).strip()
            if not rollback:
                rollback = "Degisiklik oncesi ilgili dosyalari yedekleyin. Sorun durumunda yedekten geri yukleyin."

            # Parse reasoning
            reasoning = str(data.get("reasoning", "")).strip()
            if not reasoning:
                reasoning = "Bu prensip ve standartlar, istenen guvenlik seviyesine uygundur."

            return ZTEnrichment(
                zt_principles=zt_principles,
                standards=standards,
                impact_level=impact_level,
                rollback_approach=rollback,
                reasoning=reasoning
            )

        except Exception as e:
            if self.debug:
                print(f"  [WARNING] Failed to parse ZT response: {e}")
            return self._get_fallback(ctx)

    def _get_fallback(self, ctx: RequestContext) -> ZTEnrichment:
        """Get fallback enrichment based on context"""
        # Determine OS-specific standards
        os_lower = (ctx.os or "ubuntu_22_04").lower()

        if "ubuntu" in os_lower or "debian" in os_lower:
            standards = [
                "CIS_Ubuntu_22_04:5.2.5",  # SSH PermitRootLogin
                "CIS_Ubuntu_22_04:5.3.1",  # Password complexity
                "NIST_800-53:AC-2"         # Account Management
            ]
        elif "windows" in os_lower:
            standards = [
                "CIS_Windows_Server_2022:2.3.7.8",  # Account lockout
                "CIS_Windows_Server_2022:2.3.11.5", # Network security
                "NIST_800-53:AC-2"                   # Account Management
            ]
        elif "centos" in os_lower or "rhel" in os_lower:
            standards = [
                "CIS_CentOS_9:5.2.5",      # SSH hardening
                "CIS_CentOS_9:5.3.1",      # Password policy
                "NIST_800-53:AC-2"         # Account Management
            ]
        else:
            standards = [
                "NIST_800-207:3.2",        # Zero Trust Architecture
                "NIST_800-53:AC-2",        # Account Management
                "ISO_27001:A.9.2.3"        # Privileged access
            ]

        # Determine impact level based on security_level
        if ctx.security_level == "strict":
            impact_level = "high"
        elif ctx.security_level == "minimal":
            impact_level = "low"
        else:
            impact_level = "medium"

        return ZTEnrichment(
            zt_principles=["least_privilege", "continuous_verification"],
            standards=standards,
            impact_level=impact_level,
            rollback_approach="Degisiklik oncesi ilgili config dosyalarini yedekleyin. Sorun durumunda yedekten geri yukleyin.",
            reasoning="Temel guvenlik prensipleri ve standartlar uygulanmistir."
        )
