"""
Integration tests for the RAG-enabled branches of Info and Action pipelines.

A fake rag_builder / query_planner / claim_verifier are injected so the
retrieval, source-extraction, query-planning and claim-verification code paths
run deterministically and offline.
"""

from __future__ import annotations

import types

import pytest

from llm.core.context import RequestContext
from llm.pipelines.layers.info_pipeline import InfoPipeline
from llm.pipelines.layers.action_pipeline import ActionPipeline

pytestmark = pytest.mark.integration


CONTEXT_STR = "CIS 5.2: PermitRootLogin no; Port 2222"

RAW_RESULTS = [
    {
        "text": "PermitRootLogin no disables direct root SSH login.",
        "score": 0.91,
        "metadata": {
            "section_id": "5.2",
            "section_title": "SSH Server",
            "doc_type": "pdf",
            "benchmark_product": "CIS Ubuntu 24.04",
        },
    },
    {
        "text": "audit: grep PermitRootLogin\nremediation: set PermitRootLogin no",
        "score": 0.88,
        "metadata": {
            "doc_type": "yaml_rule",
            "rule_id": "5.2.8",
            "title": "Disable SSH root login",
        },
    },
]


class FakeRag:
    def __init__(self):
        self.calls = []  # çağrı izleme — RAG atlandığında boş kalmalı

    def retrieve_balanced(self, query):
        self.calls.append(query)
        return CONTEXT_STR, RAW_RESULTS

    def retrieve_multi(self, queries, original_query):
        self.calls.append(original_query)
        return CONTEXT_STR, RAW_RESULTS


def fake_query_planner():
    plan = types.SimpleNamespace(all_queries=lambda: ["q1", "q2"])
    return types.SimpleNamespace(plan=lambda q: plan)


class FakeVerifier:
    """Reports one unsupported claim -> low confidence -> disclaimer appended."""

    def __init__(self, valid=False, confidence=0.4):
        self._valid = valid
        self._conf = confidence

    def verify(self, answer, chunks):
        return types.SimpleNamespace(
            is_valid=self._valid,
            confidence=self._conf,
            unsupported=["Port 2222"],
        )


LONG_ANSWER = (
    "SSH güvenliği için PermitRootLogin no ayarlanmalı ve port değiştirilmeli; "
    "bu CIS 5.2 ile uyumludur ve yetkisiz erişimi azaltır."
)


class TestInfoPipelineRag:
    def test_rag_retrieval_and_sources(self):
        ip = InfoPipeline(
            llm_small=lambda _p: LONG_ANSWER,
            llm_large=lambda _p: LONG_ANSWER,
            rag_builder=FakeRag(),
        )
        res = ip.handle(RequestContext(user_question="Ubuntu 24.04 sshd_config CIS 5.2 hardening"))
        assert res.used_rag
        assert res.rag_chunks == 2
        assert res.rag_sources  # source metadata extracted
        assert res.answer

    def test_query_planner_and_claim_verifier_branches(self):
        ip = InfoPipeline(
            llm_small=lambda _p: LONG_ANSWER,
            llm_large=lambda _p: LONG_ANSWER,
            rag_builder=FakeRag(),
            query_planner=fake_query_planner(),
            claim_verifier=FakeVerifier(valid=False, confidence=0.4),
        )
        res = ip.handle(
            RequestContext(user_question="Ubuntu 24.04 sshd_config CIS 5.2 detaylı hardening prosedürü ve gerekçesi")
        )
        # low-confidence disclaimer should be appended
        assert res.verification_confidence == pytest.approx(0.4)
        assert "Güven skoru" in res.answer or "güven" in res.answer.lower()


class TestSmartRagTriggering:
    """Akıllı RAG tetikleme: jenerik tanım → atla, spesifik/zor → kullan."""

    def _pipe(self, rb):
        return InfoPipeline(
            llm_small=lambda _p: "Kısa cevap.",
            llm_large=lambda _p: LONG_ANSWER,
            rag_builder=rb,
        )

    def test_generic_definition_skips_rag(self):
        """'Firewall nedir?' → RAG ATLANIR (gereksiz embedding/Qdrant çağrısı yok)."""
        rb = FakeRag()
        res = self._pipe(rb).handle(RequestContext(user_question="Firewall nedir?"))
        assert res.used_rag is False
        assert rb.calls == []              # retriever hiç çağrılmadı
        assert res.model_used == "small"   # basit → küçük model

    def test_specific_question_uses_rag(self):
        """Spesifik OS/config sorusu → RAG çalışır + büyük modele yönlenir."""
        rb = FakeRag()
        res = self._pipe(rb).handle(
            RequestContext(user_question="Ubuntu 24.04 sshd_config PermitRootLogin nasıl ayarlanır?")
        )
        assert res.used_rag is True
        assert len(rb.calls) >= 1
        assert res.model_used in ("large", "large+CoT")

    def test_generic_plus_specific_indicator_uses_rag(self):
        """'ubuntu ... nedir' jenerik+spesifik karışımı → spesifik baskın, RAG çalışır."""
        rb = FakeRag()
        res = self._pipe(rb).handle(
            RequestContext(user_question="Ubuntu 24.04 ufw nedir ve nasıl yapılandırılır?")
        )
        assert res.used_rag is True
        assert len(rb.calls) >= 1


class TestActionPipelineRag:
    def test_script_prompt_uses_yaml_and_pdf_chunks(self):
        captured = {}

        def big_llm(prompt):
            captured["prompt"] = prompt
            return "```bash\n#!/usr/bin/env bash\nset -euo pipefail\nsudo sed -i 's/.../' /etc/ssh/sshd_config\n```"

        ap = ActionPipeline(
            llm_large=big_llm,
            llm_small=lambda _p: "OK",     # zt enrich falls back / output deep-check returns OK
            rag_builder=FakeRag(),
        )
        ctx = RequestContext(
            user_question="Ubuntu 24.04 SSH root login kapat",
            os="ubuntu_24_04",
            role="sysadmin",
            security_level="strict",
        )
        res = ap.handle(ctx)
        assert res.success
        assert res.rag_sources
        # YAML rule scripts must be surfaced into the generation prompt
        assert "CIS Rule Scripts" in captured["prompt"]
        assert "5.2.8" in captured["prompt"]

    def test_missing_params_returns_prompt(self):
        ap = ActionPipeline(llm_large=lambda _p: "x", rag_builder=FakeRag())
        res = ap.handle(RequestContext(user_question="script yaz"))
        assert res.success is False
        assert res.missing_params  # os/role missing
        assert res.user_prompt_message
