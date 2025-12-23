# prompts/__init__.py
"""Advanced prompt templates for optimized LLM usage."""

from .cot_prompts import CoTSecurityAnalyzer
from .few_shot_examples import FEW_SHOT_EXAMPLES

__all__ = [
    "CoTSecurityAnalyzer",
    "FEW_SHOT_EXAMPLES",
]
