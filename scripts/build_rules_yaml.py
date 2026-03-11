#!/usr/bin/env python3
"""
KURALLAR klasöründeki audit/remediation script'lerini tarayarak
data/rules/ubuntu_24_04_rules.yaml dosyasını oluşturur.

RAG için zenginleştirilmiş format:
  - Tam script içerikleri
  - SSH direktif adları ve beklenen değerler
  - Config dosya yolları
  - Ana audit/remediation komutları
  - Detaylı tag'ler

Kullanim:
    cd ai-powered-os-hardening
    python scripts/build_rules_yaml.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from datetime import date
from collections import Counter

try:
    import yaml
except ImportError:
    print("PyYAML gerekli: pip install pyyaml")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────────────────────────

BASE_DIR    = Path(__file__).resolve().parent.parent
RULES_DIR   = BASE_DIR / "KURALLAR" / "KURALLAR" / "platforms" / "linux" / "ubuntu" / "desktop" / "rules"
DONT_DIR    = BASE_DIR / "KURALLAR" / "KURALLAR" / "dontremediate" / "ubuntudont"
OUTPUT_FILE = BASE_DIR / "data" / "rules" / "ubuntu_24_04_rules.yaml"


# ──────────────────────────────────────────────────────────────────
# SECTION METADATA
# ──────────────────────────────────────────────────────────────────

SECTION_MAP = {
    "1": "Initial Setup and Filesystem Configuration",
    "2": "Software and Service Configuration",
    "3": "Network Configuration",
    "4": "Logging and Auditing",
    "5": "Access Authentication and Authorization",
    "6": "System Maintenance",
    "7": "Security Patching and Updates",
}

# Section -> base tags
SECTION_BASE_TAGS: dict[str, list[str]] = {
    "1": ["filesystem", "kernel_module", "initial_setup"],
    "2": ["services", "software", "daemon"],
    "3": ["network", "ipv4", "ipv6", "firewall"],
    "4": ["logging", "auditing", "syslog", "auditd"],
    "5": ["access_control", "authentication", "authorization"],
    "6": ["file_permissions", "system_maintenance", "integrity"],
    "7": ["patching", "updates", "package_management"],
}

# SSH directives -> extra tags
SSH_DIRECTIVE_TAGS: dict[str, list[str]] = {
    "PermitRootLogin":           ["ssh", "root_login", "privilege_escalation"],
    "PermitEmptyPasswords":      ["ssh", "password", "empty_password"],
    "MaxAuthTries":              ["ssh", "brute_force", "authentication"],
    "MaxSessions":               ["ssh", "session_limit"],
    "MaxStartups":               ["ssh", "dos_protection", "connection_limit"],
    "LoginGraceTime":            ["ssh", "timeout", "authentication"],
    "GSSAPIAuthentication":      ["ssh", "kerberos", "gssapi"],
    "KerberosAuthentication":    ["ssh", "kerberos"],
    "HostbasedAuthentication":   ["ssh", "hostbased"],
    "IgnoreRhosts":              ["ssh", "rhosts", "legacy_auth"],
    "PermitUserEnvironment":     ["ssh", "environment", "privilege_escalation"],
    "UsePAM":                    ["ssh", "pam", "authentication"],
    "DisableForwarding":         ["ssh", "port_forwarding", "x11"],
    "LogLevel":                  ["ssh", "logging", "audit_trail"],
    "Banner":                    ["ssh", "banner", "legal_notice"],
    "Ciphers":                   ["ssh", "encryption", "cipher", "crypto"],
    "MACs":                      ["ssh", "mac", "integrity", "crypto"],
    "KexAlgorithms":             ["ssh", "key_exchange", "crypto"],
    "AllowUsers":                ["ssh", "access_control", "user_restriction"],
    "AllowGroups":               ["ssh", "access_control", "group_restriction"],
    "DenyUsers":                 ["ssh", "access_control", "user_restriction"],
    "DenyGroups":                ["ssh", "access_control", "group_restriction"],
}

# Kernel modules -> extra tags
MODULE_TAGS: dict[str, list[str]] = {
    "cramfs":   ["cramfs", "unused_filesystem"],
    "freevxfs": ["freevxfs", "unused_filesystem"],
    "hfs":      ["hfs", "unused_filesystem"],
    "hfsplus":  ["hfsplus", "unused_filesystem"],
    "jffs2":    ["jffs2", "unused_filesystem"],
    "squashfs": ["squashfs", "unused_filesystem"],
    "udf":      ["udf", "unused_filesystem"],
    "usb-storage": ["usb", "removable_media"],
    "dccp":     ["dccp", "unused_protocol", "network"],
    "sctp":     ["sctp", "unused_protocol", "network"],
    "rds":      ["rds", "unused_protocol", "network"],
    "tipc":     ["tipc", "unused_protocol", "network"],
}


# ──────────────────────────────────────────────────────────────────
# SCRIPT CONTENT HELPERS
# ──────────────────────────────────────────────────────────────────

def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return ""


def extract_title(audit_content: str) -> str:
    """audit.sh içinden CIS kural başlığını çıkar."""
    patterns = [
        re.compile(r"#\s+CIS\s+[\d.]+\s+(?:Audit\s*[-–]\s*)?(.+?)(?:\s*\((?:Automated|Manual)\))?\s*$", re.M),
        re.compile(r"#\s+[\d.]+(?:\.\d+)*\s+(.+?)(?:\s*\((?:Automated|Manual)\))?\s*$", re.M),
        re.compile(r"#\s+(?:Check|Ensure|Verify)\s+(.+?)(?:\s*\((?:Automated|Manual)\))?\s*$", re.M),
    ]
    for pat in patterns:
        m = pat.search(audit_content)
        if m:
            title = m.group(1).strip()
            title = re.sub(r"\s*-?\s*Audit\s*$", "", title, flags=re.IGNORECASE)
            if title and len(title) > 5:
                return title
    return ""


def extract_config_files(content: str) -> list[str]:
    """Script içindeki config dosya yollarını bul."""
    found = re.findall(r"/etc/[A-Za-z0-9_/.\-]+", content)
    # Anlamsız kısa pathleri filtrele
    result = []
    seen = set()
    for f in found:
        if len(f) > 8 and f not in seen:
            seen.add(f)
            result.append(f)
    return result[:5]


def extract_sshd_directive(audit_content: str) -> tuple[str, str]:
    """
    sshd -T kullanan kurallarda direktif adı ve beklenen değeri çıkar.
    Returns: (directive_name, expected_value)
    """
    # grep -i '^permitrootlogin' gibi patternler
    m = re.search(r"grep\s+['\"]?-[iI]\s*['\"]?\^([A-Za-z]+)['\"]?", audit_content)
    if not m:
        m = re.search(r"grep\s+-[qiI]+\s+['\"]([A-Za-z]+)\s+", audit_content)
    if m:
        directive = m.group(1)
        # Beklenen değeri FAIL mesajından çıkar
        val_m = re.search(
            r"Expected:\s*" + re.escape(directive.lower()) + r"\s+([^\n\"']+)",
            audit_content, re.IGNORECASE
        )
        if val_m:
            return directive, val_m.group(1).strip()
        # PASS mesajından çıkar
        val_m2 = re.search(
            directive + r"\s+is\s+(\w+)",
            audit_content, re.IGNORECASE
        )
        if val_m2:
            return directive, val_m2.group(1).lower()
        return directive, ""
    return "", ""


def extract_expected_value(audit_content: str, directive: str) -> str:
    """Beklenen değeri PASS/FAIL satırlarından çıkar."""
    if not directive:
        return ""
    # "Expected: permitrootlogin no"
    m = re.search(
        r"Expected[:\s]+(?:" + re.escape(directive.lower()) + r"\s+)?([^\n\"']{1,50})",
        audit_content, re.IGNORECASE
    )
    if m:
        val = m.group(1).strip().rstrip("\"'")
        if len(val) < 50:
            return val
    return ""


def extract_main_audit_command(audit_content: str) -> str:
    """Ana audit komutunu çıkar (sshd -T, stat, systemctl, vb.)."""
    candidates = []
    for line in audit_content.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if any(cmd in line for cmd in ["sshd -T", "stat -", "systemctl", "grep -", "find /", "awk ", "dpkg-query"]):
            # Değişken atamalarını tercih et
            if "=" in line and not line.startswith("if") and not line.startswith("while"):
                candidates.append(line)
            elif line.startswith("if ") or line.startswith("result="):
                candidates.append(line)
    return candidates[0] if candidates else ""


def extract_main_remediation_command(rem_content: str) -> str:
    """Ana remediation komutunu çıkar."""
    commands = []
    for line in rem_content.splitlines():
        line = line.strip()
        if line.startswith("#") or not line or line.startswith("echo"):
            continue
        if any(cmd in line for cmd in ["chmod", "chown", "sed -i", "echo ", "systemctl", "modprobe", "update-initramfs"]):
            commands.append(line)
    if commands:
        return "; ".join(commands[:3])
    return ""


def extract_kernel_module(content: str) -> str:
    """Kernel module adını çıkar."""
    m = re.search(r'mod_name\s*=\s*["\']?(\w[\w-]*)["\']?', content)
    if m:
        return m.group(1)
    m = re.search(r'modprobe\s+(?:-r\s+)?["\']?(\w[\w-]*)["\']?', content)
    if m:
        return m.group(1)
    return ""


def build_tags(section: str, title: str, audit_content: str, directive: str, module: str) -> list[str]:
    """Kapsamlı tag listesi oluştur."""
    tags: set[str] = set(SECTION_BASE_TAGS.get(section, ["hardening"]))

    # SSH direktif tags
    if directive and directive in SSH_DIRECTIVE_TAGS:
        tags.update(SSH_DIRECTIVE_TAGS[directive])
    elif "sshd" in audit_content.lower() or "ssh" in title.lower():
        tags.add("ssh")

    # Kernel module tags
    if module and module in MODULE_TAGS:
        tags.update(MODULE_TAGS[module])
    elif module:
        tags.update(["kernel_module", module])

    # Title-based tags
    title_lower = title.lower()
    keyword_map = {
        "password":    ["password", "authentication"],
        "sudo":        ["sudo", "privilege_escalation"],
        "cron":        ["cron", "scheduled_tasks"],
        "firewall":    ["firewall", "network"],
        "ufw":         ["ufw", "firewall", "network"],
        "nftables":    ["nftables", "firewall", "network"],
        "iptables":    ["iptables", "firewall", "network"],
        "auditd":      ["auditd", "logging"],
        "journald":    ["journald", "logging", "systemd"],
        "rsyslog":     ["rsyslog", "logging", "syslog"],
        "apparmor":    ["apparmor", "mandatory_access_control"],
        "selinux":     ["selinux", "mandatory_access_control"],
        "ipv6":        ["ipv6", "network"],
        "ipv4":        ["ipv4", "network"],
        "partition":   ["partition", "filesystem"],
        "mount":       ["mount", "filesystem"],
        "permission":  ["file_permissions"],
        "ownership":   ["file_permissions"],
        "update":      ["patching", "updates"],
        "package":     ["package_management"],
        "bootloader":  ["bootloader", "grub"],
        "grub":        ["bootloader", "grub"],
        "gdm":         ["gdm", "display_manager"],
        "x11":         ["x11", "display"],
        "usb":         ["usb", "removable_media"],
        "bluetooth":   ["bluetooth", "wireless"],
        "wifi":        ["wifi", "wireless"],
        "nfs":         ["nfs", "network_filesystem"],
        "samba":       ["samba", "smb", "file_sharing"],
        "ftp":         ["ftp", "file_transfer"],
        "telnet":      ["telnet", "insecure_protocol"],
        "rsh":         ["rsh", "legacy_protocol"],
        "avahi":       ["avahi", "mdns", "network_discovery"],
        "cups":        ["cups", "printing"],
        "dhcp":        ["dhcp", "network"],
        "dns":         ["dns", "network"],
        "ldap":        ["ldap", "directory_service"],
        "smtp":        ["smtp", "email"],
        "snmp":        ["snmp", "network_management"],
        "time":        ["ntp", "time_sync"],
        "ntp":         ["ntp", "time_sync"],
        "chrony":      ["chrony", "ntp", "time_sync"],
        "aide":        ["aide", "file_integrity"],
        "integrity":   ["file_integrity"],
        "pam":         ["pam", "authentication"],
        "shadow":      ["shadow", "password", "user_accounts"],
        "passwd":      ["passwd", "user_accounts"],
        "group":       ["group_management", "user_accounts"],
        "home":        ["home_directory", "user_accounts"],
        "umask":       ["umask", "file_permissions"],
        "sticky":      ["sticky_bit", "file_permissions"],
        "suid":        ["suid", "setuid", "privilege_escalation"],
        "sgid":        ["sgid", "setgid", "privilege_escalation"],
        "world-writable": ["world_writable", "file_permissions"],
    }
    for kw, extra_tags in keyword_map.items():
        if kw in title_lower:
            tags.update(extra_tags)

    return sorted(tags)


def generate_description(title: str, directive: str, expected_value: str,
                         config_files: list[str], module: str, audit_content: str) -> str:
    """RAG için anlamlı açıklama oluştur."""
    desc_parts = []

    if directive and expected_value:
        cfg = config_files[0] if config_files else "/etc/ssh/sshd_config"
        desc_parts.append(
            f"{cfg} dosyasinda '{directive}' direktifi '{expected_value}' olarak ayarlanmalidir."
        )
    elif module:
        desc_parts.append(
            f"'{module}' kernel modulu sistem guvenligini artirmak icin devre disi birakilmalidir."
        )
    elif config_files:
        cfg = config_files[0]
        desc_parts.append(f"Bu kural {cfg} dosyasinin guvenlik yapilandirmasini denetler.")

    # FAIL mesajindan aciiklama al
    fail_msgs = re.findall(r'echo\s+"(?:FAIL|Expected)[:\s]+([^"]{10,100})"', audit_content)
    if fail_msgs:
        desc_parts.append("Denetim: " + fail_msgs[0].strip())

    return " ".join(desc_parts) if desc_parts else f"CIS Benchmark kurali: {title}"


# ──────────────────────────────────────────────────────────────────
# RULE ID HELPERS
# ──────────────────────────────────────────────────────────────────

RULE_ID_RE = re.compile(r"^\d+(\.\d+)+$")


def is_rule_id(name: str) -> bool:
    return bool(RULE_ID_RE.match(name))


def get_section_number(rule_id: str) -> str:
    return rule_id.split(".")[0]


def get_relative_path(full_path: Path) -> str:
    try:
        return str(full_path.relative_to(BASE_DIR)).replace("\\", "/")
    except ValueError:
        return str(full_path).replace("\\", "/")


# ──────────────────────────────────────────────────────────────────
# DONTREMEDIATE LIST
# ──────────────────────────────────────────────────────────────────

def load_dontremediate_ids() -> set[str]:
    ids: set[str] = set()
    if not DONT_DIR.exists():
        return ids
    for item in DONT_DIR.iterdir():
        if item.is_dir() and is_rule_id(item.name):
            ids.add(item.name)
    return ids


# ──────────────────────────────────────────────────────────────────
# MAIN SCANNER
# ──────────────────────────────────────────────────────────────────

def process_rule_dir(rule_dir: Path, auto_remediate: bool) -> dict | None:
    rule_id = rule_dir.name
    audit_sh = rule_dir / "audit.sh"
    rem_sh   = rule_dir / "remediation.sh"

    if not audit_sh.exists():
        return None

    audit_content = read_file(audit_sh)
    rem_content   = read_file(rem_sh) if rem_sh.exists() else ""

    # Temel bilgiler
    title     = extract_title(audit_content)
    section   = get_section_number(rule_id)
    parts     = rule_id.split(".")
    section_id = ".".join(parts[:3]) if len(parts) >= 3 else ".".join(parts[:2])
    manual    = bool(re.search(r"\(Manual\)", audit_content, re.IGNORECASE))

    # Zenginleştirilmiş alanlar
    directive, _     = extract_sshd_directive(audit_content)
    expected_value   = extract_expected_value(audit_content, directive)
    config_files     = extract_config_files(audit_content + rem_content)
    module           = extract_kernel_module(audit_content + rem_content)
    main_audit_cmd   = extract_main_audit_command(audit_content)
    main_rem_cmd     = extract_main_remediation_command(rem_content)
    tags             = build_tags(section, title, audit_content, directive, module)
    description      = generate_description(
                           title, directive, expected_value,
                           config_files, module, audit_content
                       )

    rule: dict = {
        "id":               rule_id,
        "section":          section_id,
        "category":         SECTION_MAP.get(section, "General"),
        "title":            title or f"CIS Rule {rule_id}",
        "description":      description,
        "level":            1,
        "auto_remediate":   auto_remediate and not manual,
        "manual_review":    manual,
    }

    # SSH direktif bilgisi (varsa)
    if directive:
        rule["sshd_directive"]   = directive
        rule["expected_value"]   = expected_value

    # Kernel module bilgisi (varsa)
    if module:
        rule["kernel_module"]    = module

    # Config dosyaları
    if config_files:
        rule["config_files"]     = config_files

    # Ana komutlar (varsa)
    if main_audit_cmd:
        rule["audit_command"]    = main_audit_cmd
    if main_rem_cmd:
        rule["remediation_command"] = main_rem_cmd

    # Script yolları
    rule["audit_script"]         = get_relative_path(audit_sh)
    rule["remediation_script"]   = get_relative_path(rem_sh) if rem_sh.exists() else None

    # Tam script içerikleri (RAG için kritik)
    rule["audit_script_content"]       = audit_content
    rule["remediation_script_content"] = rem_content if rem_content else None

    rule["tags"] = tags

    return rule


def scan_rules(dont_ids: set[str]) -> list[dict]:
    rules: list[dict] = []
    seen_ids: set[str] = set()

    def add_rule(rule_dir: Path, auto_remediate: bool) -> None:
        rule_id = rule_dir.name
        if rule_id in seen_ids:
            return
        seen_ids.add(rule_id)
        rule = process_rule_dir(rule_dir, auto_remediate)
        if rule:
            rules.append(rule)

    # Normal kurallar
    if RULES_DIR.exists():
        for path in sorted(RULES_DIR.rglob("audit.sh")):
            rule_dir = path.parent
            if is_rule_id(rule_dir.name):
                add_rule(rule_dir, auto_remediate=(rule_dir.name not in dont_ids))

    # dontremediate kurallar
    if DONT_DIR.exists():
        for item in sorted(DONT_DIR.iterdir()):
            if item.is_dir() and is_rule_id(item.name):
                add_rule(item, auto_remediate=False)

    rules.sort(key=lambda r: [int(x) for x in r["id"].split(".")])
    return rules


# ──────────────────────────────────────────────────────────────────
# YAML WRITER
# ──────────────────────────────────────────────────────────────────

class _Literal(str):
    pass


def _literal_representer(dumper: yaml.Dumper, data: _Literal):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(_Literal, _literal_representer)


def write_yaml(rules: list[dict]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Script içeriklerini literal block olarak işaretle
    for rule in rules:
        for field in ("audit_script_content", "remediation_script_content"):
            if rule.get(field):
                rule[field] = _Literal(rule[field])

    doc = {
        "metadata": {
            "os":                   "ubuntu_24_04",
            "benchmark":            "CIS Ubuntu Linux Benchmark",
            "benchmark_version":    "v2.0.0",
            "generated":            str(date.today()),
            "total_rules":          len(rules),
            "auto_remediate_count": sum(1 for r in rules if r.get("auto_remediate")),
            "manual_review_count":  sum(1 for r in rules if r.get("manual_review")),
            "with_remediation":     sum(1 for r in rules if r.get("remediation_script")),
            "description": (
                "CIS Ubuntu Linux Benchmark v2.0.0 security hardening rules. "
                "Her kural: title, description, sshd_directive/kernel_module, "
                "config_files, audit/remediation script icerikleri ve tags icermektedir. "
                "Ubuntu 20.04, 22.04, 24.04 icin gecerlidir."
            ),
        },
        "rules": rules,
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        yaml.dump(
            doc, f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            indent=2,
            width=120,
        )

    size_kb = OUTPUT_FILE.stat().st_size // 1024
    print(f"[OK] {len(rules)} kural yazildi -> {OUTPUT_FILE}")
    print(f"     Dosya boyutu: {size_kb} KB")


# ──────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────

def main() -> None:
    if not RULES_DIR.exists():
        print(f"[HATA] Kurallar klasoru bulunamadi: {RULES_DIR}")
        sys.exit(1)

    print("[*] dontremediate listesi yukleniyor...")
    dont_ids = load_dontremediate_ids()
    print(f"    {len(dont_ids)} kural manuel inceleme gerektirir")

    print("[*] Kurallar taranip zenginlestiriliyor...")
    rules = scan_rules(dont_ids)
    print(f"    {len(rules)} kural bulundu")

    print("[*] YAML olusturuluyor...")
    write_yaml(rules)

    # Ozet
    print("\n-- Bolum Ozeti --")
    counts = Counter(r["category"] for r in rules)
    for cat, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {cat:<50} {n:>3} kural")

    ssh_rules = [r for r in rules if r.get("sshd_directive")]
    km_rules  = [r for r in rules if r.get("kernel_module")]
    print(f"\n  SSH direktif kurallari : {len(ssh_rules)}")
    print(f"  Kernel module kurallari: {len(km_rules)}")
    print(f"  Script icerigi olan    : {sum(1 for r in rules if r.get('audit_script_content'))}")


if __name__ == "__main__":
    main()
