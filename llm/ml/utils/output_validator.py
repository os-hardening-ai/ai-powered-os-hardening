# utils/output_validator.py
"""
Output Validation & Quality Checks

LLM Best Practices:
- Hallucination detection
- Safety checking
- PII/secret detection
- Response quality scoring

References:
- LLM Evaluation Metrics: https://www.confident-ai.com/blog/llm-evaluation-metrics-everything-you-need-for-llm-evaluation
- LLM Guardrails: https://www.datadoghq.com/blog/llm-guardrails-best-practices/
"""

from __future__ import annotations
import re
from typing import List
from dataclasses import dataclass, field


@dataclass
class OutputValidationResult:
    """Output validation sonucu"""
    is_safe: bool
    quality_score: float  # 0-100
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    hallucination_signals: List[str] = field(default_factory=list)
    pii_detected: List[str] = field(default_factory=list)


class OutputValidator:
    """
    LLM output validation ve quality checking.

    Kontroller:
    1. Hallucination signals
    2. Unsafe content
    3. PII/secrets leakage
    4. Response quality
    """

    # Hallucination indicators
    HALLUCINATION_PATTERNS = [
        r"I('m| am) not (sure|certain|confident)",
        r"I (don't|do not) (know|have)",
        r"(probably|maybe|perhaps|might be)",
        r"(could|may|might) be",
        r"I (think|believe|guess)",
        r"(uncertain|unclear|ambiguous)",
        r"(fake|fictional|made[- ]up)",
        r"CIS[_-]FAKE",  # Uydurma referanslar
        r"NIST[_-]XXX",
        r"RFC[_-]9999",
    ]

    # Unsafe content patterns
    UNSAFE_PATTERNS = [
        r"rm\s+-rf\s+/",  # Dangerous commands
        r"dd\s+if=/dev/zero",
        r":(){ :|:& };:",  # Fork bomb
        r"sudo\s+chmod\s+777\s+/",
        r"disable.*firewall",
        r"turn\s+off.*security",
        r"(kapat|devre dışı|disable).*firewall",
        r"(remove|kaldır).*ufw",
        r"ufw\s+disable",
        r"systemctl\s+(stop|disable).*(firewall|security)",
    ]

    # PII patterns
    PII_PATTERNS = [
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
        r"\b\d{16}\b",  # Credit card
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
        r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",  # IP address
        r"-----BEGIN [A-Z ]+ PRIVATE KEY-----",  # Private key
    ]

    # Secret patterns
    SECRET_PATTERNS = [
        r"api[_-]?key['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9]{20,}",
        r"password['\"]?\s*[:=]\s*['\"]?[^\s'\"]+",
        r"secret['\"]?\s*[:=]\s*['\"]?[^\s'\"]+",
        r"token['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9]{20,}",
        r"sk-[a-zA-Z0-9]{20,}",  # OpenAI API key
        r"gsk_[a-zA-Z0-9]{20,}",  # Groq API key
    ]

    def __init__(self, strict_mode: bool = False):
        """
        Args:
            strict_mode: Katı mod (düşük quality score'da da reject)
        """
        self.strict_mode = strict_mode

        # Compile regexes
        self.hallucination_regex = re.compile(
            '|'.join(self.HALLUCINATION_PATTERNS),
            re.IGNORECASE
        )
        self.unsafe_regex = re.compile(
            '|'.join(self.UNSAFE_PATTERNS),
            re.IGNORECASE
        )
        self.pii_regex = re.compile(
            '|'.join(self.PII_PATTERNS)
        )
        self.secret_regex = re.compile(
            '|'.join(self.SECRET_PATTERNS),
            re.IGNORECASE
        )

    def validate(self, response: str, context: str = "") -> OutputValidationResult:
        """
        LLM output'unu validate et.

        Args:
            response: LLM yanıtı
            context: Request context (opsiyonel)

        Returns:
            OutputValidationResult
        """
        issues = []
        warnings = []
        hallucination_signals = []
        pii_detected = []

        # 1. Empty response check
        if not response or not response.strip():
            issues.append("Empty response from LLM")
            return OutputValidationResult(
                is_safe=False,
                quality_score=0.0,
                issues=issues
            )

        # 2. Hallucination detection
        halluc_matches = self.hallucination_regex.findall(response)
        if halluc_matches:
            hallucination_signals.extend(halluc_matches[:3])  # Max 3
            warnings.append(f"Possible hallucination signals: {len(halluc_matches)}")

        # 3. Unsafe content detection
        unsafe_matches = self.unsafe_regex.findall(response)
        if unsafe_matches:
            issues.append(f"Unsafe content detected: {unsafe_matches[0]}")

        # 4. PII detection
        pii_matches = self.pii_regex.findall(response)
        if pii_matches:
            pii_detected.extend(pii_matches[:3])
            warnings.append(f"PII detected: {len(pii_matches)} instances")

        # 5. Secret detection
        secret_matches = self.secret_regex.findall(response)
        if secret_matches:
            issues.append(f"Potential secret/credential detected")
            pii_detected.extend(["[SECRET_REDACTED]"] * len(secret_matches))

        # 6. Quality scoring
        quality_score = self._calculate_quality_score(
            response,
            hallucination_signals,
            unsafe_matches,
            pii_matches,
            secret_matches
        )

        # 7. Safety decision
        is_safe = len(issues) == 0 and (quality_score >= 50 or not self.strict_mode)

        return OutputValidationResult(
            is_safe=is_safe,
            quality_score=quality_score,
            issues=issues,
            warnings=warnings,
            hallucination_signals=hallucination_signals,
            pii_detected=pii_detected
        )

    def _calculate_quality_score(
        self,
        response: str,
        hallucination_signals: List[str],
        unsafe_matches: List[str],
        pii_matches: List[str],
        secret_matches: List[str]
    ) -> float:
        """
        Response quality score hesapla (0-100).

        Criteria:
        - Length appropriateness
        - No hallucination signals
        - No unsafe content
        - No PII/secrets
        - Structure quality
        """
        score = 100.0

        # Length penalty
        if len(response) < 20:
            score -= 30  # Too short
        elif len(response) > 5000:
            score -= 10  # Unnecessarily long

        # Hallucination penalty
        score -= min(len(hallucination_signals) * 10, 40)

        # Unsafe content penalty (severe)
        if unsafe_matches:
            score -= 50

        # PII penalty
        score -= min(len(pii_matches) * 5, 20)

        # Secret penalty (critical)
        if secret_matches:
            score -= 50

        # Structure bonus
        if "```" in response:  # Has code blocks
            score += 5

        if any(marker in response for marker in ["1.", "2.", "3.", "-", "*"]):
            score += 5  # Has lists/steps

        return max(0.0, min(100.0, score))


# Global instance
_validator = OutputValidator(strict_mode=False)


def validate_output(response: str, context: str = "", strict: bool = False) -> OutputValidationResult:
    """
    Convenience function for output validation.

    Args:
        response: LLM response
        context: Request context
        strict: Enable strict mode

    Returns:
        OutputValidationResult
    """
    if strict:
        validator = OutputValidator(strict_mode=True)
        return validator.validate(response, context)

    return _validator.validate(response, context)


# ─────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("="*70)
    print("OUTPUT VALIDATOR - TEST")
    print("="*70)

    test_cases = [
        # Good responses
        ("""SSH hardening için şu adımları izleyin:
1. Port değiştirin: /etc/ssh/sshd_config'de Port 22 -> 2222
2. Root login'i devre dışı bırakın: PermitRootLogin no
3. Key-based authentication kullanın
4. Fail2ban kurun: sudo apt install fail2ban

Referans: CIS Benchmark Ubuntu 22.04 Section 5.2""", True),

        # Hallucination signals
        ("""I'm not sure about this, but I think SSH port might be changed in /etc/ssh/sshd_config.
Maybe you could try changing Port 22 to something else, probably 2222 would work.""", True),

        # Unsafe content
        ("""SSH'yi durdurmak için: sudo systemctl stop ssh
Tüm güvenlik duvarını kapatın: sudo ufw disable
Firewall'u tamamen kaldırın: sudo apt remove ufw""", False),

        # PII detection
        ("""Yardımcı olmak için API key'inize ihtiyacım var.
Lütfen bu key'i kullanın: sk-1234567890abcdefghij
Email: user@example.com""", False),

        # Empty response
        ("", False),

        # Too short
        ("Evet", True),  # Low score but safe
    ]

    validator = OutputValidator(strict_mode=False)

    for i, (response, should_be_safe) in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i} ---")
        print(f"Response: {response[:80]}...")

        result = validator.validate(response)

        status = "PASS" if result.is_safe == should_be_safe else "FAIL"
        safety = "SAFE" if result.is_safe else "UNSAFE"

        print(f"[{status}] [{safety}] Quality: {result.quality_score:.1f}/100")

        if result.issues:
            print(f"  Issues: {result.issues}")

        if result.warnings:
            print(f"  Warnings: {result.warnings}")

        if result.hallucination_signals:
            print(f"  Hallucination signals: {result.hallucination_signals}")

        if result.pii_detected:
            print(f"  PII detected: {result.pii_detected}")

    print("\n" + "="*70)
    print("TEST COMPLETED")
    print("="*70)
