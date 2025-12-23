# layers/safety_classifier.py
"""
Layer 1: Safety Classification

LLM Security Best Practice 2025: Input validation as first defense layer

Purpose:
- Detect malicious/offensive queries before processing
- Protect against prompt injection
- Classify adversarial inputs
- Provide threat intelligence

Based on research:
- https://www.oligo.security/academy/llm-security-in-2025-risks-examples-and-best-practices
- https://www.confident-ai.com/blog/the-comprehensive-guide-to-llm-security
"""

from __future__ import annotations
from typing import Literal, Optional, Callable
from dataclasses import dataclass
import json
import re


SafetyCategory = Literal[
    "safe_defensive",      # Legitimate security hardening
    "safe_educational",    # Learning/research query
    "ambiguous",           # Unclear intent
    "unsafe_offensive",    # Attack/exploit development
    "unsafe_spam"          # Spam/abuse attempt
]


@dataclass
class SafetyResult:
    """Safety classification result"""
    category: SafetyCategory
    confidence: float  # 0.0 - 1.0
    reason: str
    is_safe: bool = True  # Convenience flag

    def __post_init__(self):
        self.is_safe = self.category in ["safe_defensive", "safe_educational", "ambiguous"]


class SafetyClassifier:
    """
    Layer 1: Ultra-fast safety classification using LLM

    Design:
    - Single-shot classification (no multi-turn)
    - Structured JSON output
    - Ultra-fast model (Groq Llama 8B - free)
    - ~200ms latency, $0 cost

    Decision Logic:
    - safe_defensive (>0.8) → PROCEED
    - safe_educational (>0.7) → PROCEED
    - ambiguous → WARN + PROCEED with caution
    - unsafe_offensive (>0.6) → REJECT
    - unsafe_spam → REJECT + rate limit
    """

    CLASSIFICATION_PROMPT = """You are a security AI assistant. Classify this question as safe or unsafe.

Question: "{question}"

Categories:
1. safe_defensive: Legitimate security hardening, system protection, defensive measures
   Examples: "SSH hardening best practices", "How to configure firewall", "Enable 2FA"

2. safe_educational: Learning about security concepts, research, understanding risks
   Examples: "What is buffer overflow?", "How does SQL injection work?", "Explain zero trust"

3. ambiguous: Unclear intent, needs clarification
   Examples: "How to bypass?", "Security tricks", "Can you help with..."

4. unsafe_offensive: Attack development, exploit creation, malicious hacking
   Examples: "How to exploit SSH?", "Bypass firewall detection", "Crack passwords"

5. unsafe_spam: Spam, irrelevant, abusive content
   Examples: "Buy cheap meds", "Click here", Random gibberish

Output ONLY valid JSON (no markdown, no explanations):
{{"category": "safe_defensive|safe_educational|ambiguous|unsafe_offensive|unsafe_spam", "confidence": 0.XX, "reason": "brief explanation"}}

Classification:"""

    def __init__(self, llm_ultra_fast: Callable[[str], str], debug: bool = False):
        """
        Args:
            llm_ultra_fast: Ultra-fast LLM callable (Groq Llama 8B recommended)
            debug: Enable debug logging
        """
        self.llm = llm_ultra_fast
        self.debug = debug
        self.stats = {
            "total_classifications": 0,
            "safe_count": 0,
            "unsafe_count": 0,
            "ambiguous_count": 0,
        }

    def classify(self, question: str) -> SafetyResult:
        """
        Classify question safety

        Args:
            question: User input

        Returns:
            SafetyResult with category, confidence, reason

        Raises:
            ValueError: If LLM response cannot be parsed
        """
        if not question or not question.strip():
            return SafetyResult(
                category="unsafe_spam",
                confidence=1.0,
                reason="Empty question"
            )

        # Build prompt
        prompt = self.CLASSIFICATION_PROMPT.format(question=question)

        try:
            # LLM call (ultra-fast model)
            response = self.llm(prompt)

            if self.debug:
                print(f"[SafetyClassifier] LLM response: {response}")

            # Parse JSON response
            result = self._parse_response(response)

            # Update stats
            self.stats["total_classifications"] += 1
            if result.is_safe:
                self.stats["safe_count"] += 1
            elif result.category == "ambiguous":
                self.stats["ambiguous_count"] += 1
            else:
                self.stats["unsafe_count"] += 1

            return result

        except Exception as e:
            if self.debug:
                print(f"[SafetyClassifier] Error: {e}")

            # Fallback: Default to safe but ambiguous
            return SafetyResult(
                category="ambiguous",
                confidence=0.5,
                reason=f"Classification failed: {str(e)}"
            )

    def _parse_response(self, response: str) -> SafetyResult:
        """
        Parse LLM JSON response

        Handles:
        - Clean JSON
        - JSON wrapped in markdown ```json
        - Malformed JSON (extract with regex)
        """
        # Clean markdown wrapper
        response = response.strip()
        if response.startswith("```json"):
            response = response.replace("```json", "").replace("```", "").strip()
        elif response.startswith("```"):
            response = response.replace("```", "").strip()

        try:
            # Parse JSON
            data = json.loads(response)

            category = data.get("category", "ambiguous")
            confidence = float(data.get("confidence", 0.5))
            reason = data.get("reason", "No reason provided")

            # Validate category
            valid_categories = ["safe_defensive", "safe_educational", "ambiguous", "unsafe_offensive", "unsafe_spam"]
            if category not in valid_categories:
                category = "ambiguous"
                confidence = 0.5
                reason = f"Invalid category: {category}"

            return SafetyResult(
                category=category,  # type: ignore
                confidence=confidence,
                reason=reason
            )

        except json.JSONDecodeError:
            # Fallback: Regex extraction
            if self.debug:
                print(f"[SafetyClassifier] JSON parse failed, using regex fallback")

            category_match = re.search(r'"category":\s*"(\w+)"', response)
            confidence_match = re.search(r'"confidence":\s*([\d.]+)', response)

            category = category_match.group(1) if category_match else "ambiguous"
            confidence = float(confidence_match.group(1)) if confidence_match else 0.5

            return SafetyResult(
                category=category,  # type: ignore
                confidence=confidence,
                reason="Parsed with regex fallback"
            )

    def get_stats(self) -> dict:
        """Get classification statistics"""
        total = self.stats["total_classifications"]
        if total == 0:
            return self.stats

        return {
            **self.stats,
            "safe_rate": self.stats["safe_count"] / total,
            "unsafe_rate": self.stats["unsafe_count"] / total,
            "ambiguous_rate": self.stats["ambiguous_count"] / total,
        }


# Convenience function
def classify_safety(
    question: str,
    llm_ultra_fast: Callable[[str], str],
    debug: bool = False
) -> SafetyResult:
    """
    Quick safety classification

    Usage:
        result = classify_safety("How to hack SSH?", llm_ultra_fast)
        if not result.is_safe:
            return "Unsafe query rejected"
    """
    classifier = SafetyClassifier(llm_ultra_fast, debug=debug)
    return classifier.classify(question)


# ─────────────────────────────────────────────
# Test & Examples
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Mock LLM for testing
    def mock_llm(prompt: str) -> str:
        """Mock LLM that returns classification based on keywords"""
        question_lower = prompt.lower()

        if any(kw in question_lower for kw in ["hack", "exploit", "crack", "bypass"]):
            return '{"category": "unsafe_offensive", "confidence": 0.9, "reason": "Contains attack keywords"}'

        if any(kw in question_lower for kw in ["hardening", "secure", "protect", "firewall"]):
            return '{"category": "safe_defensive", "confidence": 0.95, "reason": "Legitimate security hardening"}'

        if any(kw in question_lower for kw in ["what is", "how does", "explain"]):
            return '{"category": "safe_educational", "confidence": 0.85, "reason": "Educational query"}'

        return '{"category": "ambiguous", "confidence": 0.6, "reason": "Unclear intent"}'

    # Test cases
    test_cases = [
        ("SSH hardening best practices", "safe_defensive"),
        ("How to exploit SSH vulnerabilities", "unsafe_offensive"),
        ("What is SQL injection?", "safe_educational"),
        ("Security tricks", "ambiguous"),
        ("Buy cheap meds now!", "ambiguous"),  # Mock doesn't detect spam
        ("How to configure firewall on Ubuntu", "safe_defensive"),
        ("Bypass antivirus detection", "unsafe_offensive"),
    ]

    print("="*70)
    print("SAFETY CLASSIFIER - TEST")
    print("="*70)

    classifier = SafetyClassifier(mock_llm, debug=True)

    for question, expected_category in test_cases:
        print(f"\n{'─'*70}")
        print(f"Question: {question}")

        result = classifier.classify(question)

        print(f"\nResult:")
        print(f"  Category: {result.category}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Reason: {result.reason}")
        print(f"  Is Safe: {result.is_safe}")

        status = "✅" if result.category == expected_category else "❌"
        print(f"\n{status} Expected: {expected_category}, Got: {result.category}")

    print("\n" + "="*70)
    print("STATISTICS")
    print("="*70)
    stats = classifier.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
