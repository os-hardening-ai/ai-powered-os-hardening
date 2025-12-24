# models/adaptive_router.py
"""
Adaptive Model Router - Task Complexity'e Göre Model Seçimi

Basit tasklar için küçük/hızlı model, karmaşık tasklar için büyük/güçlü model kullanır.
Hem maliyet hem latency optimize edilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Callable
from enum import Enum

from llm.core.context import RequestContext, IntentType


# Type alias
LLMCallable = Callable[[str], str]


class ModelTier(Enum):
    """Model tier seviyeleri"""
    ULTRA_FAST = "ultra_fast"  # Groq llama-8b, gpt-4o-mini
    BALANCED = "balanced"       # gpt-4o-mini, claude-haiku
    POWERFUL = "powerful"       # gpt-4o, claude-sonnet


@dataclass
class ModelSpec:
    """Model specifications ve performance karakteristikleri"""

    name: str
    provider: str  # openai, groq, anthropic
    tier: ModelTier

    # Performance metrics (approximate)
    cost_per_1k_tokens: float  # USD
    avg_latency_ms: int        # milliseconds
    capability_score: int      # 1-10, subjective quality rating

    # Limits
    context_window: int = 8000
    max_output_tokens: int = 2048

    def __repr__(self) -> str:
        return f"<ModelSpec {self.name} ({self.provider}) - ${self.cost_per_1k_tokens:.4f}/1k, {self.avg_latency_ms}ms>"


class ModelRegistry:
    """Mevcut modellerin kayıt defteri"""

    MODELS = {
        # Ultra Fast Tier (sınıflandırma, basit tasks)
        "llama-3.1-8b-instant": ModelSpec(
            name="llama-3.1-8b-instant",
            provider="groq",
            tier=ModelTier.ULTRA_FAST,
            cost_per_1k_tokens=0.00027,
            avg_latency_ms=200,
            capability_score=6,
            context_window=8000,
        ),
        "gpt-4o-mini-fast": ModelSpec(
            name="gpt-4o-mini",
            provider="openai",
            tier=ModelTier.ULTRA_FAST,
            cost_per_1k_tokens=0.00015,
            avg_latency_ms=500,
            capability_score=7,
            context_window=128000,
        ),

        # Balanced Tier (genel kullanım)
        "gpt-4o-mini": ModelSpec(
            name="gpt-4o-mini",
            provider="openai",
            tier=ModelTier.BALANCED,
            cost_per_1k_tokens=0.00015,
            avg_latency_ms=800,
            capability_score=8,
            context_window=128000,
        ),
        "llama-3.1-70b-versatile": ModelSpec(
            name="llama-3.1-70b-versatile",
            provider="groq",
            tier=ModelTier.BALANCED,
            cost_per_1k_tokens=0.00064,
            avg_latency_ms=600,
            capability_score=8,
            context_window=8000,
        ),

        # Powerful Tier (complex reasoning, critical tasks)
        "gpt-4o": ModelSpec(
            name="gpt-4o",
            provider="openai",
            tier=ModelTier.POWERFUL,
            cost_per_1k_tokens=0.005,
            avg_latency_ms=1500,
            capability_score=10,
            context_window=128000,
            max_output_tokens=4096,
        ),
    }

    @classmethod
    def get(cls, name: str) -> ModelSpec:
        """Model spec'i getir"""
        if name not in cls.MODELS:
            raise ValueError(f"Unknown model: {name}. Available: {list(cls.MODELS.keys())}")
        return cls.MODELS[name]

    @classmethod
    def get_by_tier(cls, tier: ModelTier) -> list[ModelSpec]:
        """Tier'a göre modelleri getir"""
        return [spec for spec in cls.MODELS.values() if spec.tier == tier]


class AdaptiveModelRouter:
    """
    Task complexity ve priority'ye göre en uygun modeli seç.

    Strateji:
    - Simple tasks (safety, intent classification) → Ultra Fast
    - Medium tasks (zt_mapping, planning) → Balanced
    - Complex tasks (answer generation, correction) → Balanced veya Powerful (priority'ye göre)
    """

    def __init__(
        self,
        default_priority: Literal["speed", "quality", "cost"] = "balanced"
    ):
        """
        Args:
            default_priority: Varsayılan optimizasyon hedefi
                - speed: En hızlı modeli seç
                - quality: En kaliteli modeli seç
                - cost: En ucuz modeli seç
        """
        self.default_priority = default_priority
        self.registry = ModelRegistry()

    def select_for_task(
        self,
        task: str,
        ctx: RequestContext,
        priority: Literal["speed", "quality", "cost", "balanced"] | None = None
    ) -> ModelSpec:
        """
        Task ve context'e göre en uygun modeli seç.

        Args:
            task: Pipeline task adı (safety_classifier, answer_generator, vb.)
            ctx: Request context
            priority: Optimizasyon hedefi (None ise default kullanılır)

        Returns:
            Seçilen model spec
        """

        priority = priority or self.default_priority

        # Task complexity bazlı kararlar
        if task in ("safety_classifier", "smalltalk"):
            # En basit tasklar - ultra fast yeterli
            return self._select_ultra_fast(priority)

        elif task in ("intent_classifier", "output_judge"):
            # Sınıflandırma taskları - ultra fast veya balanced
            if priority == "quality":
                return self._select_balanced(priority)
            return self._select_ultra_fast(priority)

        elif task in ("zt_mapper", "planner"):
            # Orta complexity - balanced ideal
            return self._select_balanced(priority)

        elif task == "answer_generator":
            # En kritik task - quality priority ise powerful
            if priority == "quality":
                return self._select_powerful()
            return self._select_balanced(priority)

        elif task == "correction":
            # Correction için powerful tercih edilir
            return self._select_powerful()

        else:
            # Unknown task - balanced seç
            return self._select_balanced(priority)

    def _select_ultra_fast(self, priority: str) -> ModelSpec:
        """Ultra fast tier'dan seç"""
        candidates = self.registry.get_by_tier(ModelTier.ULTRA_FAST)

        if priority == "speed":
            # En düşük latency
            return min(candidates, key=lambda m: m.avg_latency_ms)
        elif priority == "cost":
            # En düşük maliyet
            return min(candidates, key=lambda m: m.cost_per_1k_tokens)
        else:  # quality or balanced
            # En yüksek capability
            return max(candidates, key=lambda m: m.capability_score)

    def _select_balanced(self, priority: str) -> ModelSpec:
        """Balanced tier'dan seç"""
        candidates = self.registry.get_by_tier(ModelTier.BALANCED)

        if not candidates:
            # Fallback to ultra fast
            return self._select_ultra_fast(priority)

        if priority == "speed":
            return min(candidates, key=lambda m: m.avg_latency_ms)
        elif priority == "cost":
            return min(candidates, key=lambda m: m.cost_per_1k_tokens)
        else:  # quality or balanced
            return max(candidates, key=lambda m: m.capability_score)

    def _select_powerful(self) -> ModelSpec:
        """Powerful tier'dan en iyisini seç"""
        candidates = self.registry.get_by_tier(ModelTier.POWERFUL)

        if not candidates:
            # Fallback to balanced
            return self._select_balanced("quality")

        # Quality öncelikli - en yüksek capability
        return max(candidates, key=lambda m: m.capability_score)

    def estimate_cost(self, prompt: str, model_spec: ModelSpec) -> float:
        """
        Tahmini request maliyetini hesapla.

        Args:
            prompt: LLM prompt
            model_spec: Model specification

        Returns:
            Estimated cost in USD
        """

        # Rough estimate: 1 token ≈ 4 characters
        # Input + output tokens
        input_tokens = len(prompt) / 4
        output_tokens = model_spec.max_output_tokens * 0.5  # Varsayılan olarak max'ın yarısı

        total_tokens = input_tokens + output_tokens
        estimated_cost = (total_tokens / 1000) * model_spec.cost_per_1k_tokens

        return estimated_cost

    def get_recommendation(self, ctx: RequestContext) -> dict:
        """
        Tüm pipeline için model önerileri.

        Args:
            ctx: Request context

        Returns:
            Dict mapping task -> recommended model
        """

        # Intent bazlı dinamik strateji
        if ctx.intent in ("smalltalk_greeting", "smalltalk_farewell", "smalltalk_other"):
            priority = "speed"  # Smalltalk için hız önemli
        elif ctx.security_level == "strict":
            priority = "quality"  # Strict mode'da kalite öncelikli
        else:
            priority = "balanced"

        recommendations = {
            "safety_classifier": self.select_for_task("safety_classifier", ctx, priority),
            "intent_classifier": self.select_for_task("intent_classifier", ctx, priority),
            "zt_mapper": self.select_for_task("zt_mapper", ctx, priority),
            "planner": self.select_for_task("planner", ctx, priority),
            "answer_generator": self.select_for_task("answer_generator", ctx, priority),
            "output_judge": self.select_for_task("output_judge", ctx, priority),
            "correction": self.select_for_task("correction", ctx, priority),
        }

        return recommendations

    def print_recommendation_summary(self, recommendations: dict):
        """Önerileri güzelce yazdır"""
        print("\n" + "="*70)
        print("🎯 ADAPTIVE MODEL ROUTING RECOMMENDATIONS")
        print("="*70)

        for task, model_spec in recommendations.items():
            print(f"\n{task:20} → {model_spec.name:30} ({model_spec.provider})")
            print(f"{'':20}   Cost: ${model_spec.cost_per_1k_tokens:.5f}/1k  |  "
                  f"Latency: ~{model_spec.avg_latency_ms}ms  |  "
                  f"Quality: {model_spec.capability_score}/10")

        # Total cost estimate (rough)
        total_cost = sum(m.cost_per_1k_tokens for m in recommendations.values()) * 0.5
        print(f"\n{'─'*70}")
        print(f"Estimated total cost per request: ${total_cost:.4f}")
        print(f"{'─'*70}\n")


# Convenience functions
def create_router(priority: str = "balanced") -> AdaptiveModelRouter:
    """Router instance oluştur"""
    return AdaptiveModelRouter(default_priority=priority)  # type: ignore


def get_optimal_model_for_task(
    task: str,
    ctx: RequestContext,
    priority: str = "balanced"
) -> ModelSpec:
    """Tek bir task için optimal model seç"""
    router = AdaptiveModelRouter(default_priority=priority)  # type: ignore
    return router.select_for_task(task, ctx)


# Example usage
if __name__ == "__main__":
    from context import RequestContext

    # Test context
    test_ctx = RequestContext(
        user_question="SSH hardening nasıl yapılır?",
        os="ubuntu_22_04",
        role="sysadmin",
        security_level="strict",
    )

    # Router oluştur
    router = AdaptiveModelRouter(default_priority="balanced")

    # Tüm tasklar için öneri al
    recommendations = router.get_recommendation(test_ctx)
    router.print_recommendation_summary(recommendations)

    # Tek bir task için
    model = router.select_for_task("answer_generator", test_ctx, priority="quality")
    print(f"\nAnswer generator için seçilen model: {model}")

    # Maliyet tahmini
    sample_prompt = "Test prompt " * 100
    estimated_cost = router.estimate_cost(sample_prompt, model)
    print(f"Tahmini maliyet: ${estimated_cost:.4f}")
