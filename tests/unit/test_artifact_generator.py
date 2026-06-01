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
        import yaml
        art = gen.generate(linux_rules, "ansible")
        assert art.content.startswith("---")
        play = yaml.safe_load(art.content)[0]
        assert play["hosts"] == "all"
        assert play["become"] is True   # safe_dump → 'become: true'
        assert art.rule_count == 2

    def test_ansible_handles_invalid_surrogate_chars(self, gen):
        # REGRESYON: rule içeriğinde lone surrogate (#xDC90) → eskiden YAML parse PATLIYORDU.
        import yaml
        bad = [{"id": "5.1.4", "title": "ssh\udc90 access",
                "remediation_command": "echo bad\udc90char >> /etc/ssh/sshd_config"}]
        art = gen.generate(bad, "ansible")
        parsed = yaml.safe_load(art.content)   # patlamamalı
        assert parsed[0]["tasks"][0]["ansible.builtin.shell"]  # temizlenmiş içerik var
        assert "\udc90" not in art.content     # surrogate çıkarıldı

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


@pytest.fixture
def sshd_rules():
    """Gerçek CIS YAML kurallarını taklit eder: her birinde gömülü shebang + (5.1.4'te)
    fonksiyon-dışı `return` + kural başına `systemctl reload sshd`. Eski birleştirici bunları
    olduğu gibi yapıştırıyordu (20 shebang, 19 reload, `return` ile set -e patlaması)."""
    return [
        {"id": "5.1.4", "title": "sshd access", "config_files": ["/etc/ssh/sshd_config"],
         "remediation_script_content":
             "#!/bin/bash\necho configuring\n"
             "if grep -q AllowGroups /etc/ssh/sshd_config; then\n  echo done\n  return 0\nfi\n"
             "echo 'AllowGroups sudo' >> /etc/ssh/sshd_config\nsystemctl reload sshd"},
        {"id": "5.1.20", "title": "PermitRootLogin", "config_files": ["/etc/ssh/sshd_config"],
         "remediation_script_content":
             "#!/bin/bash\nsed -i '/^PermitRootLogin/d' /etc/ssh/sshd_config\n"
             "echo 'PermitRootLogin no' >> /etc/ssh/sshd_config\nsystemctl reload sshd"},
    ]


class TestBashProductionGrade:
    """Agent (/api/agent/harden) artifact'i best-practice: tek shebang, tek reload+doğrulama,
    yedek, fonksiyon-wrap (return-safe)."""

    def test_single_shebang_no_embedded(self, gen, sshd_rules):
        c = gen.generate(sshd_rules, "bash").content
        assert c.count("#!/usr/bin/env bash") == 1   # yalnız 1 shebang (başta)
        assert "#!/bin/bash" not in c                # gömülü shebang'ler temizlendi

    def test_reload_deduped_once_with_sshd_t_guard(self, gen, sshd_rules):
        c = gen.generate(sshd_rules, "bash").content
        assert c.count("systemctl reload sshd") == 1  # 2 kural → TEK reload (19× değil)
        assert "sshd -t" in c                          # reload ÖNCESİ config doğrulama (kilitlenme önlenir)

    def test_single_backup_of_config_files(self, gen, sshd_rules):
        c = gen.generate(sshd_rules, "bash").content
        assert c.count('cp -a "/etc/ssh/sshd_config"') == 1  # tek yedek (dedup)
        assert "BACKUP_DIR" in c

    def test_rules_wrapped_in_functions_return_safe(self, gen, sshd_rules):
        c = gen.generate(sshd_rules, "bash").content
        assert "apply_5_1_4()" in c and "apply_5_1_20()" in c
        assert "return 0" in c   # korundu — artık FONKSİYON içinde → geçerli (eskiden set -e patlatıyordu)

    @pytest.mark.skipif(not __import__("shutil").which("bash"), reason="bash yok")
    def test_generated_bash_is_syntactically_valid(self, gen, sshd_rules):
        import subprocess
        c = gen.generate(sshd_rules, "bash").content
        r = subprocess.run(["bash", "-n"], input=c, capture_output=True,
                           text=True, encoding="utf-8")
        assert r.returncode == 0, f"bash -n syntax hatası:\n{r.stderr}"


class TestSanitizeRemediation:
    def test_strips_shebang_and_extracts_reload(self):
        body, reloads = ArtifactGenerator._sanitize_remediation(
            "#!/bin/bash\necho hi\nsystemctl reload sshd")
        assert "#!" not in body and "echo hi" in body
        assert reloads == ["systemctl reload sshd"]

    def test_dedups_reload_and_keeps_enable(self):
        body, reloads = ArtifactGenerator._sanitize_remediation(
            "systemctl reload sshd\nsystemctl enable foo\nsystemctl reload sshd")
        assert reloads == ["systemctl reload sshd"]      # reload tek + dedup
        assert "systemctl enable foo" in body            # enable reload DEĞİL → gövdede kalır
