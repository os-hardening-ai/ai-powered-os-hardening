# llm/__init__.py
"""
LLM Pipeline Module - Reorganized Structure

Yapı:
- core/: Ana LLM işlevleri, Models, Layers
- ml/: Machine Learning (intent detection, eval)
- testing/: Test ve validation
- monitoring/: Logging, metrics, prompts
"""

__version__ = "0.2.0"

# Core imports
from .core.pipeline_optimized import OptimizedPipeline, run_optimized_pipeline_with_retry
from .core.context import RequestContext
from .core.config import *
from .core.models import get_llm_clients

# ML imports
from .ml.ml_intent_detector import *

__all__ = [
    "core",
    "ml",
    "testing",
    "monitoring",
    "OptimizedPipeline",
    "run_optimized_pipeline_with_retry",
    "RequestContext",
    "get_llm_clients",
]
