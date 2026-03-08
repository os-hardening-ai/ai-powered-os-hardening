# prompts/cot_prompts.py
"""
Chain-of-Thought (CoT) Prompting for Single-Shot Analysis

6-7 LLM çağrısı yerine 1 çağrı ile aynı kaliteyi sağlar.
Şablonlar llm/prompts/templates/cot.md ve few_shot.md dosyalarından yüklenir.
"""

from __future__ import annotations
from typing import Optional
import re

from llm.core.context import RequestContext
from .loader import load_template, render_template


class CoTSecurityAnalyzer:
    """Chain-of-Thought yaklaşımıyla güvenlik analizi (tek LLM çağrısı)."""

    def __init__(self, use_few_shot: bool = True):
        self.use_few_shot = use_few_shot

    def build_cot_prompt(self, ctx: RequestContext) -> str:
        """CoT prompt oluştur."""
        few_shot_section = ""
        if self.use_few_shot:
            few_shot_section = load_template("few_shot") + "\n\n"

        rag_section = (
            f"\nCIS BENCHMARK REFERANSLARI:\n{ctx.retrieved_context}\n"
            if ctx.retrieved_context else ""
        )

        return render_template(
            "cot",
            few_shot_section=few_shot_section,
            user_question=ctx.user_question,
            os=ctx.os or "belirtilmemiş",
            role=ctx.role or "sysadmin",
            security_level=ctx.security_level,
            zt_maturity=ctx.zt_maturity,
            rag_section=rag_section,
        )

    def parse_cot_response(self, raw_response: str, ctx: RequestContext) -> RequestContext:
        """CoT response'unu parse et ve context'e yaz."""

        # ADIM 1: Safety classification
        safety_match = re.search(
            r'\*\*SONUC:\*\*\s*\[?(defensive_security|ambiguous|offensive_illegal)',
            raw_response,
            re.IGNORECASE
        )
        if safety_match:
            from llm.core.context import SafetyResult
            ctx.safety = SafetyResult(category=safety_match.group(1))  # type: ignore

        # ADIM 2: Intent
        intent_match = re.search(
            r'\*\*Intent:\*\*\s*\[?(os_hardening|script_or_config|incident_analysis|conceptual_explanation)',
            raw_response,
            re.IGNORECASE
        )
        if intent_match:
            ctx.intent = intent_match.group(1)  # type: ignore

        target_match = re.search(r'\*\*Hedef Alan:\*\*\s*\[?([^\]]+)', raw_response)
        if target_match:
            ctx.target_area = target_match.group(1).strip()

        # ADIM 3: ZT Principles
        zt_section = re.search(
            r'ADIM 3:.*?\*\*Ilgili Prensipler:\*\*(.*?)─{5,}',
            raw_response,
            re.DOTALL | re.IGNORECASE
        )
        if zt_section:
            zt_text = zt_section.group(1)
            principles = re.findall(
                r'(least_privilege|continuous_verification|assume_breach|micro_segmentation|strong_identity)',
                zt_text,
                re.IGNORECASE
            )
            ctx.zt_principles = list(set(p.lower() for p in principles))

        # Standards
        standards = re.findall(r'(CIS_[A-Za-z0-9_]+:\S+|NIST_[0-9-]+:\S+|ISO_[0-9]+:\S+)', raw_response)
        if standards:
            ctx.standards = list(set(standards))

        # ADIM 4: Risk level
        risk_match = re.search(r'\*\*Risk Seviyesi:\*\*\s*\[?(low|medium|high|critical)', raw_response, re.IGNORECASE)
        if risk_match:
            ctx.extra["impact_level"] = risk_match.group(1).lower()

        # Rollback approach
        rollback_match = re.search(
            r'\*\*Rollback Stratejisi:\*\*(.*?)(?:─{5,}|ADIM 5)',
            raw_response,
            re.DOTALL | re.IGNORECASE
        )
        if rollback_match:
            ctx.extra["rollback_approach"] = rollback_match.group(1).strip()

        # ADIM 6: Final answer
        final_answer_match = re.search(
            r'ADIM 6:.*?(?:## OZET.*)',
            raw_response,
            re.DOTALL | re.IGNORECASE
        )
        if final_answer_match:
            answer_start = final_answer_match.group(0).find("## OZET")
            if answer_start != -1:
                final_answer = final_answer_match.group(0)[answer_start:]
                final_answer = re.sub(r'═{10,}.*', '', final_answer, flags=re.DOTALL)
                ctx.final_answer = final_answer.strip()
        else:
            ctx.final_answer = raw_response

        return ctx


def run_cot_analysis(
    llm_large,
    ctx: RequestContext,
    use_few_shot: bool = True
) -> RequestContext:
    """CoT analysis çalıştır (single LLM call)."""
    analyzer = CoTSecurityAnalyzer(use_few_shot=use_few_shot)
    prompt = analyzer.build_cot_prompt(ctx)
    raw_response = llm_large(prompt)
    return analyzer.parse_cot_response(raw_response, ctx)
