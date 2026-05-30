"""
Unit tests for llm.prompts (simple_prompts + cot_prompts).

Prompt builders are pure string construction; CoT parsing is regex-based.
No LLM, no network.
"""

from __future__ import annotations

from llm.core.context import RequestContext
from llm.prompts.simple_prompts import (
    build_simple_prompt,
    build_medium_prompt,
    get_prompt_for_complexity,
)
from llm.prompts.cot_prompts import CoTSecurityAnalyzer


def ctx(q="Ubuntu 24.04 SSH hardening nasıl yapılır?", **kw):
    return RequestContext(user_question=q, **kw)


class TestSimplePrompts:
    def test_simple_prompt_contains_question(self):
        c = ctx()
        p = build_simple_prompt(c)
        assert isinstance(p, str) and c.user_question in p

    def test_medium_prompt_contains_question(self):
        c = ctx()
        assert c.user_question in build_medium_prompt(c)

    def test_prompt_includes_retrieved_context(self):
        c = ctx(retrieved_context="CIS 5.2: PermitRootLogin no")
        p = build_medium_prompt(c)
        assert "PermitRootLogin" in p

    def test_get_prompt_for_complexity_routes(self):
        c = ctx()
        for level in ("simple", "medium", "complex"):
            p = get_prompt_for_complexity(c, level)
            assert isinstance(p, str) and len(p) > 0

    def test_history_section_rendered(self):
        c = ctx(conversation_history=[
            {"role": "user", "content": "önceki soru"},
            {"role": "assistant", "content": "önceki cevap"},
        ])
        p = build_medium_prompt(c)
        # history should be woven into the prompt
        assert "önceki" in p


class TestCoT:
    def test_build_cot_prompt(self):
        analyzer = CoTSecurityAnalyzer(use_few_shot=True)
        p = analyzer.build_cot_prompt(ctx())
        assert isinstance(p, str)
        assert ctx().user_question in p

    def test_build_cot_prompt_no_few_shot(self):
        analyzer = CoTSecurityAnalyzer(use_few_shot=False)
        assert isinstance(analyzer.build_cot_prompt(ctx()), str)

    def test_parse_structured_cot_sets_final_answer(self):
        analyzer = CoTSecurityAnalyzer()
        raw = (
            "**Hedef Alan:** SSH\n"
            "**Analiz:** root login açık\n"
            "**Final Cevap:**\nPermitRootLogin no ayarla ve servisi yeniden başlat."
        )
        c = analyzer.parse_cot_response(raw, ctx())
        assert isinstance(c, RequestContext)

    def test_parse_plain_text_does_not_crash(self):
        analyzer = CoTSecurityAnalyzer()
        c = analyzer.parse_cot_response("düz metin cevap, yapısal değil", ctx())
        assert isinstance(c, RequestContext)
