# layers/pattern_responder.py
"""
Layer 3A: Pattern Responder (Smalltalk Handler)

Purpose:
- Handle smalltalk queries with pre-defined responses (NO LLM)
- Ultra-fast responses (<1ms)
- Zero cost ($0)
- Professional, consistent tone

Based on:
- REVISED_ROUTE_ARCHITECTURE.md - Layer 3A specification
- Reuses existing local_responder.py logic
"""

from __future__ import annotations
from typing import Optional
from dataclasses import dataclass

from llm.utils.local_responder import LocalResponder


@dataclass
class PatternResponse:
    """Pattern-based response result"""
    response: str
    category: str  # greeting, farewell, thanks, help, etc.
    matched_pattern: str
    response_time_ms: float = 0.0


class PatternResponderHandler:
    """
    Layer 3A: Pattern Responder Handler

    Design:
    - NO LLM calls (pure pattern matching)
    - <1ms latency, $0 cost
    - Handles smalltalk categories:
      - greeting
      - farewell
      - thanks
      - help
      - affirmation
      - security_definition (e.g., "CIS nedir?")
      - quick_command (e.g., "SSH port değiştir")

    Integration:
    - Called after Layer 2 (Intent Detector) identifies "smalltalk" intent
    - Returns pre-defined response immediately
    - No context, no parameters needed
    """

    def __init__(self, debug: bool = False):
        """
        Args:
            debug: Enable debug logging
        """
        self.debug = debug
        self.local_responder = LocalResponder()
        self.stats = {
            "total_responses": 0,
            "category_counts": {
                "greeting": 0,
                "farewell": 0,
                "thanks": 0,
                "help": 0,
                "affirmation": 0,
                "security_definition": 0,
                "quick_command": 0,
                "other": 0,
            }
        }

    def handle(self, question: str) -> Optional[PatternResponse]:
        """
        Handle smalltalk question with pattern matching

        Args:
            question: User input

        Returns:
            PatternResponse if matched, None if no pattern matches

        Examples:
            >>> handler = PatternResponderHandler()
            >>> result = handler.handle("merhaba")
            >>> result.response
            "Merhaba! Siber güvenlik konusunda size nasıl yardımcı olabilirim?"

            >>> result = handler.handle("CIS nedir?")
            >>> result.category
            "security_definition"
        """
        import time
        start_time = time.time()

        # Delegate to local_responder
        response_text = self.local_responder.check_and_respond(question)

        if not response_text:
            return None  # No pattern match, needs LLM

        # Infer category from response
        category = self._infer_category(question, response_text)

        # Update stats
        self.stats["total_responses"] += 1
        self.stats["category_counts"][category] += 1

        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000

        if self.debug:
            print(f"[PatternResponder] Matched category: {category}, time: {response_time_ms:.2f}ms")

        return PatternResponse(
            response=response_text,
            category=category,
            matched_pattern="local_responder",  # Generic for now
            response_time_ms=response_time_ms,
        )

    def _infer_category(self, question: str, response: str) -> str:
        """Infer smalltalk category from question and response"""
        q_lower = question.lower()

        # Simple heuristics
        greeting_keywords = ["merhaba", "selam", "hi", "hello", "günaydın"]
        farewell_keywords = ["görüşürüz", "hoşça kal", "bye", "güle güle"]
        thanks_keywords = ["teşekkür", "sağ ol", "thanks", "eyvallah"]
        help_keywords = ["soru", "yardım", "help", "nasıl çalış"]
        definition_keywords = ["nedir", "ne demek"]
        command_keywords = ["port", "restart", "durum", "kurulum"]

        if any(kw in q_lower for kw in greeting_keywords):
            return "greeting"
        elif any(kw in q_lower for kw in farewell_keywords):
            return "farewell"
        elif any(kw in q_lower for kw in thanks_keywords):
            return "thanks"
        elif any(kw in q_lower for kw in help_keywords):
            return "help"
        elif any(kw in q_lower for kw in definition_keywords):
            return "security_definition"
        elif any(kw in q_lower for kw in command_keywords):
            return "quick_command"
        elif q_lower in ["evet", "tamam", "ok", "okay", "peki"]:
            return "affirmation"
        else:
            return "other"

    def get_stats(self) -> dict:
        """Get usage statistics"""
        return {
            **self.stats,
            "local_responder_stats": self.local_responder.get_stats(),
        }


# Convenience function
def handle_pattern_response(question: str, debug: bool = False) -> Optional[PatternResponse]:
    """
    Quick pattern response handler

    Usage:
        result = handle_pattern_response("merhaba")
        if result:
            return result.response
        else:
            # Need LLM
            pass
    """
    handler = PatternResponderHandler(debug=debug)
    return handler.handle(question)


# ─────────────────────────────────────────────
# Test & Examples
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("="*70)
    print("PATTERN RESPONDER HANDLER - TEST")
    print("="*70)

    handler = PatternResponderHandler(debug=True)

    test_cases = [
        # Smalltalk - should match
        ("merhaba", True),
        ("selam", True),
        ("görüşürüz", True),
        ("teşekkür ederim", True),
        ("sağ ol", True),
        ("yardım lazım", True),
        ("CIS nedir?", True),
        ("SSH port nasıl değişir?", True),

        # Security questions - should NOT match (need LLM)
        ("Ubuntu 22.04'te SSH hardening nasıl yapılır?", False),
        ("Firewall kuralları nasıl optimize edilir?", False),
        ("Zero Trust maturity level 3 için hangi adımlar gerekli?", False),
    ]

    for question, should_match in test_cases:
        print(f"\n{'─'*70}")
        print(f"Question: {question}")
        print(f"Expected: {'MATCH' if should_match else 'NO MATCH'}")

        result = handler.handle(question)

        if result:
            print(f"\n✅ MATCHED")
            print(f"  Category: {result.category}")
            print(f"  Response: {result.response[:80]}...")
            print(f"  Time: {result.response_time_ms:.2f}ms")

            status = "✅ OK" if should_match else "❌ FALSE POSITIVE"
        else:
            print(f"\n❌ NO MATCH - LLM needed")
            status = "✅ OK" if not should_match else "❌ FALSE NEGATIVE"

        print(f"\nStatus: {status}")

    print("\n" + "="*70)
    print("STATISTICS")
    print("="*70)
    stats = handler.get_stats()
    print(f"Total responses: {stats['total_responses']}")
    print(f"\nCategory breakdown:")
    for category, count in stats['category_counts'].items():
        if count > 0:
            print(f"  {category}: {count}")

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)
