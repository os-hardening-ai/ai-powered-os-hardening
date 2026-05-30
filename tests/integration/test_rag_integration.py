"""
Integration tests for llm.rag.integration.RAGContextBuilder.

The embedding client and vector store are replaced with in-memory fakes
(monkeypatched at import site), so the retrieval orchestration — balanced
retrieval, multi-query fan-out, refinement loop, context formatting and the
fallback paths — runs deterministically with no Qdrant / Novita calls.
"""

from __future__ import annotations

import pytest

import llm.rag.integration as integ
from llm.rag.integration import RAGContextBuilder

pytestmark = pytest.mark.integration


class FakeEmbed:
    def embed_query(self, q):
        return [0.1, 0.2, 0.3, 0.4]


class FakeStore:
    """Returns deterministic hits; score controllable to drive filter/fallback."""

    def __init__(self, score=0.9, n=2, empty=False):
        self.score = score
        self.n = n
        self.empty = empty
        self.calls = []

    def search(self, emb, top_k=5, doc_type=None, os_version=None):
        self.calls.append({"top_k": top_k, "doc_type": doc_type, "os_version": os_version})
        if self.empty:
            return []
        return [
            {
                "id": f"{doc_type or 'doc'}-{i}",
                "text": f"chunk {i} for {doc_type}",
                "score": self.score - i * 0.01,
                "metadata": {
                    "section_id": "5.2",
                    "section_title": "SSH",
                    "benchmark_product": "CIS Ubuntu 24.04",
                    "doc_type": doc_type or "pdf",
                },
            }
            for i in range(self.n)
        ]


@pytest.fixture
def patch_rag(monkeypatch):
    """Patch the module-level factory functions used in RAGContextBuilder.__init__."""
    def _install(store):
        monkeypatch.setattr(integ, "get_embedding_client", lambda: FakeEmbed())
        monkeypatch.setattr(integ, "get_vector_store", lambda: store)
    return _install


def build(patch_rag, store, **kw):
    patch_rag(store)
    return RAGContextBuilder(top_k=3, min_score=0.5, use_hybrid=False, use_mmr=False, **kw)


class TestSingleQuery:
    def test_retrieve_all_returns_context_and_results(self, patch_rag):
        rb = build(patch_rag, FakeStore(score=0.9, n=2))
        ctx, results = rb.retrieve_all("Ubuntu SSH hardening")
        assert results
        assert "Kaynak" in ctx and "Relevance" in ctx

    def test_retrieve_all_fallback_when_below_threshold(self, patch_rag):
        rb = build(patch_rag, FakeStore(score=0.1, n=2))  # below min_score 0.5
        ctx, results = rb.retrieve_all("obscure query")
        assert results == []
        assert isinstance(ctx, str) and ctx  # fallback message

    def test_retrieve_context_and_raw_helpers(self, patch_rag):
        rb = build(patch_rag, FakeStore())
        assert isinstance(rb.retrieve_context("q"), str)
        assert isinstance(rb.retrieve_raw("q"), list)


class TestBalanced:
    def test_retrieve_balanced_combines_yaml_and_pdf(self, patch_rag):
        store = FakeStore(score=0.9, n=2)
        rb = build(patch_rag, store)
        ctx, results = rb.retrieve_balanced("CIS 5.2 sshd")
        # yaml_rule + cis_benchmark searched -> combined, sorted desc
        assert len(results) >= 2
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)
        doc_types = {c["doc_type"] for c in store.calls}
        assert {"yaml_rule", "cis_benchmark"} <= doc_types

    def test_retrieve_balanced_fallback_when_empty(self, patch_rag):
        rb = build(patch_rag, FakeStore(empty=True))
        ctx, results = rb.retrieve_balanced("q")
        assert results == []

    def test_refinement_loop_triggers_on_low_score(self, patch_rag):
        # max score 0.5 < min_confidence 0.55 -> refinement retrieve runs
        store = FakeStore(score=0.50, n=2)
        rb = build(patch_rag, store)
        ctx, results = rb.retrieve_balanced("borderline query")
        # refinement issues extra searches; must not crash and return something
        assert isinstance(results, list)
        assert len(store.calls) > 2  # initial 2 + refinement attempts

    def test_os_version_soft_filter_path(self, patch_rag):
        store = FakeStore(score=0.9, n=2)
        rb = build(patch_rag, store, os_version="ubuntu_24_04")
        rb.retrieve_balanced("ssh")
        # at least one search carried the os_version filter
        assert any(c["os_version"] == "ubuntu_24_04" for c in store.calls)


class TestMultiQuery:
    def test_retrieve_multi_dedups_across_queries(self, patch_rag):
        store = FakeStore(score=0.9, n=2)
        rb = build(patch_rag, store)
        ctx, results = rb.retrieve_multi(["q1", "q2", "q3"], original_query="orig")
        # same ids across queries collapse to unique chunks
        ids = [r["id"] for r in results]
        assert len(ids) == len(set(ids))
        assert results

    def test_retrieve_multi_fallback_when_empty(self, patch_rag):
        rb = build(patch_rag, FakeStore(empty=True))
        ctx, results = rb.retrieve_multi(["q1"], original_query="orig")
        assert results == []
