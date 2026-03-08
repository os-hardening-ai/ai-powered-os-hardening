# pipeline_v2.py
"""
4-Layer Security-First Pipeline (2025 Best Practices)

Architecture:
Layer 1: Safety Classification (LLM-based threat detection)
Layer 2: Intent Detection (Pattern-based routing)
Layer 3A: Pattern Responder (Smalltalk - NO LLM)
Layer 3B: Info Pipeline (Smart RAG + Complexity routing)
Layer 3C: Action Pipeline (Script generation with strict validation)

Based on:
- REVISED_ROUTE_ARCHITECTURE.md
- LLM Security Best Practices 2025
- Oligo Security & Confident AI guidelines

Performance:
- Security check: ~200ms (Groq Llama 8B - FREE)
- Smalltalk: <1ms ($0)
- Info queries: 1-3s ($0.0002-$0.0015)
- Scripts: 3-5s ($0.0025)
"""

from __future__ import annotations
from typing import Callable, Optional
from dataclasses import dataclass
from datetime import datetime

from llm.core.context import RequestContext
from llm.pipelines.layers.safety_classifier import SafetyClassifier, SafetyResult
from llm.pipelines.layers.hybrid_intent_detector import HybridIntentDetector, HybridIntent
from llm.pipelines.layers.pattern_responder import PatternResponderHandler, PatternResponse
from llm.pipelines.layers.info_pipeline import InfoPipeline, InfoQueryResult
from llm.pipelines.layers.action_pipeline import ActionPipeline, ActionQueryResult
from llm.core.config import CONFIG

# Type alias
LLMCallable = Callable[[str], str]


@dataclass
class PipelineResult:
    """Final pipeline result"""
    success: bool
    answer: str
    layer_path: str  # e.g., "1→2→3A" (safety→intent→pattern)
    safety: SafetyResult
    intent: HybridIntent
    total_time_s: float
    estimated_cost: float
    metadata: dict  # Additional info for debugging


class SecurePipelineV2:
    """
    4-Layer Security-First Pipeline

    Flow:
    User Input
        ↓
    [Layer 1: Safety Classification]  ← Groq Llama 8B (FREE, ~200ms)
        ↓
    Safe? YES → Continue
          NO  → REJECT (return safety warning)
        ↓
    [Layer 2: Intent Detection]  ← Pattern matching (NO LLM, <1ms)
        ↓
    Intent?
        ├── smalltalk → [Layer 3A: Pattern Responder] (NO LLM, <1ms)
        ├── info_request → [Layer 3B: Info Pipeline] (Smart RAG + Complexity routing)
        └── action_request → [Layer 3C: Action Pipeline] (CoT + Strict validation)
        ↓
    Final Answer

    Key Features:
    - Safety-first: ALL queries checked for threats
    - Zero-trust: No assumptions about input
    - Adaptive routing: Complexity-based model selection
    - Cost optimized: 35% queries = $0 (pattern responses)
    - Smart RAG: Only when needed, not for generic questions
    """

    def __init__(
        self,
        llm_ultra_fast: LLMCallable,  # For Layer 1 safety (Groq Llama 8B)
        llm_small: LLMCallable,  # For simple info queries
        llm_large: LLMCallable,  # For complex queries & scripts
        rag_builder: Optional[Callable] = None,
        debug: bool = False,
    ):
        """
        Args:
            llm_ultra_fast: Ultra-fast model for safety classification (Groq recommended)
            llm_small: Small model for simple queries (Groq/GPT-3.5)
            llm_large: Large model for complex queries (GPT-4o-mini/GPT-4o)
            rag_builder: RAG context builder (optional)
            debug: Enable debug logging
        """
        self.debug = debug

        # Layer 1: Safety Classification
        self.safety_classifier = SafetyClassifier(
            llm_ultra_fast=llm_ultra_fast,
            debug=debug
        )

        # Layer 2: Intent Detection
        self.intent_detector = HybridIntentDetector(use_ml=True, debug=debug)

        # Layer 3A: Pattern Responder
        self.pattern_handler = PatternResponderHandler(debug=debug)

        # Layer 3B: Info Pipeline
        self.info_pipeline = InfoPipeline(
            llm_small=llm_small,
            llm_large=llm_large,
            rag_builder=rag_builder,
            debug=debug,
        )

        # Layer 3C: Action Pipeline
        self.action_pipeline = ActionPipeline(
            llm_large=llm_large,
            rag_builder=rag_builder,
            debug=debug,
        )

        self.stats = {
            "total_queries": 0,
            "rejected_unsafe": 0,
            "pattern_responses": 0,  # Layer 3A
            "info_responses": 0,  # Layer 3B
            "action_responses": 0,  # Layer 3C
            "total_cost": 0.0,
        }

    def run(self, ctx: RequestContext) -> PipelineResult:
        """
        Run the 4-layer pipeline

        Args:
            ctx: Request context

        Returns:
            PipelineResult with final answer and metadata
        """
        start_time = datetime.now()

        if self.debug:
            print("="*70)
            print("4-LAYER SECURITY PIPELINE V2")
            print("="*70)
            print(f"Question: {ctx.user_question}")
            print("="*70)

        # ─────────────────────────────────────────────
        # LAYER 1: SAFETY CLASSIFICATION
        # ─────────────────────────────────────────────

        if self.debug:
            print("\n[Layer 1] Safety Classification...")

        safety_result = self.safety_classifier.classify(ctx.user_question)

        if self.debug:
            print(f"  Category: {safety_result.category}")
            print(f"  Confidence: {safety_result.confidence:.2f}")
            print(f"  Is Safe: {safety_result.is_safe}")

        # Check if unsafe
        if not safety_result.is_safe:
            if self.debug:
                print(f"  [REJECTED]: {safety_result.reason}")

            self.stats["total_queries"] += 1
            self.stats["rejected_unsafe"] += 1

            total_time = (datetime.now() - start_time).total_seconds()

            return PipelineResult(
                success=False,
                answer=self._build_rejection_message(safety_result),
                layer_path="1→REJECT",
                safety=safety_result,
                intent=HybridIntent(type="unknown", subtype="", confidence=0.0, metadata={}),
                total_time_s=total_time,
                estimated_cost=0.0001,  # Just safety check cost
                metadata={"reason": "unsafe_query"}
            )

        # ─────────────────────────────────────────────
        # LAYER 2: INTENT DETECTION
        # ─────────────────────────────────────────────

        if self.debug:
            print("\n[Layer 2] Intent Detection...")

        intent = self.intent_detector.detect(ctx.user_question)

        if self.debug:
            print(f"  Type: {intent.type}")
            print(f"  Subtype: {intent.subtype}")
            print(f"  Confidence: {intent.confidence:.2f}")

        # ─────────────────────────────────────────────
        # LAYER 3: ROUTING
        # ─────────────────────────────────────────────

        if intent.type == "out_of_scope":
            # Out-of-scope: Polite rejection
            result = self._handle_out_of_scope(ctx, safety_result, intent)
            self.stats["pattern_responses"] += 1  # No cost, like pattern responses

        elif intent.type == "smalltalk":
            # Layer 3A: Pattern Responder
            result = self._handle_layer_3a(ctx, safety_result, intent)
            self.stats["pattern_responses"] += 1

        elif intent.type == "info_request":
            # Layer 3B: Info Pipeline
            result = self._handle_layer_3b(ctx, safety_result, intent)
            self.stats["info_responses"] += 1

        elif intent.type == "action_request":
            # Layer 3C: Action Pipeline
            result = self._handle_layer_3c(ctx, safety_result, intent)
            self.stats["action_responses"] += 1

        else:
            # Unknown intent → Default to info pipeline
            if self.debug:
                print(f"\n[Layer 3B] Unknown intent, defaulting to Info Pipeline")

            result = self._handle_layer_3b(ctx, safety_result, intent)
            self.stats["info_responses"] += 1

        # Update global stats
        self.stats["total_queries"] += 1
        self.stats["total_cost"] += result.estimated_cost

        # Final logging
        if self.debug:
            print("\n" + "="*70)
            print(f"[COMPLETE]: {result.layer_path}")
            print(f"Time: {result.total_time_s:.2f}s | Cost: ${result.estimated_cost:.4f}")
            print("="*70)

        return result

    def _handle_layer_3a(
        self,
        ctx: RequestContext,
        safety: SafetyResult,
        intent: Intent
    ) -> PipelineResult:
        """Layer 3A: Pattern Responder (Smalltalk)"""
        if self.debug:
            print("\n[Layer 3A] Pattern Responder...")

        start_time = datetime.now()

        pattern_result = self.pattern_handler.handle(ctx.user_question)

        if not pattern_result:
            # Fallback: If pattern matching fails, use info pipeline
            if self.debug:
                print("  [WARNING] Pattern match failed, falling back to Info Pipeline")

            return self._handle_layer_3b(ctx, safety, intent)

        total_time = (datetime.now() - start_time).total_seconds()

        if self.debug:
            print(f"  Category: {pattern_result.category}")
            print(f"  Response: {pattern_result.response[:60]}...")

        return PipelineResult(
            success=True,
            answer=pattern_result.response,
            layer_path="1→2→3A",
            safety=safety,
            intent=intent,
            total_time_s=total_time,
            estimated_cost=0.0001,  # Only safety check cost
            metadata={
                "pattern_category": pattern_result.category,
                "pattern_time_ms": pattern_result.response_time_ms,
            }
        )

    def _handle_layer_3b(
        self,
        ctx: RequestContext,
        safety: SafetyResult,
        intent: Intent
    ) -> PipelineResult:
        """Layer 3B: Info Pipeline (Smart RAG + Complexity routing)"""
        if self.debug:
            print("\n[Layer 3B] Info Pipeline...")

        start_time = datetime.now()

        info_result = self.info_pipeline.handle(ctx)

        total_time = (datetime.now() - start_time).total_seconds()

        if self.debug:
            print(f"  Complexity: {info_result.complexity}")
            print(f"  RAG Used: {info_result.used_rag}")
            print(f"  Model: {info_result.model_used}")

        return PipelineResult(
            success=True,
            answer=info_result.answer,
            layer_path="1→2→3B",
            safety=safety,
            intent=intent,
            total_time_s=total_time,
            estimated_cost=0.0001 + info_result.estimated_cost,  # Safety + info cost
            metadata={
                "complexity": info_result.complexity,
                "rag_used": info_result.used_rag,
                "rag_chunks": info_result.rag_chunks,
                "model": info_result.model_used,
                "rag_sources": info_result.rag_sources,  # Add RAG sources to metadata
            }
        )

    def _handle_layer_3c(
        self,
        ctx: RequestContext,
        safety: SafetyResult,
        intent: Intent
    ) -> PipelineResult:
        """Layer 3C: Action Pipeline (Script generation with validation)"""
        if self.debug:
            print("\n[Layer 3C] Action Pipeline...")

        start_time = datetime.now()

        action_result = self.action_pipeline.handle(ctx)

        total_time = (datetime.now() - start_time).total_seconds()

        if not action_result.success:
            # Missing parameters - ask user
            if self.debug:
                print(f"  [WARNING] Missing parameters: {action_result.missing_params}")

            return PipelineResult(
                success=False,
                answer=action_result.user_prompt_message,
                layer_path="1→2→3C→PARAMS_NEEDED",
                safety=safety,
                intent=intent,
                total_time_s=total_time,
                estimated_cost=0.0001,  # Just safety check cost
                metadata={
                    "missing_params": action_result.missing_params,
                    "reason": "missing_parameters"
                }
            )

        # Success - script generated
        if self.debug:
            print(f"  [SUCCESS] Script generated")
            print(f"  Model: {action_result.model_used}")

        return PipelineResult(
            success=True,
            answer=action_result.answer,
            layer_path="1→2→3C",
            safety=safety,
            intent=intent,
            total_time_s=total_time,
            estimated_cost=0.0001 + action_result.estimated_cost,
            metadata={
                "model": action_result.model_used,
                "script_generated": True,
            }
        )

    def _handle_out_of_scope(
        self,
        ctx: RequestContext,
        safety: SafetyResult,
        intent: Intent
    ) -> PipelineResult:
        """Handle out-of-scope (non-security) queries with polite rejection"""
        if self.debug:
            print("\n[Out-of-Scope] Non-security topic detected")

        start_time = datetime.now()

        # Build polite rejection message
        message = """KAPSAMDISI SORU

Ben sadece siber guvenlik ve isletim sistemi sikilaştirma (OS hardening) konularinda yardimci olabiliyorum.

Size yardimci olabilecegim konular:
- SSH, RDP, Firewall hardening
- CIS Benchmarks ve NIST 800-207 uygulamalari
- Zero Trust Architecture
- Guvenlik yapilandirmalari ve scriptleri
- Vulnerability assessment ve risk azaltma

Lutfen guvenlik veya sistem sikilaştirma ile ilgili bir soru sorun."""

        total_time = (datetime.now() - start_time).total_seconds()

        if self.debug:
            print(f"  Topic: Non-security")
            print(f"  Response: Polite rejection")

        return PipelineResult(
            success=True,  # Not an error, just out of scope
            answer=message,
            layer_path="1→2→OUT_OF_SCOPE",
            safety=safety,
            intent=intent,
            total_time_s=total_time,
            estimated_cost=0.0001,  # Just safety check cost
            metadata={
                "reason": "out_of_scope",
                "matched_keywords": intent.metadata.get("matched_keywords", [])
            }
        )

    def _build_rejection_message(self, safety: SafetyResult) -> str:
        """Build user-friendly rejection message for unsafe queries"""
        return f"""GUVENLIK UYARISI

Bu soru guvenlik politikalarimiz kapsaminda yanitlanamıyor.

Kategori: {safety.category}
Sebep: {safety.reason}

Neden reddedildi?
Bu sistem savunma amacli guvenlik sikilaştirma icin tasarlanmiştir. Saldiri, exploit geliştirme veya zararli amacli sorular kabul edilmez.

Nasil yardimci olabilirim?
- Sistem guvenligi nasil artirilir?
- CIS Benchmark best practices neler?
- SSH/RDP hardening nasil yapilir?
- Zero Trust nasil uygulanir?

Lutfen sorunuzu savunma odakli olacak sekilde yeniden ifade edin.
"""

    def get_stats(self) -> dict:
        """Get pipeline statistics"""
        total = self.stats["total_queries"]
        if total == 0:
            return self.stats

        return {
            **self.stats,
            "rejection_rate": self.stats["rejected_unsafe"] / total,
            "pattern_rate": self.stats["pattern_responses"] / total,
            "info_rate": self.stats["info_responses"] / total,
            "action_rate": self.stats["action_responses"] / total,
            "avg_cost_per_query": self.stats["total_cost"] / total,
            "layer_stats": {
                "safety": self.safety_classifier.get_stats(),
                "intent": self.intent_detector.get_stats(),
                "pattern": self.pattern_handler.get_stats(),
                "info": self.info_pipeline.get_stats(),
                "action": self.action_pipeline.get_stats(),
            }
        }


# ─────────────────────────────────────────────
# Convenience Function
# ─────────────────────────────────────────────

def run_secure_pipeline_v2(
    question: str,
    llm_ultra_fast: LLMCallable,
    llm_small: LLMCallable,
    llm_large: LLMCallable,
    rag_builder: Optional[Callable] = None,
    context: Optional[RequestContext] = None,
    debug: bool = False,
) -> PipelineResult:
    """
    Run the 4-layer secure pipeline

    Usage:
        result = run_secure_pipeline_v2(
            question="Ubuntu 22.04 SSH hardening nasıl yapılır?",
            llm_ultra_fast=groq_llama_8b,  # FREE
            llm_small=groq_llama_8b,  # FREE
            llm_large=openai_gpt4o_mini,
            rag_builder=rag_builder,
            debug=True
        )

        print(result.answer)
        print(f"Path: {result.layer_path}")
        print(f"Cost: ${result.estimated_cost:.4f}")
    """
    from llm.core.context import RequestContext

    if context is None:
        context = RequestContext(user_question=question)

    pipeline = SecurePipelineV2(
        llm_ultra_fast=llm_ultra_fast,
        llm_small=llm_small,
        llm_large=llm_large,
        rag_builder=rag_builder,
        debug=debug,
    )

    return pipeline.run(context)

