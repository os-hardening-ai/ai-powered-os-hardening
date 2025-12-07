# Security Updates

## Critical Security Fixes Applied

### Date: 2025-12-08

This document tracks security vulnerabilities and their resolutions.

---

## Fixed Vulnerabilities

### 1. langgraph-checkpoint (CVE-2025-64439) ✅ FIXED
- **Severity**: Critical
- **Affected Version**: 2.1.0
- **Fixed Version**: 3.0.0
- **Status**: ✅ Updated and verified
- **Details**: Security vulnerability in checkpoint mechanism
- **Action Taken**: Updated from 2.1.0 to 3.0.0

---

## Pending Vulnerabilities (Windows File Locking)

The following vulnerabilities require manual update due to Windows file locking issues:

### 2. h11 (CVE-2025-43859) ⚠️ PENDING
- **Severity**: High
- **Affected Version**: 0.14.0
- **Fixed Version**: 0.16.0
- **Status**: ⚠️ Updated in requirements.txt, pending manual installation
- **Details**: Security vulnerability in HTTP/1.1 parsing
- **Manual Fix Required**:
  ```bash
  # Close all Python processes, then run:
  pip install --force-reinstall h11==0.16.0
  ```

### 3. pillow (PYSEC-2025-61) ⚠️ PENDING
- **Severity**: Moderate
- **Affected Version**: 11.2.1
- **Fixed Version**: 11.3.0
- **Status**: ⚠️ Updated in requirements.txt, pending manual installation
- **Details**: Security vulnerability in image processing
- **Manual Fix Required**:
  ```bash
  # Close all Python processes, then run:
  pip install --force-reinstall pillow==11.3.0
  ```

---

## Installation Instructions

### For Development (Local)

1. **Close all Python processes** including:
   - VS Code Python terminals
   - Running API servers (`python -m main`)
   - Jupyter notebooks
   - Any other Python processes

2. **Install updates**:
   ```bash
   pip install --force-reinstall -r requirements.txt
   ```

3. **Verify updates**:
   ```bash
   python -m pip_audit
   ```

### For Production (Docker)

If using Docker, rebuild the container:
```bash
docker build -t ai-os-hardening .
docker-compose up -d
```

### For CI/CD

Update your CI/CD pipeline to use the latest requirements.txt:
```yaml
- name: Install dependencies
  run: pip install -r requirements.txt
```

---

## Verification

After applying updates, verify all vulnerabilities are fixed:

```bash
# Run security audit
python -m pip_audit

# Expected output:
# No known vulnerabilities found
```

---

## requirements.txt Updates

The following packages were updated in requirements.txt:

```diff
- h11>=0.16.0  # Was: h11==0.14.0
+ h11==0.16.0  # Fixed: CVE-2025-43859

- langgraph-checkpoint>=3.0.0  # Was: langgraph-checkpoint==2.1.0
+ langgraph-checkpoint==3.0.0  # Fixed: CVE-2025-64439

- pillow>=11.3.0  # Was: pillow==11.2.1
+ pillow==11.3.0  # Fixed: PYSEC-2025-61
```

---

## Security Scanning Schedule

We recommend running security audits:
- **Before deployment**: Always
- **Weekly**: Automated scan in CI/CD
- **On dependency updates**: Manual verification

### Automated Scanning

Add to your GitHub Actions workflow:

```yaml
name: Security Audit
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
  push:
    branches: [main, develop]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pip-audit
      - name: Run security audit
        run: python -m pip_audit
```

---

## Additional Security Measures

### 1. Rate Limiting
Already implemented in `api/middleware/rate_limiter.py`:
- 100 requests per minute per IP
- 1000 requests per hour per IP

### 2. Input Validation
All user inputs are validated through:
- Pydantic models
- Safety classifier (Layer 1)
- Output validator (hybrid regex + LLM)

### 3. Security Headers
Implemented in FastAPI middleware:
- HSTS (HTTP Strict Transport Security)
- CSP (Content Security Policy)
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY

### 4. Dependency Management
- Pin all dependency versions in requirements.txt
- Regular security audits with pip-audit
- Automated Dependabot alerts on GitHub

---

## Known Issues

### Windows File Locking
**Issue**: `[WinError 5] Access denied` when updating packages

**Cause**: Python processes have locked .pyd/.dll files

**Solution**:
1. Close all Python processes
2. Restart your terminal
3. Run: `pip install --force-reinstall <package>`

### Invalid Distribution Warning
**Warning**: `Ignoring invalid distribution ~iter`

**Cause**: Corrupted package installation

**Solution**:
```bash
# Find and remove corrupted package
cd %LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.3.12_*\LocalCache\local-packages\Python312\site-packages
# Delete folders starting with ~
```

---

## Contact

For security issues, please:
1. **Do not** create public GitHub issues
2. Email: [security contact email]
3. Include: CVE/PYSEC ID, affected version, reproduction steps

---

## References

- [CVE-2025-43859 (h11)](https://nvd.nist.gov/vuln/detail/CVE-2025-43859)
- [CVE-2025-64439 (langgraph-checkpoint)](https://nvd.nist.gov/vuln/detail/CVE-2025-64439)
- [PYSEC-2025-61 (pillow)](https://pypi.org/project/pillow/)
- [pip-audit Documentation](https://pypi.org/project/pip-audit/)

---

**Last Updated**: 2025-12-08
**Next Review**: 2025-12-15
