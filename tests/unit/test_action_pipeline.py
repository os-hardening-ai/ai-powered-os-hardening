"""
Unit tests for ActionPipeline (Layer 3C) graceful degradation.

Focus: the script-generation LLM call is now GUARDED. A provider failure
(e.g. Groq 429 after retries, timeout) must NOT crash / bubble up as a 500 —
it must return a clean success=False result with a user-facing message, the
same way the info pipeline degrades. The LLM is faked (no network).
"""

from __future__ import annotations

import pytest

from llm.pipelines.layers.action_pipeline import ActionPipeline, ActionQueryResult
from llm.core.context import RequestContext


def _ctx() -> RequestContext:
    # All required params present so we reach STEP 2C (generation).
    return RequestContext(
        user_question="Ubuntu 24.04 SSH sıkılaştırma scripti üret",
        os="ubuntu_24_04",
        role="sysadmin",
        security_level="balanced",
    )


class TestActionPipelineDegradation:
    def test_generation_failure_degrades_gracefully(self):
        def boom(_prompt):
            raise RuntimeError("Groq rate limit exceeded (429)")

        pipe = ActionPipeline(llm_large=boom, rag_builder=None, debug=False)
        result = pipe.handle(_ctx())  # must NOT raise

        assert isinstance(result, ActionQueryResult)
        assert result.success is False
        assert result.user_prompt_message  # user gets a message, not a crash
        assert "tekrar deneyin" in result.user_prompt_message.lower()
        assert result.estimated_cost == 0.0

    def test_missing_params_short_circuits_before_llm(self):
        """No LLM call when required params are missing (regression guard)."""
        called = {"n": 0}

        def llm(_p):
            called["n"] += 1
            return "x"

        pipe = ActionPipeline(llm_large=llm, rag_builder=None, debug=False)
        ctx = RequestContext(user_question="script üret")  # no os/role/level
        result = pipe.handle(ctx)
        assert result.success is False
        assert result.missing_params  # asked for params
        assert called["n"] == 0  # LLM never invoked
