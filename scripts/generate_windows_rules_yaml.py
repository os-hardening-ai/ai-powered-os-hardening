"""
Windows 11 CIS kural JSON'larını ubuntu_24_04_rules.yaml formatında
windows_2025_rules.yaml'a dönüştürür.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import yaml

RULES_DIR = Path("KURALLAR/KURALLAR/platforms/windows/rules")
OUTPUT_FILE = Path("data/rules/windows_2025_rules.yaml")

SECTION_DIRS = [
    "S1_Account_Policies",
    "S2_Local_Policies",
    "S5_System_Services",
    "S9_Windows_Firewall",
    "S17_Advanced_Audit_Policy",
    "S18_Administrative_Templates",
    "S19_Administrative_Templates_User",
]


def _section_from_id(rule_id: str) -> str:
    parts = rule_id.split(".")
    return ".".join(parts[:-1]) if len(parts) > 1 else rule_id


def _build_audit_script(rule: dict) -> str:
    rule_id = rule.get("rule_id", "")
    title = rule.get("title", "")
    audit_ps = (rule.get("audit_logic") or {}).get("powershell_script", "")

    lines = [
        f"# CIS {rule_id} Audit - {title}",
        "# Exit codes: 0=PASS, 1=FAIL, 2=NOT_APPLICABLE",
        "",
        "#Requires -RunAsAdministrator",
        "",
    ]

    if audit_ps:
        # Satır sonlarını normalize et
        audit_ps = audit_ps.replace("\r\n", "\n").replace("\r", "\n")
        lines.append("$auditResult = & {")
        lines.append(audit_ps)
        lines.append("}")
        lines.append("")
        lines.append("if ($auditResult -eq $true) {")
        lines.append(f'    Write-Output "[PASS] Rule {rule_id}: Compliant"')
        lines.append("    exit 0")
        lines.append("} elseif ($null -eq $auditResult) {")
        lines.append(f'    Write-Output "[INFO] Rule {rule_id}: Not applicable on this system"')
        lines.append("    exit 2")
        lines.append("} else {")
        lines.append(f'    Write-Output "[FAIL] Rule {rule_id}: Not compliant"')
        lines.append("    exit 1")
        lines.append("}")
    else:
        lines.append(f'Write-Output "[INFO] Rule {rule_id}: No automated audit available"')
        lines.append("exit 2")

    return "\n".join(lines)


def _build_remediation_script(rule: dict) -> str:
    rule_id = rule.get("rule_id", "")
    title = rule.get("title", "")
    impl = rule.get("implementation_local") or {}
    ps_script = impl.get("powershell_script", "")
    ps_command = impl.get("powershell_command", "")

    lines = [
        f"# CIS {rule_id} Remediation - {title}",
        "",
        "#Requires -RunAsAdministrator",
        "",
        f'Write-Output "[REMEDIATE] Applying rule {rule_id}..."',
        "",
    ]

    if ps_script:
        ps_script = ps_script.replace("\r\n", "\n").replace("\r", "\n")
        lines.append("try {")
        lines.append(ps_script)
        lines.append(f'    Write-Output "[SUCCESS] Rule {rule_id}: Applied"')
        lines.append("} catch {")
        lines.append(f'    Write-Output "[ERROR] Rule {rule_id}: $($_.Exception.Message)"')
        lines.append("    exit 1")
        lines.append("}")
    elif ps_command:
        lines.append("try {")
        lines.append(f"    {ps_command}")
        lines.append(f'    Write-Output "[SUCCESS] Rule {rule_id}: Applied"')
        lines.append("} catch {")
        lines.append(f'    Write-Output "[ERROR] Rule {rule_id}: $($_.Exception.Message)"')
        lines.append("    exit 1")
        lines.append("}")
    else:
        lines.append(f'Write-Output "[INFO] Rule {rule_id}: Manual remediation required"')
        lines.append('Write-Output "[INFO] See CIS Benchmark for guidance"')

    return "\n".join(lines)


def _config_files(rule: dict) -> list[str]:
    files: list[str] = []
    reg = rule.get("registry_config")
    if reg and reg.get("path"):
        path = reg["path"].replace("\\\\", "\\")
        files.append(path)
    gpo = rule.get("gpo_config")
    if gpo and gpo.get("policy_path"):
        files.append(gpo["policy_path"])
    return files or ["N/A"]


def _audit_command(rule: dict) -> str:
    audit_ps = (rule.get("audit_logic") or {}).get("powershell_script", "")
    if not audit_ps:
        return ""
    # İlk satırı al, normalize et
    first_line = audit_ps.replace("\r\n", "\n").split("\n")[0].strip()
    return first_line[:200] if first_line else ""


def _remediation_command(rule: dict) -> str:
    impl = rule.get("implementation_local") or {}
    cmd = impl.get("powershell_command") or ""
    if cmd:
        return cmd[:200]
    ps = impl.get("powershell_script") or ""
    if ps:
        first = ps.replace("\r\n", "\n").split("\n")[0].strip()
        return first[:200]
    return ""


def _script_path(section_dir: str, rule_id: str, script_type: str) -> str:
    return f"KURALLAR/KURALLAR/platforms/windows/rules/{section_dir}/{rule_id}/{script_type}.ps1"


def load_rules_from_dir(section_dir: str) -> list[dict]:
    dir_path = RULES_DIR / section_dir
    rules = []
    for json_file in sorted(dir_path.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8-sig"))
            rules.append(data)
        except Exception as e:
            print(f"[WARN] {json_file.name} okunamadi: {e}")
    return rules


def convert_rule(raw: dict, section_dir: str) -> dict:
    rule_id = raw.get("rule_id", "")
    impl = raw.get("implementation_local") or {}
    gpo = raw.get("gpo_config") or {}
    reg = raw.get("registry_config") or {}

    rule: dict = {
        "id": rule_id,
        "section": _section_from_id(rule_id),
        "category": raw.get("category", "") + (
            f" - {raw['subcategory']}" if raw.get("subcategory") else ""
        ),
        "title": raw.get("title", ""),
        "description": raw.get("description", ""),
        "level": raw.get("cis_level", 1),
        "auto_remediate": raw.get("automated", False),
        "manual_review": not raw.get("automated", False),
        "config_files": _config_files(raw),
        "audit_command": _audit_command(raw),
        "remediation_command": _remediation_command(raw),
        "audit_script": _script_path(section_dir, rule_id, "audit"),
        "remediation_script": _script_path(section_dir, rule_id, "remediation"),
        "audit_script_content": _build_audit_script(raw),
        "remediation_script_content": _build_remediation_script(raw),
        "tags": raw.get("tags", []),
    }

    # Registry path varsa ekle
    if reg.get("path"):
        rule["registry_path"] = reg["path"].replace("\\\\", "\\")
        rule["registry_value"] = reg.get("value_name", "")

    # GPO setting varsa ekle
    if gpo.get("setting_name"):
        rule["policy_setting"] = gpo["setting_name"]
        rule["gpo_path"] = gpo.get("policy_path", "")

    # Requires reboot
    if impl.get("requires_reboot"):
        rule["requires_reboot"] = True

    return rule


def main() -> None:
    all_rules: list[dict] = []

    for section_dir in SECTION_DIRS:
        raw_rules = load_rules_from_dir(section_dir)
        print(f"[{section_dir}] {len(raw_rules)} kural yuklendi")
        for raw in raw_rules:
            all_rules.append(convert_rule(raw, section_dir))

    auto_count = sum(1 for r in all_rules if r["auto_remediate"])
    manual_count = sum(1 for r in all_rules if r["manual_review"])
    with_remediation = sum(
        1 for r in all_rules if r.get("remediation_script_content", "")
    )

    output = {
        "metadata": {
            "os": "windows_11",
            "benchmark": "CIS Microsoft Windows 11 Stand-alone Benchmark",
            "benchmark_version": "v4.0.0",
            "generated": str(date.today()),
            "total_rules": len(all_rules),
            "auto_remediate_count": auto_count,
            "manual_review_count": manual_count,
            "with_remediation": with_remediation,
            "description": (
                "CIS Microsoft Windows 11 Stand-alone Benchmark v4.0.0 security hardening rules. "
                "Her kural: title, description, registry_path/policy_setting, config_files, "
                "audit/remediation PowerShell script icerikleri ve tags icermektedir."
            ),
        },
        "rules": all_rules,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        yaml.dump(
            output,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=120,
        )

    print(f"\n[DONE] {len(all_rules)} kural yazildi -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
