# prompts/few_shot_examples.py
"""
Few-Shot Examples — içerik llm/prompts/templates/few_shot.md dosyasına taşındı.
Geriye dönük uyumluluk için bu modül FEW_SHOT_EXAMPLES sabitini hâlâ sağlar.
"""

from __future__ import annotations
from .loader import load_template

FEW_SHOT_EXAMPLES: str = load_template("few_shot")
