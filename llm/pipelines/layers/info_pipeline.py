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
import logging
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from llm.core.context import RequestContext, SafetyResult
from llm.utils.question_classifier import classify_question
from llm.prompts.simple_prompts import get_prompt_for_complexity
from llm.prompts.cot_prompts import CoTSecurityAnalyzer
from llm.core.config import CONFIG

# Type alias
LLMCallable = Callable[[str], str]

_logger = logging.getLogger(__name__)



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
    rag_sources: list = field(default_factory=list)
    verification_confidence: float | None = None  # None = not checked
    unsupported_claims: list = field(default_factory=list)  # bağlamca DESTEKLENMEYEN iddialar
    timing: Dict[str, float] = field(default_factory=dict)  # per-step breakdown (seconds)


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
        query_planner=None,
        claim_verifier=None,
        debug: bool = False,
    ):
        """
        Args:
            llm_small:      Small/fast model callable
            llm_large:      Large/powerful model callable
            rag_builder:    RAG context builder (optional)
            query_planner:  QueryPlanner instance (optional — expands queries)
            claim_verifier: ClaimVerifier instance (optional — halüsinasyon kontrolü)
            debug:          Enable debug logging
        """
        self.llm_small = llm_small
        self.llm_large = llm_large
        self.rag_builder = rag_builder
        self.query_planner = query_planner
        self.claim_verifier = claim_verifier
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
        _t: dict[str, float] = {}  # per-step timing accumulator

        # Classify complexity
        complexity = classify_question(ctx.user_question)

        if self.debug:
            print(f"[InfoPipeline] Complexity: {complexity}")

        # RAG kararı iki koşula bağlı:
        #  1) rag_builder mevcut (API'dan use_rag=True geldi), VE
        #  2) _should_use_rag akıllı tetikleme: jenerik tanım sorularında
        #     ("firewall nedir") RAG'i ATLA → gereksiz embedding + Qdrant çağrısı yok,
        #     daha hızlı + daha az kota tüketimi. Spesifik/zor sorularda RAG çalışır.
        use_rag = self.rag_builder is not None and self._should_use_rag(
            ctx.user_question, complexity
        )

        if self.debug:
            print(f"[InfoPipeline] RAG usage: {use_rag} (builder={self.rag_builder is not None})")

        # RAG retrieval (if needed)
        rag_chunks = 0
        rag_sources = []
        raw_results_for_verify: List[dict] = []
        _logger.debug("[InfoPipeline] use_rag=%s, rag_builder=%s", use_rag, "SET" if self.rag_builder else "NONE")
        if use_rag and self.rag_builder:
            try:
                # Query planning: expand query before retrieval
                if self.query_planner is not None and complexity != "simple":
                    try:
                        _t0 = datetime.now()
                        plan = self.query_planner.plan(ctx.user_question)
                        _t["query_planner_s"] = (datetime.now() - _t0).total_seconds()
                        all_queries = plan.all_queries()
                        _logger.debug(
                            "[InfoPipeline] QueryPlanner: %d queries for '%s'",
                            len(all_queries),
                            ctx.user_question[:50],
                        )
                        # Use retrieve_multi if available, else fall back to balanced
                        _t0 = datetime.now()
                        if hasattr(self.rag_builder, "retrieve_multi"):
                            rag_context, raw_results = self.rag_builder.retrieve_multi(
                                queries=all_queries,
                                original_query=ctx.user_question,
                            )
                        else:
                            rag_context, raw_results = self.rag_builder.retrieve_balanced(
                                ctx.user_question
                            )
                        _t["rag_retrieve_s"] = (datetime.now() - _t0).total_seconds()
                    except Exception as qp_exc:
                        _logger.warning("[InfoPipeline] QueryPlanner failed, using balanced: %s", qp_exc)
                        _t0 = datetime.now()
                        rag_context, raw_results = self.rag_builder.retrieve_balanced(ctx.user_question)
                        _t["rag_retrieve_s"] = (datetime.now() - _t0).total_seconds()
                else:
                    # Standard balanced retrieval: YAML rules + PDF benchmarks
                    _t0 = datetime.now()
                    rag_context, raw_results = self.rag_builder.retrieve_balanced(ctx.user_question)
                    _t["rag_retrieve_s"] = (datetime.now() - _t0).total_seconds()

                if rag_context and raw_results:
                    ctx.retrieved_context = rag_context
                    rag_chunks = len(raw_results)
                    raw_results_for_verify = raw_results
                    self.stats["rag_used_count"] += 1

                    # Extract source metadata
                    for result in raw_results:
                        metadata = result.get("metadata", {})
                        section_id = metadata.get("section_id") or metadata.get("section") or ""
                        section_title = metadata.get("section_title") or metadata.get("title") or ""
                        if section_id and section_title and section_id != section_title:
                            section = f"{section_id} - {section_title}"
                        elif section_id:
                            section = section_id
                        elif section_title:
                            section = section_title
                        else:
                            section = "N/A"
                        chunk_text = result.get("text", "")
                        rag_sources.append({
                            "score": result.get("score", 0.0),
                            "source": metadata.get("benchmark_product") or metadata.get("source_id") or "CIS Benchmark",
                            "section": section,
                            "text": chunk_text[:500] if chunk_text else None,
                        })

                    _logger.info("[InfoPipeline] RAG OK — %d chunks, %d sources", rag_chunks, len(rag_sources))
                else:
                    _logger.info(
                        "[InfoPipeline] RAG returned empty — context=%s, results=%d",
                        bool(rag_context), len(raw_results)
                    )
            except Exception as e:
                _logger.error("[InfoPipeline] RAG ERROR: %s", e)
        else:
            self.stats["rag_skipped_count"] += 1
            _logger.debug("[InfoPipeline] RAG skipped")

        # RAG kaliteli context getirdiyse simple→medium yükselt
        if complexity == "simple" and rag_chunks >= 2:
            complexity = "medium"
            _logger.debug("[InfoPipeline] Upgraded simple→medium (rag_chunks=%d)", rag_chunks)

        # Route based on complexity — time the LLM generation separately
        _t0 = datetime.now()
        try:
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
        except Exception as gen_exc:
            _logger.error("[InfoPipeline] LLM generation failed: %s", gen_exc)
            result = (
                "Şu anda yanıt üretilemedi — LLM sağlayıcısı geçici olarak kullanılamıyor. "
                "Lütfen birkaç saniye bekleyip tekrar deneyin."
            )
            model_used = "error"
            estimated_cost = 0.0
        _t["llm_gen_s"] = (datetime.now() - _t0).total_seconds()

        # Claim verification (only when RAG was used — no context = no verification)
        verification_confidence: float | None = None
        unsupported_claims: list = []
        if self.claim_verifier is not None and raw_results_for_verify:
            try:
                _t0 = datetime.now()
                vr = self.claim_verifier.verify(result, raw_results_for_verify)
                _t["claim_verify_s"] = (datetime.now() - _t0).total_seconds()
                verification_confidence = vr.confidence
                unsupported_claims = list(vr.unsupported)
                if not vr.is_valid:
                    _logger.warning(
                        "[InfoPipeline] Low verification confidence %.2f — unsupported: %s",
                        vr.confidence,
                        vr.unsupported[:2],
                    )
                    result += (
                        f"\n\n> ⚠️ **Güven skoru:** %{vr.confidence * 100:.0f} — "
                        "bazı ifadeler kaynak dokümanlarla tam örtüşmüyor, "
                        "lütfen kritik komutları resmi CIS Benchmark'tan doğrulayın."
                    )
            except Exception as cv_exc:
                _logger.warning("[InfoPipeline] ClaimVerifier failed: %s", cv_exc)

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
            verification_confidence=verification_confidence,
            unsupported_claims=unsupported_claims,
            timing=_t,
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
    from llm.core.context import RequestContext

    if context is None:
        context = RequestContext(user_question=question)

    pipeline = InfoPipeline(
        llm_small=llm_small,
        llm_large=llm_large,
        rag_builder=rag_builder,
        debug=debug,
    )

    return pipeline.handle(context)
