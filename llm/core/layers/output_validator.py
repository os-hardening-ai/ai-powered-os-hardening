"""
Output Validation Layer
------------------------
LLM ciktisini kalite kontrolunden gecirir:

1. Regex-based tehlikeli komut kontrolu (ALWAYS)
2. Format ve uzunluk kontrolu (ALWAYS)
3. LLM-based quality check (OPTIONAL - only for critical queries)

Hybrid approach:
- Hafif validation: Her zaman (0ms latency, $0 cost)
- LLM-based judge: Sadece action_request icin (1-2s latency, $0.001 cost)
"""

from __future__ import annotations
from typing import Callable, Optional, List
from dataclasses import dataclass
import re


LLMCallable = Callable[[str], str]


@dataclass
class ValidationResult:
    """Output validation result"""
    is_valid: bool
    issues: List[str]  # Tespit edilen sorunlar
    corrected_output: Optional[str]  # Duzeltilmis cikti (eger varsa)
    validation_method: str  # "regex" veya "llm"


class OutputValidator:
    """
    Output Validation Layer

    Hybrid approach:
    - Regex-based: Fast, rule-based validation (ALWAYS)
    - LLM-based: Deep quality check (ONLY for critical queries)
    """

    # Tehlikeli komutlar (ASLA script'te bulunmamali)
    DANGEROUS_COMMANDS = [
        r"\brm\s+-rf\s+/",  # rm -rf /
        r"\bformat\s+C:",   # format C:
        r"\bdd\s+if=/dev/zero\s+of=/dev/sd",  # Disk wipe
        r"\bmkfs\.",        # Format filesystem
        r"\b:\(\)\{.*\|&\};:",  # Fork bomb
        r"\bchmod\s+777\s+/",   # Dangerous permissions on root
        r"\bchown\s+.*:.*\s+/", # Ownership change on root
        r">\s*/dev/sda",    # Direct disk write
        r"curl.*\|\s*bash", # Pipe to bash (security risk)
        r"wget.*\|\s*sh",   # Pipe to sh (security risk)
    ]

    # Minimum cevap uzunlugu (cok kisa cevaplar kalitesiz olabilir)
    MIN_ANSWER_LENGTH = 50

    def __init__(
        self,
        llm: Optional[LLMCallable] = None,
        use_llm_validation: bool = False,
        debug: bool = False
    ):
        self.llm = llm
        self.use_llm_validation = use_llm_validation
        self.debug = debug

    def validate(
        self,
        output: str,
        intent: str = "info_request",
        use_deep_check: bool = False
    ) -> ValidationResult:
        """
        Validate LLM output

        Args:
            output: LLM ciktisi
            intent: Intent type (action_request icin daha strict)
            use_deep_check: LLM-based deep validation kullan mi?

        Returns:
            ValidationResult
        """
        if self.debug:
            print("\n[Output Validation] Checking output...")

        issues: List[str] = []

        # ─── STEP 1: Regex-based Validation (ALWAYS) ───

        # Check 1: Dangerous commands
        for pattern in self.DANGEROUS_COMMANDS:
            if re.search(pattern, output, re.IGNORECASE):
                issues.append(f"Tehlikeli komut tespit edildi: {pattern}")

        # Check 2: Minimum length
        if len(output.strip()) < self.MIN_ANSWER_LENGTH:
            issues.append(f"Cevap cok kisa ({len(output)} char, min {self.MIN_ANSWER_LENGTH})")

        # Check 3: For action_request, require code block
        if intent == "action_request":
            if "```" not in output:
                issues.append("Script icin kod blogu (```) bulunamadi")

        # Check 4: Look for common LLM errors
        error_phrases = [
            "i cannot", "i can't", "i am unable to",
            "i don't have access to", "i'm not able to",
            "as an ai", "as a language model"
        ]
        for phrase in error_phrases:
            if phrase in output.lower():
                issues.append(f"LLM refusal phrase detected: '{phrase}'")

        # ─── STEP 2: LLM-based Validation (OPTIONAL) ───

        corrected_output = None

        if use_deep_check and self.use_llm_validation and self.llm:
            if self.debug:
                print("  [Deep Check] Running LLM-based validation...")

            llm_result = self._llm_based_validation(output, intent)
            issues.extend(llm_result["issues"])

            if llm_result["needs_correction"]:
                corrected_output = llm_result["corrected_output"]

        # ─── Result ───

        is_valid = len(issues) == 0

        if self.debug:
            if is_valid:
                print("  [OK] Output validation passed")
            else:
                print(f"  [WARNING] {len(issues)} issue(s) found:")
                for issue in issues[:3]:  # Show first 3
                    print(f"    - {issue}")

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            corrected_output=corrected_output,
            validation_method="llm" if (use_deep_check and self.llm) else "regex"
        )

    def _llm_based_validation(self, output: str, intent: str) -> dict:
        """
        LLM-based deep validation

        Returns:
            {
                "issues": List[str],
                "needs_correction": bool,
                "corrected_output": Optional[str]
            }
        """
        if not self.llm:
            return {"issues": [], "needs_correction": False, "corrected_output": None}

        prompt = f"""Asagidaki guvenlik asistani cevabini degerlendir.

CEVAP:
\"\"\"{output}\"\"\"

INTENT: {intent}

GOREV:
Bu cevabi kontrol et ve sunlari belirle:

1) Guvenlik sorunlari var mi?
   - Saldiri/exploit yonlendirmesi
   - Tehlikeli komutlar
   - Yetkisiz erisim onerileri

2) Teknik hatalar var mi?
   - Yanlis bilgi
   - Eksik aciklama
   - Gercekci olmayan oneriler

3) Zero Trust prensipleri eksik mi?
   - least_privilege
   - continuous_verification
   - assume_breach

CIKTI:
Sadece problemleri listele (her satir bir sorun).
Eger sorun yoksa "OK" yaz.

ORNEK:
- SSH root login kapatma onerilmemis (least_privilege)
- CIS Benchmark referansi yok
- Rollback stratejisi aciklanmamis
""".strip()

        try:
            response = self.llm(prompt).strip()

            if response.upper() == "OK" or not response:
                return {
                    "issues": [],
                    "needs_correction": False,
                    "corrected_output": None
                }

            # Parse issues (each line is an issue)
            issues = [
                line.strip("- ").strip()
                for line in response.split("\n")
                if line.strip() and not line.strip().startswith("#")
            ]

            # For now, we don't auto-correct (can be added later)
            return {
                "issues": issues,
                "needs_correction": len(issues) > 2,  # If 3+ issues, correction recommended
                "corrected_output": None
            }

        except Exception as e:
            if self.debug:
                print(f"  [WARNING] LLM validation failed: {e}")
            return {"issues": [], "needs_correction": False, "corrected_output": None}


# ─────────────────────────────────────────────
# Convenience Function
# ─────────────────────────────────────────────

def validate_output(
    output: str,
    intent: str = "info_request",
    llm: Optional[LLMCallable] = None,
    use_deep_check: bool = False,
    debug: bool = False
) -> ValidationResult:
    """
    Convenience function for output validation

    Args:
        output: LLM output to validate
        intent: Intent type
        llm: Optional LLM for deep validation
        use_deep_check: Use LLM-based validation
        debug: Debug mode

    Returns:
        ValidationResult
    """
    validator = OutputValidator(
        llm=llm,
        use_llm_validation=(llm is not None),
        debug=debug
    )

    return validator.validate(
        output=output,
        intent=intent,
        use_deep_check=use_deep_check
    )
