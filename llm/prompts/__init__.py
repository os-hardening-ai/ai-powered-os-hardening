"""
Prompts Module
==============

Prompt templates for LLM interactions.

## Components:

- **CoT Prompts** (`cot_prompts.py`):
  - Chain-of-Thought reasoning for complex security analysis
  - 6-step structured analysis
  - Few-shot examples support

- **Simple Prompts** (`simple_prompts.py`):
  - Minimal prompts for simple/medium complexity questions
  - Complexity-based template selection

- **Few-Shot Examples** (`few_shot_examples.py`):
  - Example question-answer pairs
  - Improves LLM performance on security tasks
"""

from .cot_prompts import CoTSecurityAnalyzer, run_cot_analysis
from .simple_prompts import get_prompt_for_complexity
from .few_shot_examples import FEW_SHOT_EXAMPLES

__all__ = [
    "CoTSecurityAnalyzer",
    "run_cot_analysis",
    "get_prompt_for_complexity",
    "FEW_SHOT_EXAMPLES",
]
