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
    """Returns claim-extraction JSON first, then a verdict per claim.

    Thread-safe: per-claim checks now run concurrently, so the call counter
    and verdict queue are guarded by a lock. Verdict order across claims is
    non-deterministic under parallelism, but the assertions that use this
    fake only depend on the multiset of verdicts (confidence / unsupported
    count), not on which claim got which verdict.
    """

    def __init__(self, claims, verdicts):
        import threading
        self._claims_json = "[" + ", ".join(f'"{c}"' for c in claims) + "]"
        self._verdicts = list(verdicts)
        self._calls = 0
        self._lock = threading.Lock()

    def __call__(self, prompt: str) -> str:
        with self._lock:
            self._calls += 1
            is_extraction = self._calls == 1
            if is_extraction:
                return self._claims_json  # extraction call (always first, sequential)
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
    # NOT: iddialar gerçek cümle olmalı — _filter_claims kısa/tek-kelime parçaları eler.
    def test_all_supported_high_confidence(self):
        llm = _ScriptedLLM(claims=["PermitRootLogin no disables direct root login",
                                   "Port 2222 changes the SSH listening port"],
                           verdicts=[True, True])
        v = ClaimVerifier(llm_fn=llm, min_confidence=0.6)
        res = v.verify("answer", CHUNKS)
        assert res.confidence == 1.0
        assert res.is_valid
        assert res.unsupported == []

    def test_half_unsupported_below_threshold(self):
        llm = _ScriptedLLM(claims=["the first hardening claim about ssh config",
                                   "the second hardening claim about ports"],
                           verdicts=[True, False])
        v = ClaimVerifier(llm_fn=llm, min_confidence=0.6)
        res = v.verify("answer", CHUNKS)
        assert res.confidence == 0.5
        assert res.is_valid is False
        assert len(res.unsupported) == 1

    def test_max_claims_cap(self):
        claims = [f"hardening claim number {i} about a config value" for i in range(10)]
        llm = _ScriptedLLM(claims=claims, verdicts=[True] * 10)
        v = ClaimVerifier(llm_fn=llm, max_claims=3)
        res = v.verify("answer", CHUNKS)
        # only up to max_claims are checked
        assert len(res.claims) == 3


class _PartialLLM:
    """1. çağrı extraction; sonraki çağrılar YENİ formatta {"support": yes|partial|no}."""

    def __init__(self, claims, supports):
        import threading
        self._claims_json = "[" + ", ".join(f'"{c}"' for c in claims) + "]"
        self._supports = list(supports)
        self._n = 0
        self._lock = threading.Lock()

    def __call__(self, prompt: str) -> str:
        with self._lock:
            self._n += 1
            if self._n == 1:
                return self._claims_json
            val = self._supports.pop(0) if self._supports else "yes"
        return '{"support": "%s", "reason": "x"}' % val


class TestPartialCredit:
    """Kısmi kredi (0/0.5/1) → kalibre groundedness; yapay-düşük skoru önler."""

    def test_partial_gives_half_credit(self):
        # tam + kısmi → (1.0 + 0.5)/2 = 0.75 (binary olsaydı 0.5'e düşerdi)
        llm = _PartialLLM(claims=["ssh permitrootlogin no directive is recommended",
                                  "ssh maxauthtries should be a low value"],
                          supports=["yes", "partial"])
        res = ClaimVerifier(llm_fn=llm, min_confidence=0.6).verify("answer", CHUNKS)
        assert res.confidence == 0.75
        assert res.is_valid is True               # 0.75 >= 0.6
        assert res.unsupported == []              # partial desteksiz SAYILMAZ

    def test_no_support_counts_as_unsupported(self):
        llm = _PartialLLM(claims=["a real claim about ssh hardening config",
                                  "another real claim about port settings"],
                          supports=["yes", "no"])
        res = ClaimVerifier(llm_fn=llm, min_confidence=0.6).verify("answer", CHUNKS)
        assert res.confidence == 0.5              # (1.0 + 0.0)/2
        assert len(res.unsupported) == 1

    def test_all_partial(self):
        llm = _PartialLLM(claims=["first multiword hardening claim here",
                                  "second multiword hardening claim here"],
                          supports=["partial", "partial"])
        res = ClaimVerifier(llm_fn=llm, min_confidence=0.6).verify("answer", CHUNKS)
        assert res.confidence == 0.5              # her ikisi 0.5
        # kısmi → "supported" (score>=0.5) ama unsupported listesinde değil
        assert res.unsupported == []

    def test_support_score_recorded(self):
        llm = _PartialLLM(claims=["one genuine multiword claim about config"],
                          supports=["partial"])
        res = ClaimVerifier(llm_fn=llm).verify("answer", CHUNKS)
        assert res.claims[0].support_score == 0.5
        assert res.claims[0].supported is True    # 0.5 >= 0.5

    def test_support_to_score_helper(self):
        from rag.verify.claim_verifier import _support_to_score
        assert _support_to_score({"support": "yes"}) == 1.0
        assert _support_to_score({"support": "partial"}) == 0.5
        assert _support_to_score({"support": "no"}) == 0.0
        # eski format geriye uyumlu
        assert _support_to_score({"supported": True}) == 1.0
        assert _support_to_score({"supported": False}) == 0.0
        # belirsiz → conservative 1.0
        assert _support_to_score({}) == 1.0


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


class _RecordingLLM:
    """Prompt'ları kaydeder; 1. çağrı extraction (claims JSON), sonrası 'supported:true'."""

    def __init__(self, claims):
        import threading
        self.prompts = []
        self._claims_json = "[" + ", ".join(f'"{c}"' for c in claims) + "]"
        self._n = 0
        self._lock = threading.Lock()

    def __call__(self, prompt: str) -> str:
        with self._lock:
            self.prompts.append(prompt)
            self._n += 1
            first = self._n == 1
        return self._claims_json if first else '{"supported": true, "reason": "x"}'


class TestFilterClaims:
    """_filter_claims: teşhiste görülen '/etc','1','3','CIS Benchmark' çöpünü eler."""

    def test_drops_fragments_numbers_and_short(self):
        from rag.verify.claim_verifier import _filter_claims
        out = _filter_claims(["/etc", "CIS Benchmark", "1", "3", "...",
                              "PermitRootLogin should be set to no"])
        assert out == ["PermitRootLogin should be set to no"]

    def test_keeps_real_multiword_claims(self):
        from rag.verify.claim_verifier import _filter_claims
        claims = ["ufw default deny incoming should be enabled",
                  "PASS_MAX_DAYS must be 365 days or less"]
        assert _filter_claims(claims) == claims

    def test_single_long_word_dropped(self):
        from rag.verify.claim_verifier import _filter_claims
        assert _filter_claims(["antidisestablishmentarianism"]) == []  # uzun ama tek kelime

    def test_empty(self):
        from rag.verify.claim_verifier import _filter_claims
        assert _filter_claims([]) == []


class TestCitationStripping:
    def test_citation_markers_removed_before_extraction(self):
        llm = _RecordingLLM(["a complete verifiable claim about ssh hardening"])
        ClaimVerifier(llm_fn=llm).verify(
            "Use PermitRootLogin no [1] and set Port 2222 [3] per CIS.", CHUNKS)
        extraction_prompt = llm.prompts[0]
        assert "[1]" not in extraction_prompt and "[3]" not in extraction_prompt


class TestConfigurableContextWindow:
    def test_smaller_window_yields_shorter_check_prompt(self):
        chunks = [{"text": "A" * 3000, "metadata": {}}, {"text": "B" * 3000, "metadata": {}}]
        claim = ["a genuine multiword claim about hardening configuration"]
        small = _RecordingLLM(list(claim))
        ClaimVerifier(llm_fn=small, max_chunk_chars=4000, max_context_chars=1500).verify("ans", chunks)
        big = _RecordingLLM(list(claim))
        ClaimVerifier(llm_fn=big, max_chunk_chars=4000, max_context_chars=5000).verify("ans", chunks)
        # 2. prompt = iddia denetimi; küçük pencere → daha kısa bağlam → daha kısa prompt
        assert len(small.prompts[1]) < len(big.prompts[1])

    def test_defaults_are_configurable(self):
        v = ClaimVerifier(llm_fn=lambda _p: "[]")
        assert v.max_chunk_chars == 600 and v.max_context_chars == 4000
