"""
Unit tests for rag.verify.claim_verifier.ClaimVerifier (hallucination control).

LLM is faked. We test the confidence math, the is_valid threshold, the
empty-input shortcuts and the conservative parse-error fallback.
"""

from __future__ import annotations

from rag.verify.claim_verifier import ClaimVerifier, VerificationResult


CHUNKS = [
    {"text": "PermitRootLogin no disables direct root SSH login.", "metadata": {}},
    {"text": "Set Port 2222 in /etc/ssh/sshd_config to change the SSH port.", "metadata": {}},
]


class _ScriptedLLM:
    """Returns claim-extraction JSON first, then a verdict per claim."""

    def __init__(self, claims, verdicts):
        self._claims_json = "[" + ", ".join(f'"{c}"' for c in claims) + "]"
        self._verdicts = list(verdicts)
        self._calls = 0

    def __call__(self, prompt: str) -> str:
        self._calls += 1
        if self._calls == 1:
            return self._claims_json  # extraction call
        verdict = self._verdicts.pop(0) if self._verdicts else True
        return '{"supported": %s, "reason": "x"}' % ("true" if verdict else "false")


class TestShortCircuits:
    def test_no_chunks_is_valid(self):
        v = ClaimVerifier(llm_fn=lambda _p: "[]")
        res = v.verify("some answer", [])
        assert res.is_valid and res.confidence == 1.0

    def test_no_claims_is_valid(self):
        v = ClaimVerifier(llm_fn=lambda _p: "[]")  # extraction returns empty list
        res = v.verify("some answer", CHUNKS)
        assert res.is_valid and res.confidence == 1.0


class TestConfidence:
    def test_all_supported_high_confidence(self):
        llm = _ScriptedLLM(claims=["PermitRootLogin no", "Port 2222"], verdicts=[True, True])
        v = ClaimVerifier(llm_fn=llm, min_confidence=0.6)
        res = v.verify("answer", CHUNKS)
        assert res.confidence == 1.0
        assert res.is_valid
        assert res.unsupported == []

    def test_half_unsupported_below_threshold(self):
        llm = _ScriptedLLM(claims=["claim a", "claim b"], verdicts=[True, False])
        v = ClaimVerifier(llm_fn=llm, min_confidence=0.6)
        res = v.verify("answer", CHUNKS)
        assert res.confidence == 0.5
        assert res.is_valid is False
        assert len(res.unsupported) == 1

    def test_max_claims_cap(self):
        claims = [f"claim {i}" for i in range(10)]
        llm = _ScriptedLLM(claims=claims, verdicts=[True] * 10)
        v = ClaimVerifier(llm_fn=llm, max_claims=3)
        res = v.verify("answer", CHUNKS)
        # only up to max_claims are checked
        assert len(res.claims) == 3


class TestFallbacks:
    def test_extraction_failure_returns_valid(self):
        def boom(_):
            raise RuntimeError("down")

        v = ClaimVerifier(llm_fn=boom)
        res = v.verify("answer", CHUNKS)
        # extraction failed -> no claims -> treated valid
        assert res.is_valid

    def test_unparseable_verdict_is_supported(self):
        calls = {"n": 0}

        def llm(_prompt):
            calls["n"] += 1
            if calls["n"] == 1:
                return '["only claim"]'
            return "not json at all"  # verdict unparseable -> conservative supported

        v = ClaimVerifier(llm_fn=llm)
        res = v.verify("answer", CHUNKS)
        assert res.confidence == 1.0
        assert res.is_valid

    def test_returns_verification_result_type(self):
        v = ClaimVerifier(llm_fn=lambda _p: "[]")
        assert isinstance(v.verify("a", []), VerificationResult)
