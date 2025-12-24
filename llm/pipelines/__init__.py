"""
Pipelines Module
================

Security-first pipeline implementations for OS hardening assistant.

## Available Pipelines:

1. **OptimizedPipeline** (optimized.py):
   - Chain-of-Thought + Adaptive Routing
   - Complexity-based model selection
   - 1-2 LLM calls (vs 6-7 in old pipeline)
   - Cost: ~$0.015 per query

2. **SecurePipelineV2** (secure_v2.py):
   - 4-Layer Security Architecture
   - Layer 1: Safety Classification
   - Layer 2: Intent Detection
   - Layer 3: Routing (Pattern/Info/Action)
   - Layer 4: Generation with validation

## Quick Start:

```python
from llm.pipelines.secure_v2 import run_secure_pipeline_v2
from llm.clients import get_llm_clients

llm_ultra_fast, llm_small, llm_large = get_llm_clients()

result = run_secure_pipeline_v2(
    question="SSH hardening nasıl yapılır?",
    llm_ultra_fast=llm_ultra_fast,
    llm_small=llm_small,
    llm_large=llm_large
)
```
"""

from .optimized import OptimizedPipeline, run_optimized_pipeline
from .secure_v2 import SecurePipelineV2, run_secure_pipeline_v2, PipelineResult

__all__ = [
    "OptimizedPipeline",
    "run_optimized_pipeline",
    "SecurePipelineV2",
    "run_secure_pipeline_v2",
    "PipelineResult",
]
