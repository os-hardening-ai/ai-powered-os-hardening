# prompts/simple_prompts.py
"""
Basit ve Orta Karmaşıklıktaki Sorular için Prompt Builder

Şablonlar llm/prompts/templates/ klasöründeki .md dosyalarından yüklenir.
Yeni prompt denemek için Python kodu yerine .md dosyalarını düzenleyin.
"""

from __future__ import annotations
from llm.core.context import RequestContext
from .loader import render_template


def build_simple_prompt(ctx: RequestContext) -> str:
    """Basit bilgi soruları için minimal prompt."""
    rag_section = (
        f"\nCIS BENCHMARK REFERANSLARI:\n{ctx.retrieved_context}\n"
        if ctx.retrieved_context else ""
    )
    return render_template(
        "simple",
        user_question=ctx.user_question,
        os=ctx.os or "genel",
        role=ctx.role or "sysadmin",
        rag_section=rag_section,
        rag_instruction=" CIS Benchmark referanslarına dayan." if ctx.retrieved_context else "",
    )


def build_medium_prompt(ctx: RequestContext) -> str:
    """Orta karmaşıklıktaki sorular için dengeli prompt."""
    rag_section = (
        f"\nCIS BENCHMARK REFERANSLARI:\n{ctx.retrieved_context}\n"
        if ctx.retrieved_context else ""
    )
    return render_template(
        "medium",
        user_question=ctx.user_question,
        os=ctx.os or "genel",
        role=ctx.role or "sysadmin",
        security_level=ctx.security_level,
        rag_section=rag_section,
        rag_instruction=" CIS Benchmark referanslarını kullan." if ctx.retrieved_context else "",
    )


def get_prompt_for_complexity(ctx: RequestContext, complexity: str) -> str:
    """
    Soru karmaşıklığına göre uygun prompt'u döndür.

    Args:
        ctx: Request context
        complexity: "simple" | "medium" | "complex"

    Returns:
        Uygun prompt string
    """
    if complexity == "simple":
        return build_simple_prompt(ctx)
    elif complexity == "medium":
        return build_medium_prompt(ctx)
    else:
        from .cot_prompts import CoTSecurityAnalyzer
        return CoTSecurityAnalyzer(use_few_shot=True).build_cot_prompt(ctx)
