"""
Unit tests for llm.pipelines.layers.zt_enrichment.ZeroTrustEnricher.

LLM is faked. Covers JSON parsing, markdown unwrapping, standards filtering,
impact normalisation and the OS-/security-level-aware fallback path.
"""

from __future__ import annotations

import json

from llm.core.context import RequestContext
from llm.pipelines.layers.zt_enrichment import ZeroTrustEnricher, ZTEnrichment


def ctx(**kw):
    return RequestContext(user_question=kw.pop("q", "SSH hardening"), **kw)


VALID_JSON = json.dumps({
    "zt_principles": ["least_privilege", "strong_identity"],
    "standards": ["CIS_Ubuntu_22_04:5.2.5", "NIST_800-53:AC-17", "no_colon_dropped"],
    "impact_level": "HIGH",
    "rollback_approach": "Backup sshd_config then restore.",
    "reasoning": "Disabling root login follows least_privilege.",
})


class TestParsing:
    def test_valid_json_parsed(self):
        enr = ZeroTrustEnricher(llm=lambda _p: VALID_JSON).enrich(ctx(os="ubuntu_24_04"))
        assert enr.zt_principles == ["least_privilege", "strong_identity"]
        # entry without ":" is filtered out
        assert "no_colon_dropped" not in enr.standards
        assert "CIS_Ubuntu_22_04:5.2.5" in enr.standards
        # impact normalised to lowercase
        assert enr.impact_level == "high"

    def test_markdown_wrapped_json(self):
        wrapped = "```json\n" + VALID_JSON + "\n```"
        enr = ZeroTrustEnricher(llm=lambda _p: wrapped).enrich(ctx())
        assert enr.impact_level == "high"
        assert enr.rollback_approach

    def test_invalid_impact_defaults_medium(self):
        bad = json.dumps({"zt_principles": [], "standards": [], "impact_level": "ultra"})
        enr = ZeroTrustEnricher(llm=lambda _p: bad).enrich(ctx())
        assert enr.impact_level == "medium"

    def test_missing_fields_get_defaults(self):
        enr = ZeroTrustEnricher(llm=lambda _p: "{}").enrich(ctx())
        assert enr.rollback_approach  # non-empty default
        assert enr.reasoning


class TestFallback:
    def test_llm_exception_uses_fallback(self):
        def boom(_):
            raise RuntimeError("down")

        enr = ZeroTrustEnricher(llm=boom).enrich(ctx(os="ubuntu_24_04"))
        assert "least_privilege" in enr.zt_principles
        assert any("Ubuntu" in s for s in enr.standards)

    def test_fallback_windows_standards(self):
        enr = ZeroTrustEnricher(llm=lambda _p: "not json").enrich(ctx(os="windows_11"))
        assert any("Windows" in s for s in enr.standards)

    def test_fallback_impact_by_security_level(self):
        strict = ZeroTrustEnricher(lambda _p: "x").enrich(ctx(security_level="strict"))
        minimal = ZeroTrustEnricher(lambda _p: "x").enrich(ctx(security_level="minimal"))
        assert strict.impact_level == "high"
        assert minimal.impact_level == "low"

    def test_returns_dataclass(self):
        enr = ZeroTrustEnricher(lambda _p: "{}").enrich(ctx())
        assert isinstance(enr, ZTEnrichment)
