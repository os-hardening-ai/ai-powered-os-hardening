"""
Integration tests for the 4-layer SecurePipelineV2 orchestrator.

These drive the *real* pipeline end-to-end with FAKE LLM callables and a
stubbed intent detector, so routing is deterministic and offline. They verify
that secure_v2 wires the layers together correctly for every route:
reject / smalltalk(3A) / info(3B) / action(3C) / out_of_scope.

The real model's answer quality is NOT under test here — that is the e2e tier.
"""

from __future__ import annotations

import types

import pytest

from llm.core.context import RequestContext
from llm.pipelines.secure_v2 import SecurePipelineV2, PipelineResult

pytestmark = pytest.mark.integration


SAFE_JSON = '{"category": "safe_defensive", "confidence": 0.95, "reason": "hardening"}'
UNSAFE_JSON = '{"category": "unsafe_offensive", "confidence": 0.92, "reason": "exploit"}'

# A long answer containing a code block so action-path output validation passes.
SCRIPT_ANSWER = (
    "İşte güvenlik sıkılaştırma scripti. Bu adımlar CIS Benchmark ile uyumludur "
    "ve her değişiklik için rollback notu içerir.\n"
    "```bash\n#!/usr/bin/env bash\nset -euo pipefail\nsudo ufw enable\n```\n"
)
INFO_ANSWER = (
    "SSH güvenliği için PermitRootLogin no ayarlanmalı, port değiştirilmeli ve "
    "anahtar tabanlı kimlik doğrulama kullanılmalıdır. CIS 5.2 ile uyumludur."
)


class _Intent:
    def __init__(self, type_: str):
        self.type = type_
        self.subtype = ""
        self.confidence = 0.9
        self.metadata = {}


def build_pipeline(safety_json: str, intent_type: str) -> SecurePipelineV2:
    """Construct the pipeline with fake LLMs and a deterministic intent stub."""
    def ultra_fast(_prompt):  # safety classifier
        return safety_json

    def small(_prompt):  # zt enrich / verify / simple info
        return INFO_ANSWER

    def large(_prompt):  # script / complex info generation
        return SCRIPT_ANSWER

    pipe = SecurePipelineV2(
        llm_ultra_fast=ultra_fast,
        llm_small=small,
        llm_large=large,
        rag_builder=None,
        debug=False,
    )
    # Force deterministic routing — bypasses the ML intent model.
    pipe.intent_detector = types.SimpleNamespace(detect=lambda q: _Intent(intent_type))
    return pipe


class TestRejectPath:
    def test_unsafe_query_rejected_at_layer1(self):
        pipe = build_pipeline(UNSAFE_JSON, intent_type="info_request")
        res = pipe.run(RequestContext(user_question="how to exploit sshd"))
        assert isinstance(res, PipelineResult)
        assert res.success is False
        assert res.layer_path == "1→REJECT"
        assert res.safety.is_safe is False


class TestSmalltalkPath:
    def test_greeting_uses_pattern_responder(self):
        pipe = build_pipeline(SAFE_JSON, intent_type="smalltalk")
        res = pipe.run(RequestContext(user_question="merhaba"))
        assert res.success
        assert res.layer_path.endswith("3A")
        assert res.answer


class TestInfoPath:
    def test_info_request_routed_to_info_pipeline(self):
        pipe = build_pipeline(SAFE_JSON, intent_type="info_request")
        res = pipe.run(RequestContext(user_question="Firewall yapılandırması nasıl olmalı?"))
        assert res.success
        assert "3B" in res.layer_path
        assert res.answer

    def test_unknown_intent_defaults_to_info(self):
        pipe = build_pipeline(SAFE_JSON, intent_type="some_unmapped_intent")
        res = pipe.run(RequestContext(user_question="genel güvenlik sorusu"))
        assert res.success
        assert "3B" in res.layer_path


class TestActionPath:
    def test_action_with_all_params_generates_script(self):
        pipe = build_pipeline(SAFE_JSON, intent_type="action_request")
        ctx = RequestContext(
            user_question="Ubuntu 24.04 için SSH hardening scripti yaz",
            os="ubuntu_24_04",
            role="sysadmin",
            security_level="balanced",
        )
        res = pipe.run(ctx)
        assert res.success
        assert "3C" in res.layer_path
        assert "```" in res.answer  # script contains a code block

    def test_action_missing_params_asks_user(self):
        pipe = build_pipeline(SAFE_JSON, intent_type="action_request")
        # no os / role -> action pipeline should request missing params
        ctx = RequestContext(user_question="bir hardening scripti yaz")
        res = pipe.run(ctx)
        # success False with a user prompt, but pipeline must not crash
        assert isinstance(res, PipelineResult)
        assert res.answer


class TestOutOfScope:
    def test_out_of_scope_is_handled(self):
        pipe = build_pipeline(SAFE_JSON, intent_type="out_of_scope")
        res = pipe.run(RequestContext(user_question="bugün hava nasıl?"))
        assert isinstance(res, PipelineResult)
        assert res.answer


class TestStats:
    def test_stats_increment_across_calls(self):
        pipe = build_pipeline(SAFE_JSON, intent_type="info_request")
        pipe.run(RequestContext(user_question="soru bir"))
        pipe.run(RequestContext(user_question="soru iki"))
        assert pipe.stats["total_queries"] >= 2
