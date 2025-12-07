# Security Vulnerabilities Fixed

**Date**: 2025-12-07
**Status**: Requirements updated, manual pip upgrade required

## Critical Vulnerabilities Patched

### 1. **langgraph-checkpoint** - CRITICAL RCE Vulnerability
- **CVE**: CVE-2025-64439
- **Severity**: CRITICAL
- **Old Version**: 2.1.0
- **Fixed Version**: ≥3.0.0
- **Issue**: Remote Code Execution via JsonPlusSerializer deserialization
- **Impact**: Attackers could execute arbitrary code by sending malicious payloads

### 2. **h11** - Request Smuggling
- **CVE**: CVE-2025-43859
- **Severity**: HIGH
- **Old Version**: 0.14.0
- **Fixed Version**: ≥0.16.0
- **Issue**: HTTP request smuggling vulnerability
- **Impact**: Could allow attackers to bypass security controls

### 3. **pillow** - Heap Buffer Overflow
- **CVE**: PYSEC-2025-61
- **Severity**: HIGH
- **Old Version**: 11.2.1
- **Fixed Version**: ≥11.3.0
- **Issue**: Heap buffer overflow in DDS format handling
- **Impact**: Could lead to crashes or code execution

### 4. **urllib3** - Multiple CVEs (Already Fixed)
- **CVEs**:
  - CVE-2025-50182 (redirect control in Pyodide)
  - CVE-2025-50181 (redirect disable bypass)
  - CVE-2025-66418 (unbounded decompression chain)
  - CVE-2025-66471 (streaming decompression memory exhaustion)
- **Old Version**: 2.4.0
- **Fixed Version**: ≥2.6.0
- **Status**: ✅ Already upgraded

### 5. **Werkzeug** - Windows Device Names
- **CVE**: CVE-2025-66221
- **Severity**: MEDIUM
- **Old Version**: 3.1.3
- **Fixed Version**: ≥3.1.4
- **Issue**: Windows device names vulnerability
- **Status**: ✅ Already upgraded

## Actions Taken

1. ✅ Updated `requirements.txt` with secure versions
2. ⚠️ Partial pip upgrade (3/5 packages upgraded)
3. ⚠️ Manual intervention needed for locked packages

## Manual Fix Required

Due to Windows file locking, the following packages need manual upgrade:

```bash
# Close all Python processes, then run:
pip install --upgrade "h11>=0.16.0" "langgraph-checkpoint>=3.0.0" "pillow>=11.3.0"

# Or restart your system and run:
pip install -r requirements.txt --upgrade
```

## Verification

After manual upgrade, verify fixes:

```bash
python -m pip_audit
```

Expected output: **0 vulnerabilities found**

## References

- [pip-audit documentation](https://pypi.org/project/pip-audit/)
- [CVE Database](https://cve.mitre.org/)
