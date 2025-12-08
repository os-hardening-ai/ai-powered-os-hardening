# layers/info_pipeline.py
"""
Layer 3B: Info Pipeline (Smart RAG + Complexity Routing)

Purpose:
- Handle information queries with adaptive complexity routing
- Smart RAG triggering based on query type
- Complexity-based model selection (simple/medium/complex)

Based on:
- REVISED_ROUTE_ARCHITECTURE.md - Layer 3B specification
- Existing pipeline_optimized.py complexity routing
"""

from __future__ import annotations
from typing import Callable, Optional
from dataclasses import dataclass
from datetime import datetime

from ..context import RequestContext, SafetyResult
from ..utils.question_classifier import classify_question
from ..prompts.simple_prompts import get_prompt_for_complexity
from ..prompts.cot_prompts import CoTSecurityAnalyzer
from ..config import CONFIG

# Type alias
LLMCallable = Callable[[str], str]


@dataclass
class InfoQueryResult:
    """Info pipeline result"""
    answer: str
    complexity: str  # simple/medium/complex
    used_rag: bool
    rag_chunks: int = 0
    model_used: str = "unknown"
    response_time_s: float = 0.0
    estimated_cost: float = 0.0
    rag_sources: list = None  # RAG source metadata

    def __post_init__(self):
        if self.rag_sources is None:
            self.rag_sources = []


class InfoPipeline:
    """
    Layer 3B: Info Pipeline Handler

    Design:
    - Adaptive complexity routing (simple → medium → complex)
    - Smart RAG triggering:
      - SKIP RAG: Generic definitions LLM already knows
      - USE RAG: Specific OS/security config questions
    - Model selection:
      - Simple: Small model (Groq Llama 8B - FREE)
      - Medium: Medium model (GPT-4o-mini)
      - Complex: Large model + CoT (GPT-4o)

    Integration:
    - Called after Layer 2 identifies "info_request" intent
    - Uses parameter inference for metadata
    - Returns structured answer
    """

    def __init__(
        self,
        llm_small: LLMCallable,
        llm_large: LLMCallable,
        rag_builder: Optional[Callable] = None,
        debug: bool = False,
    ):
        """
        Args:
            llm_small: Small/fast model callable
            llm_large: Large/powerful model callable
            rag_builder: RAG context builder (optional)
            debug: Enable debug logging
        """
        self.llm_small = llm_small
        self.llm_large = llm_large
        self.rag_builder = rag_builder
        self.debug = debug

        # CoT analyzer for complex queries
        self.cot_analyzer = CoTSecurityAnalyzer(use_few_shot=True)

        self.stats = {
            "total_queries": 0,
            "simple_count": 0,
            "medium_count": 0,
            "complex_count": 0,
            "rag_used_count": 0,
            "rag_skipped_count": 0,
            "total_cost": 0.0,
        }

    def handle(self, ctx: RequestContext) -> InfoQueryResult:
        """
        Handle information query

        Args:
            ctx: Request context

        Returns:
            InfoQueryResult with answer

        Decision Logic:
        1. Classify complexity (simple/medium/complex)
        2. Decide RAG usage (skip generic, use specific)
        3. Route to appropriate path
        4. Return structured result
        """
        start_time = datetime.now()

        # Classify complexity
        complexity = classify_question(ctx.user_question)

        if self.debug:
            print(f"[InfoPipeline] Complexity: {complexity}")

        # Smart RAG decision
        use_rag = self._should_use_rag(ctx.user_question, complexity)

        if self.debug:
            print(f"[InfoPipeline] RAG usage: {use_rag}")

        # RAG retrieval (if needed)
        rag_chunks = 0
        rag_sources = []
        if use_rag and self.rag_builder:
            try:
                # Get formatted context for LLM
                rag_context = self.rag_builder.retrieve_context(ctx.user_question)

                # Get raw results for metadata
                raw_results = self.rag_builder.retrieve_raw(ctx.user_question)

                if rag_context:
                    ctx.retrieved_context = rag_context
                    rag_chunks = len(rag_context.split("\n\n")) if rag_context else 0
                    self.stats["rag_used_count"] += 1

                    # Extract source metadata
                    for result in raw_results:
                        metadata = result.get("metadata", {})
                        rag_sources.append({
                            "score": result.get("score", 0.0),
                            "source": metadata.get("source", "CIS Benchmark"),
                            "section": metadata.get("section", "N/A"),
                            "text_preview": result.get("text", "")[:200] + "..."  # First 200 chars
                        })

                    if self.debug:
                        print(f"[InfoPipeline] RAG retrieved {rag_chunks} chunks")
                        print(f"[InfoPipeline] RAG sources: {len(rag_sources)}")
            except Exception as e:
                if self.debug:
                    print(f"[InfoPipeline] RAG failed: {e}")
        else:
            self.stats["rag_skipped_count"] += 1

        # Route based on complexity
        if complexity == "simple":
            result = self._simple_path(ctx)
            self.stats["simple_count"] += 1
            model_used = "small"
            estimated_cost = 0.0002
        elif complexity == "medium":
            result = self._medium_path(ctx)
            self.stats["medium_count"] += 1
            model_used = "large"
            estimated_cost = 0.0005
        else:  # complex
            result = self._complex_path(ctx)
            self.stats["complex_count"] += 1
            model_used = "large+CoT"
            estimated_cost = 0.0015

        # Update stats
        self.stats["total_queries"] += 1
        self.stats["total_cost"] += estimated_cost

        # Calculate response time
        response_time = (datetime.now() - start_time).total_seconds()

        return InfoQueryResult(
            answer=result,
            complexity=complexity,
            used_rag=use_rag and rag_chunks > 0,
            rag_chunks=rag_chunks,
            model_used=model_used,
            response_time_s=response_time,
            estimated_cost=estimated_cost,
            rag_sources=rag_sources,
        )

    def _should_use_rag(self, question: str, complexity: str) -> bool:
        """
        Smart RAG triggering decision

        Strategy:
        - SKIP RAG: Generic questions LLM knows (e.g., "Firewall nedir?")
        - USE RAG: Specific OS/config questions (e.g., "Ubuntu 22.04 SSH hardening")

        Args:
            question: User question
            complexity: Question complexity (simple/medium/complex)

        Returns:
            True if RAG should be used
        """
        q_lower = question.lower()

        # Generic question patterns (NO RAG)
        generic_patterns = [
            "nedir", "ne demek", "nasıl çalışır", "ne işe yarar",
            "what is", "what does", "explain",
        ]

        # Specific question indicators (USE RAG)
        specific_indicators = [
            # OS-specific
            "ubuntu", "centos", "debian", "windows", "rhel",
            # Version-specific
            "22.04", "24.04", "20.04", "server 2022",
            # Specific configs
            "sshd_config", "firewalld", "ufw", "selinux", "apparmor",
            # CIS benchmark queries
            "cis benchmark", "cis control", "benchmark",
        ]

        # Check for generic patterns
        has_generic_pattern = any(pattern in q_lower for pattern in generic_patterns)

        # Check for specific indicators
        has_specific_indicator = any(indicator in q_lower for indicator in specific_indicators)

        # Decision logic
        if has_specific_indicator:
            return True  # Always use RAG for specific queries

        if has_generic_pattern and not has_specific_indicator:
            return False  # Skip RAG for pure generic definitions

        # Medium/complex queries without explicit generic pattern → use RAG
        if complexity in ["medium", "complex"]:
            return True

        # Default: Simple queries without specific indicators → skip RAG
        return False

    def _simple_path(self, ctx: RequestContext) -> str:
        """
        Simple path: Small model + minimal prompt

        Args:
            ctx: Request context

        Returns:
            Answer string
        """
        if self.debug:
            print("[InfoPipeline] Simple path: small model")

        # Minimal prompt
        prompt = get_prompt_for_complexity(ctx, "simple")

        # LLM call
        response = self.llm_small(prompt)

        return response.strip()

    def _medium_path(self, ctx: RequestContext) -> str:
        """
        Medium path: Large model + medium prompt

        Args:
            ctx: Request context

        Returns:
            Answer string
        """
        if self.debug:
            print("[InfoPipeline] Medium path: large model")

        # Medium prompt
        prompt = get_prompt_for_complexity(ctx, "medium")

        # LLM call
        response = self.llm_large(prompt)

        return response.strip()

    def _complex_path(self, ctx: RequestContext) -> str:
        """
        Complex path: Large model + full CoT reasoning

        Args:
            ctx: Request context

        Returns:
            Answer string
        """
        if self.debug:
            print("[InfoPipeline] Complex path: CoT reasoning")

        # CoT prompt
        cot_prompt = self.cot_analyzer.build_cot_prompt(ctx)

        # LLM call
        raw_response = self.llm_large(cot_prompt)

        # Parse CoT response
        ctx = self.cot_analyzer.parse_cot_response(raw_response, ctx)

        # Return final answer
        return ctx.final_answer if ctx.final_answer else raw_response

    def get_stats(self) -> dict:
        """Get usage statistics"""
        total = self.stats["total_queries"]
        if total == 0:
            return self.stats

        return {
            **self.stats,
            "simple_rate": self.stats["simple_count"] / total,
            "medium_rate": self.stats["medium_count"] / total,
            "complex_rate": self.stats["complex_count"] / total,
            "rag_usage_rate": self.stats["rag_used_count"] / total,
            "avg_cost_per_query": self.stats["total_cost"] / total,
        }


# Convenience function
def handle_info_query(
    question: str,
    llm_small: LLMCallable,
    llm_large: LLMCallable,
    rag_builder: Optional[Callable] = None,
    context: Optional[RequestContext] = None,
    debug: bool = False,
) -> InfoQueryResult:
    """
    Quick info query handler

    Usage:
        result = handle_info_query(
            "Ubuntu 22.04 SSH hardening nasıl yapılır?",
            llm_small=groq_llm,
            llm_large=openai_llm,
            rag_builder=rag_builder
        )
        print(result.answer)
    """
    from ..context import RequestContext

    if context is None:
        context = RequestContext(user_question=question)

    pipeline = InfoPipeline(
        llm_small=llm_small,
        llm_large=llm_large,
        rag_builder=rag_builder,
        debug=debug,
    )

    return pipeline.handle(context)


# ─────────────────────────────────────────────
# Test & Examples
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Mock LLMs for testing
    def mock_llm_small(prompt: str) -> str:
        return "This is a SMALL model response (fast, cheap)."

    def mock_llm_large(prompt: str) -> str:
        return "This is a LARGE model response (powerful, expensive)."

    # Mock RAG builder
    class MockRAGBuilder:
        def retrieve_context(self, question: str) -> Optional[str]:
            if "ubuntu" in question.lower() or "ssh" in question.lower():
                return "CIS Benchmark context:\n\n- SSH hardening steps...\n- Configure sshd_config..."
            return None

    print("="*70)
    print("INFO PIPELINE - TEST")
    print("="*70)

    pipeline = InfoPipeline(
        llm_small=mock_llm_small,
        llm_large=mock_llm_large,
        rag_builder=MockRAGBuilder(),
        debug=True,
    )

    test_cases = [
        # Generic (simple, no RAG)
        ("Firewall nedir?", "simple", False),

        # Specific (medium, with RAG)
        ("Ubuntu 22.04'te SSH hardening nasıl yapılır?", "medium", True),

        # Complex (complex, with RAG)
        ("Zero Trust maturity level 3 için SSH, RDP ve firewall hardening scriptleri yaz", "complex", True),

        # Generic educational (simple, no RAG)
        ("SELinux nasıl çalışır?", "simple", False),
    ]

    for question, expected_complexity, expected_rag in test_cases:
        print(f"\n{'─'*70}")
        print(f"Question: {question}")
        print(f"Expected: complexity={expected_complexity}, RAG={expected_rag}")

        from ..context import RequestContext
        ctx = RequestContext(user_question=question)

        result = pipeline.handle(ctx)

        print(f"\n✅ RESULT:")
        print(f"  Complexity: {result.complexity}")
        print(f"  Model: {result.model_used}")
        print(f"  RAG Used: {result.used_rag} (chunks: {result.rag_chunks})")
        print(f"  Response Time: {result.response_time_s:.2f}s")
        print(f"  Cost: ${result.estimated_cost:.4f}")
        print(f"  Answer: {result.answer[:80]}...")

        # Validation
        complexity_ok = result.complexity == expected_complexity
        rag_ok = result.used_rag == expected_rag

        status = "✅ PASS" if (complexity_ok and rag_ok) else "⚠️ PARTIAL"
        print(f"\nValidation: {status}")

    print("\n" + "="*70)
    print("STATISTICS")
    print("="*70)
    stats = pipeline.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)
