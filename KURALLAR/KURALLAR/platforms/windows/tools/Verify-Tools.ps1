#Requires -Version 5.1
<#
.SYNOPSIS
    Automated Verification Suite for CIS Hardening Generator Tools
.DESCRIPTION
    End-to-end tests covering:
      1. Execution   - Generator runs clean (GPO + Standalone)
      2. GPO Output  - Structure, portability, security, GUID uniqueness
      3. Script Output - Syntax validity, expected content
.NOTES
    Run from the platforms\windows\tools directory.
    Does NOT require Active Directory or admin rights.
    Uses a temporary output folder that is cleaned up after tests.
#>

$ErrorActionPreference = "Stop"

# ===================================================================
# Test Framework
# ===================================================================
$Script:PassCount = 0
$Script:FailCount = 0
$Script:TestResults = @()

function Write-TestHeader ($Section) {
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host "  $Section" -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan
}

function Assert-Test {
    param(
        [string]$Name,
        [bool]$Condition,
        [string]$FailDetail = ""
    )
    if ($Condition) {
        Write-Host "  [PASS] $Name" -ForegroundColor Green
        $Script:PassCount++
        $Script:TestResults += [PSCustomObject]@{ Test = $Name; Result = "PASS"; Detail = "" }
    }
    else {
        $msg = "  [FAIL] $Name"
        if ($FailDetail) { $msg += " - $FailDetail" }
        Write-Host $msg -ForegroundColor Red
        $Script:FailCount++
        $Script:TestResults += [PSCustomObject]@{ Test = $Name; Result = "FAIL"; Detail = $FailDetail }
    }
}

# ===================================================================
# Setup
# ===================================================================
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$toolsDir = $scriptDir
$rulesDir = Join-Path $toolsDir "..\rules"
$testOutput = Join-Path $env:TEMP "CIS_Verify_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

Write-Host ""
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "  CIS Hardening Generator - Verification Suite"                        -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Tools Dir  : $toolsDir"   -ForegroundColor Gray
Write-Host "  Rules Dir  : $rulesDir"   -ForegroundColor Gray
Write-Host "  Test Output: $testOutput" -ForegroundColor Gray

# ===================================================================
# 0. Pre-flight Checks
# ===================================================================
Write-TestHeader "0. Pre-flight Checks"

$requiredFiles = @(
    "generator.ps1",
    "gpo_builder.ps1",
    "ps_script_builder.ps1",
    "inf_generator.ps1",
    "registry_pol_writer.ps1"
)

foreach ($file in $requiredFiles) {
    $path = Join-Path $toolsDir $file
    Assert-Test "Source file exists: $file" (Test-Path $path)
}

$ruleFiles = Get-ChildItem -Path $rulesDir -Filter "*.json" -Recurse -ErrorAction SilentlyContinue
Assert-Test "Rule files found (count > 0)" ($ruleFiles.Count -gt 0) "Found: $($ruleFiles.Count)"

# ===================================================================
# 1. EXECUTION TESTS - Run generator twice (for uniqueness test)
# ===================================================================
Write-TestHeader "1. Execution Tests"

function Invoke-Generator {
    param([string]$OutputDir)

    if (-not (Test-Path $OutputDir)) {
        New-Item -Path $OutputDir -ItemType Directory -Force | Out-Null
    }

    # Dot-source the builder modules
    . (Join-Path $toolsDir "ps_script_builder.ps1")
    . (Join-Path $toolsDir "gpo_builder.ps1")
    . (Join-Path $toolsDir "registry_pol_writer.ps1")

    # Load rules
    $processedRules = @()
    foreach ($file in $ruleFiles) {
        $content = Get-Content $file.FullName -Raw | ConvertFrom-Json
        $processedRules += [PSCustomObject]@{ Rule = $content }
    }

    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"

    # Generate standalone PS1
    $psOutput = Join-Path $OutputDir "CIS_Hardening_${timestamp}.ps1"
    New-HardeningScript -Rules $processedRules -OutputPath $psOutput | Out-Null

    # Generate GPO Backup
    $gpoOutput = Join-Path $OutputDir "GPO_Backup_${timestamp}"
    New-Item -Path $gpoOutput -ItemType Directory -Force | Out-Null
    New-GPOBackup -Rules $processedRules -OutputPath $gpoOutput -GPOName "CIS_Test_${timestamp}" | Out-Null

    return @{
        PSOutput  = $psOutput
        GPOOutput = $gpoOutput
        Timestamp = $timestamp
        RuleCount = $processedRules.Count
    }
}

# Run 1
$run1 = $null
try {
    $run1 = Invoke-Generator -OutputDir (Join-Path $testOutput "Run1")
    Assert-Test "Generator Run 1 completed without errors" $true
}
catch {
    Assert-Test "Generator Run 1 completed without errors" $false $_.Exception.Message
}

Start-Sleep -Milliseconds 200

# Run 2
$run2 = $null
try {
    $run2 = Invoke-Generator -OutputDir (Join-Path $testOutput "Run2")
    Assert-Test "Generator Run 2 completed without errors" $true
}
catch {
    Assert-Test "Generator Run 2 completed without errors" $false $_.Exception.Message
}

# Abort if generation failed
if ($null -eq $run1 -or $null -eq $run2) {
    Write-Host ""
    Write-Host "  [ABORT] Cannot continue - generation failed." -ForegroundColor Red
    Write-Host ""
    exit 1
}

# ===================================================================
# 2. GPO OUTPUT ANALYSIS
# ===================================================================
Write-TestHeader "2a. GPO Output - Structure"

$gpoDir = $run1.GPOOutput

# Find the {GUID} backup subfolder
$guidFolder = Get-ChildItem -Path $gpoDir -Directory | Where-Object { $_.Name -match '^\{.*\}$' }
Assert-Test "GUID folder exists in GPO backup" ($null -ne $guidFolder -and $guidFolder.Count -eq 1)

if ($guidFolder) {
    $guidPath = $guidFolder[0].FullName

    # Required files in the GUID folder
    $gpoStructureFiles = @(
        @{ Name = "Backup.xml"; Path = (Join-Path $guidPath "Backup.xml") },
        @{ Name = "bkupInfo.xml"; Path = (Join-Path $guidPath "bkupInfo.xml") },
        @{ Name = "gpreport.xml"; Path = (Join-Path $guidPath "gpreport.xml") },
        @{ Name = "GptTmpl.inf"; Path = (Join-Path $guidPath "DomainSysvol\GPO\Machine\microsoft\windows nt\SecEdit\GptTmpl.inf") }
    )

    foreach ($item in $gpoStructureFiles) {
        Assert-Test "GPO file exists: $($item.Name)" (Test-Path $item.Path)
    }

    # Root-level files
    Assert-Test "manifest.xml exists at GPO root" (Test-Path (Join-Path $gpoDir "manifest.xml"))
    Assert-Test "README.md exists at GPO root" (Test-Path (Join-Path $gpoDir "README.md"))
    Assert-Test "Import-Policy.ps1 exists at GPO root" (Test-Path (Join-Path $gpoDir "Import-Policy.ps1"))

    # DomainSysvol directory structure
    $sysvolDir = Join-Path $guidPath "DomainSysvol\GPO\Machine"
    Assert-Test "DomainSysvol\GPO\Machine directory exists" (Test-Path $sysvolDir)

    # -----------------------------------------------------------
    # 2b. Portability - Domain placeholders
    # -----------------------------------------------------------
    Write-TestHeader "2b. GPO Output - Portability (Domain Placeholders)"

    $xmlFiles = @(
        (Join-Path $guidPath "Backup.xml"),
        (Join-Path $guidPath "bkupInfo.xml"),
        (Join-Path $guidPath "gpreport.xml"),
        (Join-Path $gpoDir "manifest.xml")
    )

    # Build the bare-domain search tag using char codes to avoid parser issues
    $gtChar = [char]62   # >
    $ltChar = [char]60   # <
    $bareDomainTag = "${gtChar}DOMAIN${ltChar}"

    foreach ($xmlFile in $xmlFiles) {
        if (Test-Path $xmlFile) {
            $xmlContent = Get-Content $xmlFile -Raw
            $fileName = Split-Path $xmlFile -Leaf

            # Must contain HARDENING_TEMPLATE
            $hasPlaceholder = $xmlContent -match "HARDENING_TEMPLATE"
            Assert-Test "$fileName contains HARDENING_TEMPLATE" $hasPlaceholder

            # Must NOT contain bare ">DOMAIN<"
            $escapedPattern = [regex]::Escape($bareDomainTag)
            $baredomainMatches = [regex]::Matches($xmlContent, $escapedPattern)
            Assert-Test "$fileName has no bare DOMAIN placeholder" ($baredomainMatches.Count -eq 0) `
                "Found $($baredomainMatches.Count) bare DOMAIN instances"

            # DC placeholder check
            if ($xmlContent -match "GPODomainController") {
                $hasBadDC = $xmlContent -match "DC\.DOMAIN\.LOCAL"
                Assert-Test "$fileName DC uses HARDENING_TEMPLATE (not DOMAIN)" (-not $hasBadDC)
            }
        }
    }

    # -----------------------------------------------------------
    # 2c. Security - No local path leaks
    # -----------------------------------------------------------
    Write-TestHeader "2c. GPO Output - Security (Path Leak Scan)"

    $localPathPatterns = @(
        "C:\\Users\\",
        "C:\\Windows\\",
        "D:\\"
    )

    foreach ($xmlFile in $xmlFiles) {
        if (Test-Path $xmlFile) {
            $xmlContent = Get-Content $xmlFile -Raw
            $fileName = Split-Path $xmlFile -Leaf
            $leakFound = $false
            $leakDetail = ""

            foreach ($pattern in $localPathPatterns) {
                if ($xmlContent -match [regex]::Escape($pattern)) {
                    $leakFound = $true
                    $leakDetail = "Contains: $pattern"
                    break
                }
            }

            Assert-Test "$fileName has no local path leaks" (-not $leakFound) $leakDetail
        }
    }

    # SourceExpandedPath specific check
    $backupXmlContent = Get-Content (Join-Path $guidPath "Backup.xml") -Raw
    $hasGpoVar = $backupXmlContent -match 'SourceExpandedPath.*%GPO_MACH_FSPATH%'
    Assert-Test "Backup.xml SourceExpandedPath uses %GPO_MACH_FSPATH%" $hasGpoVar

    # -----------------------------------------------------------
    # 2d. Uniqueness - GUIDs differ between Run 1 and Run 2
    # -----------------------------------------------------------
    Write-TestHeader "2d. GPO Output - GUID Uniqueness (Cross-Run)"

    $gpoDir2 = $run2.GPOOutput
    $guidFolder2 = Get-ChildItem -Path $gpoDir2 -Directory | Where-Object { $_.Name -match '^\{.*\}$' }

    if ($guidFolder -and $guidFolder2) {
        # Backup folder GUID (= BackupId) must differ
        $backupGuid1 = $guidFolder[0].Name
        $backupGuid2 = $guidFolder2[0].Name
        Assert-Test "BackupGUID differs between runs" ($backupGuid1 -ne $backupGuid2) `
            "Run1=$backupGuid1, Run2=$backupGuid2"

        # Parse XML with [xml] to extract GUIDs safely
        $bkup1Raw = Get-Content (Join-Path $guidFolder[0].FullName "bkupInfo.xml") -Raw
        $bkup2Raw = Get-Content (Join-Path $guidFolder2[0].FullName "bkupInfo.xml") -Raw

        # Extract GPOGuid using Select-String to avoid angle-bracket issues
        $gpoGuid1 = "NOT_FOUND"
        $gpoGuid2 = "NOT_FOUND"
        $pattern = "GPOGuid"
        if ($bkup1Raw -match $pattern) {
            # Parse as XML object
            [xml]$xmlObj1 = $bkup1Raw
            $node1 = $xmlObj1.SelectSingleNode("//*[local-name()='GPOGuid']")
            if ($node1) { $gpoGuid1 = $node1.InnerText.Trim() }
        }
        if ($bkup2Raw -match $pattern) {
            [xml]$xmlObj2 = $bkup2Raw
            $node2 = $xmlObj2.SelectSingleNode("//*[local-name()='GPOGuid']")
            if ($node2) { $gpoGuid2 = $node2.InnerText.Trim() }
        }
        Assert-Test "GPOGuid differs between runs" ($gpoGuid1 -ne $gpoGuid2) `
            "Run1=$gpoGuid1, Run2=$gpoGuid2"

        # BackupId from the ID element
        $id1 = "NOT_FOUND"
        $id2 = "NOT_FOUND"
        if ($xmlObj1) {
            $idNode1 = $xmlObj1.SelectSingleNode("//*[local-name()='ID']")
            if ($idNode1) { $id1 = $idNode1.InnerText.Trim() }
        }
        if ($xmlObj2) {
            $idNode2 = $xmlObj2.SelectSingleNode("//*[local-name()='ID']")
            if ($idNode2) { $id2 = $idNode2.InnerText.Trim() }
        }
        Assert-Test "BackupID differs between runs" ($id1 -ne $id2) `
            "Run1=$id1, Run2=$id2"
    }
    else {
        Assert-Test "BackupGUID differs between runs" $false "Could not find GUID folders in both runs"
        Assert-Test "GPOGuid differs between runs" $false "Skipped"
        Assert-Test "BackupID differs between runs" $false "Skipped"
    }

    # -----------------------------------------------------------
    # 2e. Import-Policy.ps1 - Content Validation
    # -----------------------------------------------------------
    Write-TestHeader "2e. GPO Output - Import-Policy.ps1 Validation"

    $importScript = Join-Path $gpoDir "Import-Policy.ps1"
    if (Test-Path $importScript) {
        $importContent = Get-Content $importScript -Raw

        Assert-Test "Import-Policy.ps1 is not empty" ($importContent.Length -gt 100)

        # Must contain the backup GUID that matches the folder name
        $expectedGuid = $guidFolder[0].Name
        $hasCorrectGuid = $importContent -match [regex]::Escape($expectedGuid)
        Assert-Test "Import-Policy.ps1 contains correct BackupId GUID" $hasCorrectGuid `
            "Expected GUID: $expectedGuid"

        # Must require admin
        $hasAdminReq = $importContent -match "#Requires -RunAsAdministrator"
        Assert-Test "Import-Policy.ps1 requires RunAsAdministrator" $hasAdminReq

        # Must reference Import-GPO
        $hasImportCmd = $importContent -match "Import-GPO"
        Assert-Test "Import-Policy.ps1 calls Import-GPO" $hasImportCmd

        # Must have -CreateIfNeeded
        $hasCreateFlag = $importContent -match "CreateIfNeeded"
        Assert-Test "Import-Policy.ps1 uses -CreateIfNeeded" $hasCreateFlag

        # Syntax check
        $syntaxErrors = $null
        [System.Management.Automation.Language.Parser]::ParseFile(
            $importScript,
            [ref]$null,
            [ref]$syntaxErrors
        ) | Out-Null
        $syntaxMsg = ""
        if ($syntaxErrors.Count -gt 0) { $syntaxMsg = $syntaxErrors[0].Message }
        Assert-Test "Import-Policy.ps1 has valid PowerShell syntax" ($syntaxErrors.Count -eq 0) $syntaxMsg
    }

    # -----------------------------------------------------------
    # 2f. GptTmpl.inf Content Validation
    # -----------------------------------------------------------
    Write-TestHeader "2f. GPO Output - GptTmpl.inf Content"

    $infPath = Join-Path $guidPath "DomainSysvol\GPO\Machine\microsoft\windows nt\SecEdit\GptTmpl.inf"
    if (Test-Path $infPath) {
        $infContent = Get-Content $infPath -Raw

        Assert-Test "GptTmpl.inf is not empty" ($infContent.Length -gt 50)
        Assert-Test "GptTmpl.inf has [Unicode] section" ($infContent -match "\[Unicode\]")
        Assert-Test "GptTmpl.inf has [Version] section" ($infContent -match "\[Version\]")
        Assert-Test 'GptTmpl.inf has $CHICAGO$ signature' ($infContent -match '\$CHICAGO\$')

        # Should have at least one rule-specific section
        $hasPolicySection = ($infContent -match "\[System Access\]") -or
        ($infContent -match "\[Registry Values\]") -or
        ($infContent -match "\[Privilege Rights\]") -or
        ($infContent -match "\[Event Audit\]")
        Assert-Test "GptTmpl.inf has at least one policy section" $hasPolicySection
    }
}
else {
    Write-Host "  [SKIP] GUID folder not found, skipping GPO deep-dive tests" -ForegroundColor Yellow
}

# ===================================================================
# 3. STANDALONE SCRIPT ANALYSIS
# ===================================================================
Write-TestHeader "3. Standalone Script Analysis"

$psScript = $run1.PSOutput

if (Test-Path $psScript) {
    $psContent = Get-Content $psScript -Raw

    # 3a. Basic checks
    Assert-Test "Standalone script is not empty" ($psContent.Length -gt 500)
    Assert-Test "Standalone script has #Requires -RunAsAdministrator" ($psContent -match "#Requires -RunAsAdministrator")
    Assert-Test "Standalone script has CIS header comment" ($psContent -match "CIS Windows Hardening")

    # 3b. Syntax validation (parse without executing)
    $syntaxErrors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        $psScript,
        [ref]$null,
        [ref]$syntaxErrors
    ) | Out-Null
    $syntaxMsg = ""
    if ($syntaxErrors.Count -gt 0) {
        $syntaxMsg = "First error: $($syntaxErrors[0].Message) at line $($syntaxErrors[0].Extent.StartLineNumber)"
    }
    Assert-Test "Standalone script has valid PowerShell syntax" ($syntaxErrors.Count -eq 0) $syntaxMsg

    # 3c. Expected function patterns
    Assert-Test "Script contains Test-CIS_* audit functions" ($psContent -match "function Test-CIS_")
    Assert-Test "Script contains Set-CIS_* remediation functions" ($psContent -match "function Set-CIS_")
    Assert-Test "Script contains Invoke-CISHardening orchestrator" ($psContent -match "function Invoke-CISHardening")

    # 3d. Expected parameters
    Assert-Test "Script has -AuditOnly parameter" ($psContent -match '\$AuditOnly')
    Assert-Test "Script has -Remediate parameter" ($psContent -match '\$Remediate')
    Assert-Test "Script has -GenerateReport parameter" ($psContent -match '\$GenerateReport')

    # 3e. Expected commands/keywords from rules
    $hasSecurityCommands = ($psContent -match "secedit") -or
    ($psContent -match "Set-ItemProperty") -or
    ($psContent -match "net accounts") -or
    ($psContent -match "PasswordHistorySize")
    Assert-Test "Script contains hardening commands (secedit/registry/net accounts)" $hasSecurityCommands

    # 3f. Rule registry (embedded JSON with rule metadata)
    Assert-Test "Script has embedded RuleRegistry" ($psContent -match '\$Script:RuleRegistry')
    Assert-Test "Script has Export-CISReport function" ($psContent -match "function Export-CISReport")

    # 3g. Function count matches rule count
    $auditFuncCount = ([regex]::Matches($psContent, "function Test-CIS_")).Count
    $expectedRules = $run1.RuleCount
    Assert-Test "Audit function count ($auditFuncCount) matches rule count ($expectedRules)" `
    ($auditFuncCount -eq $expectedRules) "Audit=$auditFuncCount, Rules=$expectedRules"
}
else {
    Assert-Test "Standalone script file exists" $false "Not found: $psScript"
}

# ===================================================================
# 4. CROSS-VALIDATION - GPO and Script cover same rules
# ===================================================================
Write-TestHeader "4. Cross-Validation"

if ((Test-Path $psScript) -and $guidFolder) {
    $crossInfPath = Join-Path $guidFolder[0].FullName "DomainSysvol\GPO\Machine\microsoft\windows nt\SecEdit\GptTmpl.inf"
    if (Test-Path $crossInfPath) {
        $crossInfContent = Get-Content $crossInfPath -Raw

        # Check that at least some rule IDs appear in both outputs
        foreach ($file in $ruleFiles | Select-Object -First 3) {
            $rule = Get-Content $file.FullName -Raw | ConvertFrom-Json
            $ruleId = $rule.rule_id
            $funcSuffix = $ruleId -replace '\.', '_'

            # The standalone script should have this rule's audit function
            $inScript = $psContent -match "Test-CIS_$funcSuffix"
            Assert-Test "Rule $ruleId present in standalone script" $inScript

            # If it has GPO inf_key, check GptTmpl.inf
            if ($rule.implementation_gpo -and $rule.implementation_gpo.inf_key) {
                $infKey = $rule.implementation_gpo.inf_key
                $inInf = $crossInfContent -match [regex]::Escape($infKey)
                Assert-Test "Rule $ruleId ($infKey) present in GptTmpl.inf" $inInf
            }
        }
    }
}

# ===================================================================
# Cleanup
# ===================================================================
Write-Host ""
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "  CLEANUP" -ForegroundColor Cyan
Write-Host ("=" * 70) -ForegroundColor Cyan

try {
    Remove-Item -Path $testOutput -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  Temp directory cleaned: $testOutput" -ForegroundColor Gray
}
catch {
    Write-Host "  Warning: Could not clean temp dir: $testOutput" -ForegroundColor Yellow
}

# ===================================================================
# Final Report
# ===================================================================
Write-Host ""
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "  FINAL REPORT" -ForegroundColor Cyan
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host ""

$total = $Script:PassCount + $Script:FailCount
$passRate = if ($total -gt 0) { [math]::Round(($Script:PassCount / $total) * 100, 1) } else { 0 }

Write-Host "  Total Tests : $total"
Write-Host "  Passed      : " -NoNewline; Write-Host $Script:PassCount -ForegroundColor Green
$failColor = if ($Script:FailCount -eq 0) { "Green" } else { "Red" }
Write-Host "  Failed      : " -NoNewline; Write-Host $Script:FailCount -ForegroundColor $failColor
Write-Host "  Pass Rate   : " -NoNewline

$rateColor = if ($passRate -eq 100) { "Green" } elseif ($passRate -ge 80) { "Yellow" } else { "Red" }
Write-Host "$passRate%" -ForegroundColor $rateColor
Write-Host ""

if ($Script:FailCount -eq 0) {
    Write-Host "  [OK] ALL TESTS PASSED - Tools are production-ready." -ForegroundColor Green
}
else {
    Write-Host "  [!!] $($Script:FailCount) TEST(S) FAILED - Review output above." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Failed tests:" -ForegroundColor Yellow
    $Script:TestResults | Where-Object { $_.Result -eq "FAIL" } | ForEach-Object {
        Write-Host "    - $($_.Test)" -ForegroundColor Red
        if ($_.Detail) { Write-Host "      $($_.Detail)" -ForegroundColor DarkRed }
    }
}

Write-Host ""

# Exit with appropriate code for CI/CD
exit $Script:FailCount
