# Windows Hardening Tools Consistency Report

**Date:** 2026-01-29
**Status:** Incomplete Implementation / Major Inconsistencies Found

## Executive Summary
The review of the `platforms/windows/tools` directory against the `WINDOWS_HARDENING_ARCHITECTURE.md` specification reveals that the current implementation is incomplete. While the PowerShell script generation (`ps_script_builder.ps1`) is functional, the GPO generation logic is disconnected and incomplete. Specifically, `generator.ps1` does not execute the GPO building process, and the GPO builder itself fails to generate `Registry.pol` files, rendering it ineffective for registry-based policies.

## Detailed Findings

### 1. Generator Orchestration (`generator.ps1`)

**Severity: Critical**

-   **Issue**: The main orchestration script `generator.ps1` **does not load or call** `gpo_builder.ps1`.
-   **Impact**: When the user runs `generator.ps1`, no GPO backup is created. The "GPO Generator" component described in the architecture (Section 3.1) is effectively missing from the execution flow.
-   **Missing Logic**:
    ```powershell
    # Missing from generator.ps1:
    . (Join-Path $scriptDir "gpo_builder.ps1")
    . (Join-Path $scriptDir "registry_pol_writer.ps1")
    New-GPOBackup -Rules $processedRules -OutputPath $outputPath
    ```

### 2. GPO Builder (`gpo_builder.ps1`)

**Severity: Critical**

-   **Issue**: `New-GPOBackup` creates the `Registry.pol` directory structure (`Machine\Registry.pol`, `User\Registry.pol`) but **never populates the file**.
-   **Impact**: Registry-based rules (which constitute the majority of hardening rules using `registry_config`) are not applied by the generated GPO. Only `SecEdit` (Security Template) settings are generated.
-   **Architecture Violation**: The architecture (Section 3.3) explicitly mentions `Registry.pol Generation` via `New-RegistryPol`. This integration is missing in `gpo_builder.ps1`.

### 3. Registry Pol Writer (`registry_pol_writer.ps1`)

**Severity: High**

-   **Issue 1 (Integration)**: The function `New-RegistryPol` exists but is not called by `gpo_builder.ps1`.
-   **Issue 2 (Type Support)**: The writer currently supports basic `REG_DWORD` and defaults everything else to string (Unicode).
    -   **Gap**: `REG_MULTI_SZ` (Multi-String) requires strictly formatted double-null termination (`\0\0`).
    -   **Gap**: `REG_QWORD` (64-bit integer) is not explicitly handled and may be malformed if written as a string or 32-bit int.
    -   **Gap**: `REG_EXPAND_SZ` is treated as a standard string, which is generally acceptable but worth verifying against PReg spec.

### 4. Rule Schema Usage

-   **Inconsistency**: The `gpo_builder.ps1` relies solely on `implementation_gpo` (for INF files). It **ignores** `registry_config`.
    -   **Correction Needed**: The GPO builder must split rules into two streams:
        1.  Rules with `registry_config` -> Send to `Registry.pol` writer.
        2.  Rules with `implementation_gpo` (INF sections) -> Send to `GptTmpl.inf` writer.

## Architecture vs. Implementation Matrix

| Component | Architecture Spec | Current Implementation | Status |
| :--- | :--- | :--- | :--- |
| **Local Script** | `ps_script_builder.ps1` | Implemented | ✅ Pass |
| **GPO Backup** | `gpo_builder.ps1` | Exists but not called | ❌ Fail |
| **Registry.pol** | `registry_pol_writer.ps1` | Exists but not integrated | ❌ Fail |
| **Security Tmpl** | `GptTmpl.inf` generation | Implemented in `gpo_builder` | ⚠️ Partial (Only uses INF data) |
| **Orchestrator** | `generator.ps1` | Missing GPO calls | ❌ Fail |

## Recommendations

1.  **Refactor `generator.ps1`**:
    -   Dot-source `gpo_builder.ps1` and `registry_pol_writer.ps1`.
    -   Call `New-GPOBackup` after script generation.

2.  **Update `gpo_builder.ps1`**:
    -   Integrate `New-RegistryPol`.
    -   Logic:
        ```powershell
        # Pseudo-code for gpo_builder.ps1
        $registryRules = $Rules | Where-Object { $_.Rule.registry_config }
        $machinePolPath = Join-Path $gpoPath "DomainSysvol\GPO\Machine\Registry.pol"
        New-RegistryPol -Rules $registryRules -OutputPath $machinePolPath
        ```

3.  **Enhance `registry_pol_writer.ps1`**:
    -   Add specific case handling for `REG_QWORD` and `REG_MULTI_SZ` to ensure binary compatibility with Windows Group Policy.

4.  **Verification**:
    -   Generate a GPO.
    -   Import it into a Test Domain Controller.
    -   Verify standard registry keys are present in the GPO Settings report.
