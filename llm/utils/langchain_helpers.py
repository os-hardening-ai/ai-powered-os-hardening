# langchain_helpers.py
"""
LangChain Best Practices Implementation

Features:
1. Structured output validation with Pydantic
2. Prompt caching for cost reduction
3. Enhanced error handling

Based on 2025 LangChain best practices research
"""

from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

# LangChain cache - updated for newer versions
try:
    from langchain_community.cache import InMemoryCache
    import langchain
    CACHE_AVAILABLE = True
except ImportError:
    try:
        from langchain.cache import InMemoryCache
        import langchain
        CACHE_AVAILABLE = True
    except ImportError:
        CACHE_AVAILABLE = False
        print("[WARNING] LangChain cache not available")


# ═════════════════════════════════════════════
# Global Configuration
# ═════════════════════════════════════════════

def setup_langchain_cache(cache_type: Literal["memory", "none"] = "memory"):
    """
    Setup LangChain prompt caching

    Args:
        cache_type: "memory" for InMemoryCache, "none" to disable

    Benefits:
    - Reduces API costs for repeated queries
    - Improves response time for cached prompts
    - Especially useful for safety classification (same prompts)
    """
    if not CACHE_AVAILABLE:
        print("[LangChain] Cache not available, skipping setup")
        return

    if cache_type == "memory":
        langchain.llm_cache = InMemoryCache()
        print("[LangChain] Enabled InMemoryCache for prompt caching")
    elif cache_type == "none":
        langchain.llm_cache = None
        print("[LangChain] Prompt caching disabled")


# ═════════════════════════════════════════════
# Structured Output Models
# ═════════════════════════════════════════════

class ValidationIssue(BaseModel):
    """Single validation issue"""
    severity: Literal["low", "medium", "high", "critical"]
    category: Literal["dangerous_command", "prompt_leakage", "hallucination", "other"]
    description: str
    suggested_fix: Optional[str] = None


class OutputValidationResult(BaseModel):
    """
    Structured output validation result

    Used with: llm.with_structured_output(OutputValidationResult)

    Benefits:
    - Type-safe validation
    - Guaranteed JSON structure
    - No manual parsing required
    """
    is_valid: bool = Field(description="Whether the output is safe and valid")
    issues: List[ValidationIssue] = Field(
        default_factory=list,
        description="List of validation issues found"
    )
    overall_severity: Literal["safe", "minor", "moderate", "severe"] = Field(
        default="safe",
        description="Overall severity assessment"
    )
    corrected_output: Optional[str] = Field(
        default=None,
        description="Corrected version of the output if issues found"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the validation result"
    )


class SafetyClassificationResult(BaseModel):
    """
    Structured safety classification result

    Used for Layer 1 (Safety Classification)
    """
    category: Literal["safe_educational", "safe_defensive", "potentially_unsafe", "unsafe"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(description="Why this classification was chosen")
    risk_indicators: List[str] = Field(
        default_factory=list,
        description="Specific risk indicators found in the input"
    )
    allow_processing: bool = Field(
        description="Whether to allow processing this request"
    )


class IntentClassificationResult(BaseModel):
    """
    Structured intent classification result (LLM-based fallback)

    Used as Tier 3 fallback when regex and semantic routing fail
    """
    intent_type: Literal["smalltalk", "info_request", "action_request", "out_of_scope"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    suggested_layer: Literal["3A", "3B", "3C", "OUT_OF_SCOPE"]
    metadata: dict = Field(default_factory=dict)


# ═════════════════════════════════════════════
# Helper Functions
# ═════════════════════════════════════════════

def create_validation_chain(llm):
    """
    Create a structured output validation chain

    Args:
        llm: LLM instance (supports with_structured_output)

    Returns:
        Chain that outputs OutputValidationResult

    Usage:
        validation_chain = create_validation_chain(llm_large)
        result: OutputValidationResult = validation_chain.invoke({"text": output})
    """
    return llm.with_structured_output(OutputValidationResult)


def create_safety_chain(llm):
    """
    Create a structured safety classification chain

    Args:
        llm: LLM instance (supports with_structured_output)

    Returns:
        Chain that outputs SafetyClassificationResult

    Usage:
        safety_chain = create_safety_chain(llm_small)
        result: SafetyClassificationResult = safety_chain.invoke({"question": user_input})
    """
    return llm.with_structured_output(SafetyClassificationResult)


def create_intent_chain(llm):
    """
    Create a structured intent classification chain (Tier 3 fallback)

    Args:
        llm: LLM instance (supports with_structured_output)

    Returns:
        Chain that outputs IntentClassificationResult

    Usage:
        intent_chain = create_intent_chain(llm_small)
        result: IntentClassificationResult = intent_chain.invoke({"question": user_input})
    """
    return llm.with_structured_output(IntentClassificationResult)


# ═════════════════════════════════════════════
# Cost Tracking
# ═════════════════════════════════════════════

class CostTracker:
    """
    Track API costs across the pipeline

    Helps identify optimization opportunities
    """
    def __init__(self):
        self.total_cost = 0.0
        self.layer_costs = {
            "safety": 0.0,
            "intent": 0.0,
            "info": 0.0,
            "action": 0.0,
            "validation": 0.0,
        }
        self.call_counts = {
            "safety": 0,
            "intent": 0,
            "info": 0,
            "action": 0,
            "validation": 0,
        }

    def add_cost(self, layer: str, cost: float):
        """Add cost for a specific layer"""
        if layer in self.layer_costs:
            self.layer_costs[layer] += cost
            self.call_counts[layer] += 1
            self.total_cost += cost

    def get_summary(self) -> dict:
        """Get cost summary"""
        return {
            "total_cost": self.total_cost,
            "layer_costs": self.layer_costs,
            "call_counts": self.call_counts,
            "avg_cost_per_request": self.total_cost / max(sum(self.call_counts.values()), 1)
        }

    def reset(self):
        """Reset all counters"""
        self.total_cost = 0.0
        self.layer_costs = {k: 0.0 for k in self.layer_costs}
        self.call_counts = {k: 0 for k in self.call_counts}


# Global cost tracker instance
cost_tracker = CostTracker()


# ═════════════════════════════════════════════
# Initialization
# ═════════════════════════════════════════════

# Auto-setup memory cache on import (can be changed later)
setup_langchain_cache("memory")
