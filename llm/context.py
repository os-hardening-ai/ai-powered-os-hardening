# context.py
from __future__ import annotations

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# 1) Sabit tip tanımları
# ─────────────────────────────────────────────

SafetyCategory = Literal[
    "defensive_security",
    "offensive_illegal",
    "generic_it",
    "ambiguous",
]

IntentType = Literal[
    # Security odaklı intentler
    "os_hardening",
    "script_or_config",
    "incident_analysis",
    "conceptual_explanation",
    "generic_qna",
    # Smalltalk / sohbet intentleri
    "smalltalk_greeting",
    "smalltalk_farewell",
    "smalltalk_other",
]

SecurityLevel = Literal["minimal", "balanced", "strict"]
ZeroTrustMaturity = Literal["low", "medium", "high"]

# Proje için yeni: Impact Level
ImpactLevel = Literal["low", "medium", "high", "critical"]


# ─────────────────────────────────────────────
# 2) Alt model sınıfları
# ─────────────────────────────────────────────

class SafetyResult(BaseModel):
    """Input safety classifier çıktısı."""
    category: SafetyCategory
    reason: Optional[str] = None


class JudgeResult(BaseModel):
    """Output judge / self-check çıktısı."""
    safety: Literal["safe", "minor_issues", "unsafe"]
    hallucination_risk: float = Field(ge=0.0, le=1.0)
    needs_rewrite: bool
    issues: List[str] = Field(default_factory=list)


class PlanStep(BaseModel):
    """Görev planlayıcı adımı."""
    id: int
    goal: str
    detail: Optional[str] = None


class Plan(BaseModel):
    """Görev planlayıcı çıktısı."""
    steps: List[PlanStep] = Field(default_factory=list)


# ─────────────────────────────────────────────
# 3) Proje için yeni modeller
# ─────────────────────────────────────────────

class StandardReference(BaseModel):
    """
    Standart referansı detaylı modeli.
    
    Örnek:
        framework: "CIS"
        control_id: "Ubuntu_22_04:5.2.5"
        description: "SSH PermitRootLogin disabled"
    """
    framework: str  # CIS, NIST, ISO
    control_id: str  # Ubuntu_22_04:5.2.5, 800-53:AC-2, A.9.2.3
    description: Optional[str] = None


class RollbackInfo(BaseModel):
    """
    Rollback/geri alma bilgileri.
    
    Proje gereksinimi: "geri alma (rollback) yaklaşımlarıyla birlikte sunulacaktır"
    """
    approach: str  # Genel yaklaşım açıklaması
    commands: List[str] = Field(default_factory=list)  # Somut rollback komutları
    backup_files: List[str] = Field(default_factory=list)  # Yedeklenmesi gereken dosyalar


# ─────────────────────────────────────────────
# 4) Ana context state modeli
# ─────────────────────────────────────────────

class RequestContext(BaseModel):
    """
    Proje gereksinimlerine göre genişletilmiş RequestContext.
    
    Yeni alanlar:
    - impact_level: Risk seviyesi (low/medium/high/critical)
    - rollback_info: Geri alma stratejisi
    - standard_references: Detaylı standart referansları
    - script_examples: Üretilen komut/config örnekleri
    """

    # ── Giriş parametreleri ──
    user_question: str
    os: Optional[str] = None
    role: Optional[str] = None
    security_level: SecurityLevel = "balanced"
    zt_maturity: ZeroTrustMaturity = "medium"
    
    retrieved_context: Optional[str] = None

    # ── 1) Safety ──
    safety: Optional[SafetyResult] = None

    # ── 2) Intent ──
    intent: Optional[IntentType] = None
    target_area: Optional[str] = None
    needs_script: bool = False

    # ── 3) Zero Trust & Standartlar ──
    zt_principles: List[str] = Field(default_factory=list)
    standards: List[str] = Field(default_factory=list)  # Basit string listesi (backward compat)
    
    # 🆕 Proje için yeni: Detaylı standart referansları
    standard_references: List[StandardReference] = Field(default_factory=list)

    # ── 4) Plan ──
    plan: Optional[Plan] = None

    # ── 5) Answer ──
    draft_answer: Optional[str] = None

    # ── 6) Judge ──
    judge_result: Optional[JudgeResult] = None

    # ── 7) Final ──
    final_answer: Optional[str] = None

    # ── 🆕 Proje için yeni alanlar ──
    
    # Risk/Etki seviyesi
    impact_level: ImpactLevel = "medium"
    
    # Rollback bilgisi
    rollback_info: Optional[RollbackInfo] = None
    
    # Üretilen script örnekleri (ayrı alanda tutmak için)
    script_examples: Dict[str, str] = Field(default_factory=dict)
    # Örnek: {"bash": "#!/bin/bash\n...", "powershell": "Set-ItemProperty..."}

    # ── Meta ──
    request_id: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True
        validate_assignment = True
    
    # ─────────────────────────────────────────────
    # Helper metodlar
    # ─────────────────────────────────────────────
    
    def add_standard_reference(
        self,
        framework: str,
        control_id: str,
        description: Optional[str] = None,
    ) -> None:
        """Standart referansı ekle."""
        ref = StandardReference(
            framework=framework,
            control_id=control_id,
            description=description,
        )
        self.standard_references.append(ref)
    
    def set_rollback(
        self,
        approach: str,
        commands: Optional[List[str]] = None,
        backup_files: Optional[List[str]] = None,
    ) -> None:
        """Rollback bilgisi ekle."""
        self.rollback_info = RollbackInfo(
            approach=approach,
            commands=commands or [],
            backup_files=backup_files or [],
        )
    
    def get_formatted_standards(self) -> str:
        """Standartları formatlı string olarak döndür."""
        if not self.standard_references:
            return "Standart referansı yok"
        
        lines = []
        for ref in self.standard_references:
            desc = f": {ref.description}" if ref.description else ""
            lines.append(f"- {ref.framework}:{ref.control_id}{desc}")
        
        return "\n".join(lines)
    
    def get_rollback_summary(self) -> str:
        """Rollback bilgisini özet string olarak döndür."""
        if not self.rollback_info:
            return "Rollback bilgisi belirtilmedi"
        
        summary = [self.rollback_info.approach]
        
        if self.rollback_info.backup_files:
            summary.append(f"\nYedeklenecek dosyalar: {', '.join(self.rollback_info.backup_files)}")
        
        if self.rollback_info.commands:
            summary.append("\nRollback komutları:")
            for cmd in self.rollback_info.commands:
                summary.append(f"  {cmd}")
        
        return "\n".join(summary)