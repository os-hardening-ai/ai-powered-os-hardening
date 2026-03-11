# CIS 1.1.1.10 - Ensure Unused Filesystems Kernel Modules Are Not Available

**Profile:** Level 1 - Server, Level 1 - Workstation
**Type:** Manual

## Overview

This control ensures that unused filesystem kernel modules are disabled to reduce the attack surface. Many filesystem modules have known CVE vulnerabilities and should be disabled if not needed by the system.

## Files in This Directory

| File | Purpose | Safety Level | Use Case |
|------|---------|--------------|----------|
| `audit.sh` | Comprehensive audit script from CIS Benchmark | N/A | Run first to understand current state |
| `remediation.sh` | Semi-automatic remediation with safety checks | **MEDIUM** | Batch disable multiple safe modules |
| `remediation_manual.sh` | Manual single-module remediation | **HIGH** | Disable one module at a time after review |

---

## Usage Guide

### Step 1: Run the Audit

```bash
sudo ./audit.sh
```

This will show:
- Which modules are available on your system
- Which modules are currently mounted (DO NOT DISABLE)
- Which modules are already disabled
- Which modules have known CVEs

**Example Output:**
```
=== CIS 1.1.1.10 Audit: Unused Filesystem Kernel Modules ===

 -- INFO: Intentionally Skipped Modules --
 - Kernel module: "xfs"
 - Kernel module: "ext4"
 - Kernel module: "vfat"

[ FAIL ] ** REVIEW the following **
 - Kernel module: "gfs2" is not fully disabled  <- CVE exists!
 - Kernel module: "cifs" is not fully disabled  <- CVE exists!
 - Kernel module: "nfs_common" is not fully disabled  <- CVE exists!

-- Correctly Configured: --
 - Kernel module: "overlay" is currently mounted - do NOT unload or disable

WARNING: Disabling or denylisting filesystem modules that are in use may be FATAL.
         Review this list carefully before running remediation.
```

### Step 2: Choose Your Remediation Approach

## Approach A: Semi-Automatic (RECOMMENDED for experienced admins)

**Safety Level:** Medium
**Use Case:** You've reviewed the audit and want to disable multiple unused modules at once

```bash
sudo ./remediation.sh
```

**What it does:**
- Automatically identifies safe-to-disable modules
- Skips protected modules (xfs, ext2/3/4, vfat, overlay)
- Skips mounted filesystems (CRITICAL safety check)
- Skips already-disabled modules
- Shows you what will be changed
- **Asks for confirmation before making changes**

**Output Example:**
```
=== Analysis Results ===

Modules to be disabled:
  - gfs2 (has CVE)
  - cifs (has CVE)
  - fscache (has CVE)

Modules that will be skipped:
  - xfs (protected)
  - ext4 (currently mounted)
  - overlay (already disabled)

Do you want to proceed? (yes/no): yes

[SUCCESS] Successfully disabled 3 module(s)
```

**Pros:**
✓ Fast for multiple modules
✓ Built-in safety checks
✓ Requires confirmation
✓ Good for clean systems

**Cons:**
✗ Less granular control
✗ May miss edge cases

---

## Approach B: Manual (SAFEST - RECOMMENDED for production)

**Safety Level:** High
**Use Case:** Production systems, or when you want maximum control

```bash
sudo ./remediation_manual.sh <module_name>
```

**Example:**
```bash
sudo ./remediation_manual.sh gfs2
```

**What it does:**
- Disables ONE module at a time
- Extensive safety checks and warnings
- Shows current module status
- **BLOCKS if module is mounted (prevents system crash)**
- Detailed confirmation prompt
- Clear success/failure messages

**Output Example:**
```
=== Module Status ===
Module name: gfs2
Has CVE: YES
Currently loaded: NO
Currently mounted: NO
Already disabled: NO

This script will:
  1. Create /etc/modprobe.d/gfs2.conf
  2. Add 'install gfs2 /bin/false' directive
  3. Add 'blacklist gfs2' directive
  4. Update initramfs

Are you sure you want to disable 'gfs2'? (yes/no): yes

[SUCCESS] Module 'gfs2' has been successfully disabled
```

**Pros:**
✓ Maximum safety
✓ Complete control
✓ Best for production
✓ Easy to verify each step
✓ Great for learning

**Cons:**
✗ Slower for many modules
✗ Requires multiple runs

---

## Key Differences Summary

| Aspect | Semi-Automatic | Manual |
|--------|----------------|--------|
| **Safety** | Medium | High |
| **Speed** | Fast (batch) | Slow (one-by-one) |
| **Control** | Moderate | Complete |
| **Best For** | Dev/test, multiple modules | Production, critical systems |
| **Confirmation** | Once for all | Once per module |
| **Mounted Check** | Yes | Yes (with block) |
| **CVE Warning** | Yes | Yes (detailed) |
| **Rollback** | All or nothing | Per-module |

---

## Protected Modules (NEVER Disable)

These modules are automatically protected:
- `xfs` - Common Linux filesystem
- `vfat` - FAT32, used by EFI/boot partitions
- `ext2`, `ext3`, `ext4` - Standard Linux filesystems
- `overlay` - Used by Docker, containers

---

## Modules with Known CVEs

These modules have known vulnerabilities and should be disabled if unused:

| Module | CVE Example | Description |
|--------|-------------|-------------|
| `afs` | CVE-2022-37402 | Andrew File System |
| `ceph` | CVE-2022-0670 | Ceph distributed filesystem |
| `cifs` | CVE-2022-29869 | Common Internet File System |
| `exfat` | CVE-2022-29973 | Extended FAT |
| `ext` | CVE-2022-1184 | Old ext filesystem |
| `fat` | CVE-2022-22043 | FAT filesystem |
| `fscache` | CVE-2022-3630 | Filesystem cache |
| `fuse` | CVE-2023-0386 | Filesystem in Userspace |
| `gfs2` | CVE-2023-3212 | Global File System 2 |
| `nfs_common` | CVE-2023-6660 | NFS common components |
| `nfsd` | CVE-2022-43945 | NFS server daemon |
| `smbfs_common` | CVE-2022-2585 | SMB filesystem common |

---

## Recommendations by Environment

### Development/Test Systems
**Use:** `remediation.sh` (semi-automatic)
- Faster deployment
- Less critical if issues occur
- Good for testing the process

### Production Systems
**Use:** `remediation_manual.sh` (manual)
- Maximum safety
- Complete control
- Better audit trail
- Easier to troubleshoot

### High-Security Environments
**Use:** `remediation_manual.sh` (manual)
- Disable all modules with CVEs that you don't use
- Document each change
- Test in staging first

---

## Safety Checklist

Before running remediation:

1. ✓ Run audit script first
2. ✓ Review ALL mounted filesystems
3. ✓ Check which modules your applications need
4. ✓ Verify boot partition filesystem (usually vfat for EFI)
5. ✓ Test in non-production first
6. ✓ Have physical/console access (in case of issues)
7. ✓ Backup current configuration
8. ✓ Know how to boot from rescue media

---

## What Gets Changed

When you disable a module, the scripts:

1. **Create/modify** `/etc/modprobe.d/<module>.conf`:
   ```bash
   install <module> /bin/false
   blacklist <module>
   ```

2. **Unload module** from memory (if loaded and safe)

3. **Update initramfs** to persist changes across reboots

---

## Verification

After remediation:

```bash
# Check if module is disabled
modprobe <module>  # Should fail with error

# Check if module is loaded
lsmod | grep <module>  # Should return nothing

# Check configuration
cat /etc/modprobe.d/<module>.conf

# Verify in modprobe config
modprobe --showconfig | grep <module>
```

---

## Troubleshooting

### System won't boot after disabling modules
1. Boot from rescue media
2. Mount root filesystem
3. Remove `/etc/modprobe.d/<module>.conf` files
4. Rebuild initramfs: `update-initramfs -u -k all`
5. Reboot

### Module still loading
1. Check if module is built-in: `grep <module> /lib/modules/$(uname -r)/modules.builtin`
2. Rebuild initramfs: `sudo update-initramfs -u -k all`
3. Reboot system

### Need to re-enable a module
```bash
sudo rm /etc/modprobe.d/<module>.conf
sudo update-initramfs -u -k all
sudo modprobe <module>
```

---

## Example Workflow

### Conservative (Production) Approach

```bash
# 1. Run audit
sudo ./audit.sh > audit_results.txt

# 2. Review results carefully
cat audit_results.txt

# 3. For each module you want to disable (starting with CVE modules)
sudo ./remediation_manual.sh gfs2
sudo ./remediation_manual.sh cifs
sudo ./remediation_manual.sh nfsd

# 4. Re-run audit to verify
sudo ./audit.sh

# 5. Reboot and test
sudo reboot
```

### Aggressive (Test) Approach

```bash
# 1. Run audit
sudo ./audit.sh

# 2. Run semi-automatic remediation
sudo ./remediation.sh

# 3. Verify changes
sudo ./audit.sh

# 4. Reboot and test
sudo reboot
```

---

## References

- [CIS Ubuntu Linux 22.04 LTS Benchmark v2.0.0](https://www.cisecurity.org/benchmark/ubuntu_linux)
- [CVE MITRE Database - Filesystem](https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=filesystem)
- [Linux Kernel Module Blacklisting](https://www.kernel.org/doc/html/latest/admin-guide/module-signing.html)

---

## When to Use Which Script

```
┌─────────────────────────────────────────────────────────────┐
│                     START: Need to disable                   │
│                   unused filesystem modules                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
                   ┌───────────────┐
                   │  Run audit.sh │
                   └───────┬───────┘
                           │
                           ▼
         ┌─────────────────────────────────┐
         │  Is this a production system?   │
         └────────┬────────────────┬───────┘
                  │ YES            │ NO
                  │                │
                  ▼                ▼
    ┌──────────────────────┐  ┌──────────────────────┐
    │ remediation_manual.sh│  │   remediation.sh     │
    │  (One at a time)     │  │  (Batch with review) │
    └──────────────────────┘  └──────────────────────┘
                  │                │
                  └────────┬───────┘
                           │
                           ▼
                   ┌───────────────┐
                   │  Run audit.sh │
                   │  (Verify)     │
                   └───────┬───────┘
                           │
                           ▼
                   ┌───────────────┐
                   │     Reboot    │
                   └───────┬───────┘
                           │
                           ▼
                   ┌───────────────┐
                   │  Test system  │
                   └───────────────┘
```

---

## Summary

**Which one should you use?**

- **Learning/Understanding:** Start with `audit.sh`, then try `remediation_manual.sh` on one module
- **Production Systems:** Always use `remediation_manual.sh`
- **Test/Dev Systems:** `remediation.sh` is acceptable if you review the output
- **High-Security:** `remediation_manual.sh` for all CVE modules you don't need

**Remember:** It's always better to be slower and safer than fast and broken. A system that won't boot is worse than a system with unused modules enabled.
