"""
Unit tests for llm.utils.parameter_inference.ParameterInferenceEngine.

Pure keyword/heuristic inference — deterministic, offline.
"""

from __future__ import annotations

import pytest

from llm.utils.parameter_inference import ParameterInferenceEngine, infer_parameters


@pytest.fixture
def eng():
    return ParameterInferenceEngine()


class TestInferOS:
    @pytest.mark.parametrize("q,needle", [
        ("Ubuntu 22.04'te SSH nasıl yapılandırılır?", "ubuntu"),
        ("Windows Server 2022 firewall ayarları", "windows"),
        ("CentOS 9 hardening", "centos"),
        ("Debian sunucu güvenliği", "debian"),
    ])
    def test_os_detected(self, eng, q, needle):
        assert needle in eng.infer_os(q).lower()

    def test_os_default_when_unknown(self, eng):
        assert eng.infer_os("genel güvenlik sorusu", default="ubuntu_22_04") == "ubuntu_22_04"


class TestInferRole:
    @pytest.mark.parametrize("q,needle", [
        ("Developer olarak SSH key nasıl yönetilir?", "developer"),
        ("kubernetes ve terraform altyapı yönetimi", "devops"),
        ("incident response, threat ve vulnerability audit", "security"),
    ])
    def test_role_detected(self, eng, q, needle):
        assert eng.infer_role(q).lower() == needle

    def test_role_default(self, eng):
        assert eng.infer_role("merhaba", default="sysadmin") == "sysadmin"


class TestInferSecurityLevel:
    def test_returns_valid_level(self, eng):
        # infer_security_level requires a role argument
        lvl = eng.infer_security_level("maksimum sıkı strict güvenlik istiyorum", role="security")
        assert lvl in {"minimal", "balanced", "strict"}

    def test_role_based_default(self, eng):
        lvl = eng.infer_security_level("normal bir kurulum", role="sysadmin")
        assert lvl in {"minimal", "balanced", "strict"}


class TestInferAll:
    def test_returns_dict_with_keys(self, eng):
        params = eng.infer_all("Ubuntu 24.04 sysadmin için strict SSH hardening")
        assert isinstance(params, dict)
        for key in ("os", "role", "security_level"):
            assert key in params
        assert "ubuntu" in params["os"].lower()


class TestModuleHelper:
    def test_infer_parameters_helper(self):
        result = infer_parameters("Windows 11 developer balanced firewall")
        assert isinstance(result, dict)
        assert "os" in result
