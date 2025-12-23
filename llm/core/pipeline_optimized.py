# pipeline_optimized.py
"""
Optimized Pipeline - Chain-of-Thought + Adaptive Routing + Complexity-Based Routing

Eski pipeline: 6-7 LLM çağrısı, 10-15 saniye, $0.08
Yeni pipeline: 1-2 LLM çağrısı, 2-4 saniye, $0.015

Optimizasyonlar:
1. CoT prompting ile 6 adımı 1 çağrıda birleştir
2. Adaptive routing ile task'e uygun model seç
3. Smalltalk ve basit sorular için hızlı path
4. 3-seviyeli karmaşıklık analizi (simple/medium/complex)
5. Basit sorular için düşük model + minimal format
"""

from __future__ import annotations

from typing import Callable, Optional
from datetime import datetime

from .context import RequestContext, SafetyResult
from .models.adaptive_router import AdaptiveModelRouter, ModelSpec
from ..monitoring.prompts.cot_prompts import CoTSecurityAnalyzer
from ..monitoring.prompts.simple_prompts import get_prompt_for_complexity
from ..ml.utils.question_classifier import classify_question
from ..ml.utils.local_responder import get_local_response
from .config import CONFIG

# RAG Integration
try:
    from .rag_integration import get_rag_context_builder
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("[WARNING] RAG integration not available. Install dependencies or check rag_integration.py")


# Type alias
LLMCallable = Callable[[str], str]


class OptimizedPipeline:
    """
    Optimize edilmiş pipeline.

    Üç ana path:
    1. Fast Path: Smalltalk için ultra-fast model
    2. Simple Path: Basit bilgi soruları için düşük model + minimal format
    3. Medium Path: Orta karmaşıklık için gpt-4o-mini + orta format
    4. Complex Path: Karmaşık güvenlik analizi için CoT reasoning
    """

    def __init__(
        self,
        llm_small: LLMCallable,
        llm_large: LLMCallable,
        priority: str = "balanced",
        use_rag: bool = True,
        rag_top_k: int = 5,
        rag_min_score: float = 0.7,
    ):
        """
        Args:
            llm_small: Küçük/hızlı model callable (gpt-3.5-turbo veya groq-llama-8b)
            llm_large: Büyük/güçlü model callable (gpt-4o-mini veya gpt-4o)
            priority: Model seçim önceliği (speed/quality/cost/balanced)
            use_rag: RAG retrieval kullanılsın mı (default: True)
            rag_top_k: RAG'den kaç chunk getirileceği (default: 5)
            rag_min_score: Minimum relevance score (default: 0.7)
        """
        self.llm_small = llm_small
        self.llm_large = llm_large
        self.use_rag = use_rag and RAG_AVAILABLE

        # Adaptive router
        self.router = AdaptiveModelRouter(default_priority=priority)  # type: ignore

        # CoT analyzer (sadece complex sorular için)
        self.cot_analyzer = CoTSecurityAnalyzer(use_few_shot=True)

        # RAG Context Builder
        self.rag_builder = None
        if self.use_rag:
            try:
                self.rag_builder = get_rag_context_builder(
                    top_k=rag_top_k,
                    min_score=rag_min_score
                )
                if CONFIG.enable_debug_logs:
                    print(f"[OptimizedPipeline] RAG enabled (top_k={rag_top_k}, min_score={rag_min_score})")
            except Exception as e:
                print(f"[OptimizedPipeline] RAG initialization failed: {e}")
                self.rag_builder = None
                self.use_rag = False

        # Stats
        self.stats = {
            "total_calls": 0,
            "local_response_count": 0,  # LLM'siz lokal cevaplar
            "fast_path_count": 0,
            "simple_path_count": 0,
            "medium_path_count": 0,
            "complex_path_count": 0,
            "total_cost_estimate": 0.0,
            "rag_retrieval_count": 0,  # RAG kullanım sayısı
        }

    def run(self, ctx: RequestContext) -> RequestContext:
        """
        Pipeline'ı çalıştır.

        Args:
            ctx: Request context

        Returns:
            Updated context with final_answer
        """
        start_time = datetime.now()

        if CONFIG.enable_debug_logs:
            print(f"[OptimizedPipeline] Starting for: '{ctx.user_question[:50]}...'")

        # STEP 0: Local response check (LLM'siz, maliyet: $0)
        local_response = get_local_response(ctx.user_question)
        if local_response:
            if CONFIG.enable_debug_logs:
                print("[LocalPath] Pattern matched, using local response (no LLM)")

            ctx.final_answer = local_response
            ctx.safety = SafetyResult(category="defensive_security")
            ctx.intent = "smalltalk_greeting"  # type: ignore
            self.stats["local_response_count"] += 1

            elapsed = (datetime.now() - start_time).total_seconds()
            if CONFIG.enable_debug_logs:
                print(f"[OptimizedPipeline] Completed in {elapsed:.2f}s")
                print(f"   Local response (no LLM, $0.00)")

            return ctx

        # STEP 0.5: RAG Retrieval (güvenlik sorularında aktif olacak)
        if self.use_rag and self.rag_builder:
            try:
                rag_context = self.rag_builder.retrieve_context(ctx.user_question)
                if rag_context:
                    ctx.retrieved_context = rag_context
                    self.stats["rag_retrieval_count"] += 1

                    if CONFIG.enable_debug_logs:
                        print(f"[RAGRetrieval] Retrieved context ({len(rag_context)} chars)")
            except Exception as e:
                if CONFIG.enable_debug_logs:
                    print(f"[RAGRetrieval] Failed: {e}")

        # STEP 1: Quick intent detection (smalltalk check)
        intent_detected = self._quick_intent_check(ctx)

        # STEP 2: Path selection
        if intent_detected in ("smalltalk_greeting", "smalltalk_farewell", "smalltalk_other"):
            # Fast Path: Smalltalk için
            ctx = self._fast_path_smalltalk(ctx)
            self.stats["fast_path_count"] += 1
        else:
            # STEP 3: Question complexity classification
            complexity = classify_question(ctx.user_question)

            if CONFIG.enable_debug_logs:
                print(f"[ComplexityClassifier] Question complexity: {complexity.upper()}")

            # STEP 4: Route based on complexity
            if complexity == "simple":
                ctx = self._simple_path(ctx)
                self.stats["simple_path_count"] += 1
            elif complexity == "medium":
                ctx = self._medium_path(ctx)
                self.stats["medium_path_count"] += 1
            else:  # complex
                ctx = self._complex_path_cot(ctx)
                self.stats["complex_path_count"] += 1

        # Performance logging
        elapsed = (datetime.now() - start_time).total_seconds()

        if CONFIG.enable_debug_logs:
            print(f"[OptimizedPipeline] Completed in {elapsed:.2f}s")
            print(f"   Total LLM calls: {self.stats['total_calls']}")
            print(f"   Estimated cost: ${self.stats['total_cost_estimate']:.4f}")

        return ctx

    def _quick_intent_check(self, ctx: RequestContext) -> str:
        """
        Hızlı intent tespiti (smalltalk vs security).

        Args:
            ctx: Request context

        Returns:
            Intent string
        """
        # Basit keyword-based check (LLM çağrısı yapmadan)
        question_lower = ctx.user_question.lower()

        # Greeting patterns
        greetings = ["merhaba", "selam", "hey", "hi", "hello", "günaydın", "iyi günler"]
        if any(g in question_lower for g in greetings) and len(ctx.user_question.split()) <= 5:
            return "smalltalk_greeting"

        # Farewell patterns
        farewells = ["görüşürüz", "hoşçakal", "bye", "güle güle", "kendine iyi bak"]
        if any(f in question_lower for f in farewells):
            return "smalltalk_farewell"

        # Security keywords (güvenlik sorusu olabilir)
        security_keywords = [
            "ssh", "rdp", "firewall", "güvenlik", "security", "hardening",
            "vulnerability", "zafiyet", "exploit", "saldırı", "attack",
            "log", "monitoring", "audit", "compliance", "zero trust", "zt"
        ]

        if any(kw in question_lower for kw in security_keywords):
            return "os_hardening"  # Security path

        # Default: security path (daha güvenli)
        return "os_hardening"

    def _fast_path_smalltalk(self, ctx: RequestContext) -> RequestContext:
        """
        Smalltalk için hızlı path (ultra-fast model).

        Args:
            ctx: Request context

        Returns:
            Updated context
        """
        if CONFIG.enable_debug_logs:
            print("[FastPath] Smalltalk detected, using ultra-fast model")

        # Safety: smalltalk her zaman defensive
        ctx.safety = SafetyResult(category="defensive_security")

        # Intent
        ctx.intent = "smalltalk_greeting"  # type: ignore

        # Basit prompt
        prompt = f"""Kullanıcı sana şunu yazdı: "{ctx.user_question}"

Bu bir smalltalk mesajı. Kısa, dostça ve profesyonel bir şekilde cevap ver.
Kullanıcıya güvenlik konusunda nasıl yardımcı olabileceğini belirt.

Cevap (1-2 cümle):"""

        # LLM call (small model)
        response = self.llm_small(prompt)
        self.stats["total_calls"] += 1

        # Maliyet tahmini (small model, kısa prompt)
        self.stats["total_cost_estimate"] += 0.0001

        ctx.final_answer = response.strip()

        return ctx

    def _simple_path(self, ctx: RequestContext) -> RequestContext:
        """
        Basit bilgi soruları için path (small model + minimal format).

        Args:
            ctx: Request context

        Returns:
            Updated context
        """
        if CONFIG.enable_debug_logs:
            print("[SimplePath] Simple question detected, using small model + minimal format")

        # Safety: basit sorular her zaman defensive
        ctx.safety = SafetyResult(category="defensive_security")

        # Minimal prompt
        prompt = get_prompt_for_complexity(ctx, "simple")

        # LLM call (SMALL model - gpt-3.5-turbo veya groq-llama-8b)
        response = self.llm_small(prompt)
        self.stats["total_calls"] += 1

        # Maliyet tahmini (small model, kısa prompt = çok ucuz!)
        self.stats["total_cost_estimate"] += 0.0002  # ~$0.0002

        ctx.final_answer = response.strip()

        return ctx

    def _medium_path(self, ctx: RequestContext) -> RequestContext:
        """
        Orta karmaşıklık soruları için path (large model ama minimal format).

        Args:
            ctx: Request context

        Returns:
            Updated context
        """
        if CONFIG.enable_debug_logs:
            print("[MediumPath] Medium complexity question, using gpt-4o-mini + medium format")

        # Safety: orta sorular her zaman defensive
        ctx.safety = SafetyResult(category="defensive_security")

        # Orta seviye prompt (CoT'dan daha kısa)
        prompt = get_prompt_for_complexity(ctx, "medium")

        # LLM call (large model ama CoT olmadan)
        response = self.llm_large(prompt)
        self.stats["total_calls"] += 1

        # Maliyet tahmini (large model, orta prompt)
        self.stats["total_cost_estimate"] += 0.0005  # ~$0.0005

        ctx.final_answer = response.strip()

        return ctx

    def _complex_path_cot(self, ctx: RequestContext) -> RequestContext:
        """
        Karmaşık güvenlik analizi için CoT path (large model + full CoT).

        Args:
            ctx: Request context

        Returns:
            Updated context
        """
        if CONFIG.enable_debug_logs:
            print("[ComplexPath] Complex question detected, using CoT reasoning")

        # Model selection (adaptive routing)
        model_spec = self.router.select_for_task(
            task="answer_generator",
            ctx=ctx,
            priority="balanced",
        )

        if CONFIG.enable_debug_logs:
            print(f"   Selected model: {model_spec.name} ({model_spec.provider})")

        # CoT prompt oluştur (FULL format)
        cot_prompt = self.cot_analyzer.build_cot_prompt(ctx)

        # LLM call (large model ile CoT reasoning)
        raw_response = self.llm_large(cot_prompt)
        self.stats["total_calls"] += 1

        # Maliyet tahmini
        estimated_cost = self.router.estimate_cost(cot_prompt, model_spec)
        self.stats["total_cost_estimate"] += estimated_cost

        # Parse response
        ctx = self.cot_analyzer.parse_cot_response(raw_response, ctx)

        # Fallback: Eğer parsing başarısız olduysa, raw response'u kullan
        if not ctx.final_answer:
            ctx.final_answer = raw_response

        return ctx


# ─────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────

def run_optimized_pipeline(
    ctx: RequestContext,
    llm_small: LLMCallable,
    llm_large: LLMCallable,
    priority: str = "balanced",
) -> RequestContext:
    """
    Optimize edilmiş pipeline'ı çalıştır.

    Args:
        ctx: Request context
        llm_small: Small model callable
        llm_large: Large model callable
        priority: Model selection priority

    Returns:
        Updated context with final_answer
    """
    pipeline = OptimizedPipeline(
        llm_small=llm_small,
        llm_large=llm_large,
        priority=priority,
    )

    return pipeline.run(ctx)


def run_optimized_pipeline_with_retry(
    ctx: RequestContext,
    llm_small: LLMCallable,
    llm_large: LLMCallable,
    max_retries: int = 2,
    priority: str = "balanced",
) -> RequestContext:
    """
    Optimize edilmiş pipeline'ı retry logic ile çalıştır.

    Args:
        ctx: Request context
        llm_small: Small model callable
        llm_large: Large model callable
        max_retries: Max retry count
        priority: Model selection priority

    Returns:
        Updated context with final_answer
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            if CONFIG.enable_debug_logs and attempt > 0:
                print(f"[Retry] Attempt {attempt + 1}/{max_retries + 1}")

            return run_optimized_pipeline(
                ctx=ctx,
                llm_small=llm_small,
                llm_large=llm_large,
                priority=priority,
            )

        except Exception as e:
            last_error = e

            if CONFIG.enable_debug_logs:
                print(f"[Retry] Attempt {attempt + 1} failed: {e}")

            # Son denemeyse, hata fırlat
            if attempt == max_retries:
                break

    # Tüm retry'lar başarısız
    error_msg = (
        f"Pipeline failed after {max_retries + 1} attempts.\n"
        f"Last error: {last_error}\n\n"
        f"Lütfen API key'lerinizi ve network bağlantınızı kontrol edin."
    )

    ctx.final_answer = f"❌ HATA: {error_msg}"

    return ctx


# ─────────────────────────────────────────────
# Example Usage
# ─────────────────────────────────────────────

if __name__ == "__main__":
    from models import get_llm_clients

    # LLM clients
    llm_small, llm_large = get_llm_clients()

    # Test context 1: Security question
    test_ctx_security = RequestContext(
        user_question="SSH hardening nasıl yapılır?",
        os="ubuntu_22_04",
        role="sysadmin",
        security_level="strict",
    )

    print("="*70)
    print("TEST 1: Security Question")
    print("="*70)

    result = run_optimized_pipeline(
        ctx=test_ctx_security,
        llm_small=llm_small,
        llm_large=llm_large,
        priority="balanced",
    )

    print("\n📋 FINAL ANSWER:")
    print(result.final_answer)
    print("\n" + "="*70 + "\n")

    # Test context 2: Smalltalk
    test_ctx_smalltalk = RequestContext(
        user_question="Merhaba!",
        os="ubuntu_22_04",
        role="sysadmin",
    )

    print("="*70)
    print("TEST 2: Smalltalk")
    print("="*70)

    result = run_optimized_pipeline(
        ctx=test_ctx_smalltalk,
        llm_small=llm_small,
        llm_large=llm_large,
        priority="speed",
    )

    print("\n📋 FINAL ANSWER:")
    print(result.final_answer)
    print("\n" + "="*70 + "\n")
