"""
Unit tests for domain.artifact_generator.ArtifactGenerator

Covers all five formats (bash, powershell, ansible, reg, gpo), rule_count
accounting, warnings for rules lacking remediation data, and the error path
for an unsupported format.

No network / external services required — uses synthetic rule dicts.
"""

from __future__ import annotations

import pytest

from domain.artifact_generator.generator import ArtifactGenerator, Artifact


@pytest.fixture
def gen():
    return ArtifactGenerator()


@pytest.fixture
def linux_rules():
    return [
        {
            "id": "5.2.1",
            "title": "Set sshd permissions",
            "remediation_script_content": "chmod 600 /etc/ssh/sshd_config",
        },
        {
            "id": "1.1.2",
            "title": "Configure /tmp",
            "remediation_command": "systemctl enable tmp.mount",
        },
        {
            "id": "9.9.9",
            "title": "Manual-only rule",
            # no remediation -> should be skipped/flagged
        },
    ]


@pytest.fixture
def windows_rules():
    return [
        {
            "id": "1.1.1",
            "title": "Password length",
            "registry_path": r"HKLM\SOFTWARE\Policies\Test",
            "registry_value": '"MinLen"=dword:0000000e',
            "remediation_script_content": "Set-Item X 14",
            "description": "Require 14-char passwords.",
            "level": 1,
            "tags": ["account", "password"],
            "category": "account_policy",
        },
    ]


class TestDispatch:
    def test_unsupported_format_raises(self, gen, linux_rules):
        with pytest.raises(ValueError):
            gen.generate(linux_rules, "yaml")  # type: ignore[arg-type]

    def test_returns_artifact_dataclass(self, gen, linux_rules):
        art = gen.generate(linux_rules, "bash")
        assert isinstance(art, Artifact)
        assert art.format == "bash"
        assert art.os_target == "ubuntu_24_04"


class TestBash:
    def test_bash_has_shebang_and_safety(self, gen, linux_rules):
        art = gen.generate(linux_rules, "bash")
        assert art.content.startswith("#!/usr/bin/env bash")
        assert "set -euo pipefail" in art.content

    def test_bash_includes_remediation_and_counts(self, gen, linux_rules):
        art = gen.generate(linux_rules, "bash")
        assert "chmod 600 /etc/ssh/sshd_config" in art.content
        assert "systemctl enable tmp.mount" in art.content
        # 2 rules with remediation, 1 skipped
        assert art.rule_count == 2
        assert any("9.9.9" in w for w in art.warnings)


class TestPowerShell:
    def test_powershell_admin_header(self, gen, windows_rules):
        art = gen.generate(windows_rules, "powershell", os_target="windows_11")
        assert art.content.startswith("#Requires -RunAsAdministrator")
        assert "Set-Item X 14" in art.content
        assert art.rule_count == 1


class TestAnsible:
    def test_ansible_is_valid_playbook_shape(self, gen, linux_rules):
        art = gen.generate(linux_rules, "ansible")
        assert art.content.startswith("---")
        assert "hosts: all" in art.content
        assert "become: yes" in art.content
        assert art.rule_count == 2

    def test_ansible_is_yaml_parseable_with_two_tasks(self, gen, linux_rules):
        import yaml
        art = gen.generate(linux_rules, "ansible")
        parsed = yaml.safe_load(art.content)
        assert isinstance(parsed, list)
        play = parsed[0]
        assert play["hosts"] == "all"
        # One play, each remediated rule is a task (2 of 3 rules have remediation)
        assert len(play["tasks"]) == 2


class TestReg:
    def test_reg_header_and_entries(self, gen, windows_rules):
        art = gen.generate(windows_rules, "reg", os_target="windows_11")
        assert art.content.startswith("Windows Registry Editor Version 5.00")
        assert r"[HKLM\SOFTWARE\Policies\Test]" in art.content
        assert art.rule_count == 1

    def test_reg_empty_when_no_registry_fields(self, gen, linux_rules):
        art = gen.generate(linux_rules, "reg")
        assert art.rule_count == 0
        assert "No registry entries" in art.content


class TestGpo:
    def test_gpo_summary_lists_rule_metadata(self, gen, windows_rules):
        art = gen.generate(windows_rules, "gpo", os_target="windows_11")
        assert "1.1.1: Password length" in art.content
        assert "CIS Level" in art.content
        assert art.rule_count == 1
