$ErrorActionPreference = "Stop"

function Write-Log ($Message) {
    Write-Host "[*] $Message" -ForegroundColor Cyan
}

$scriptPath = $MyInvocation.MyCommand.Definition
$scriptDir = Split-Path -Parent $scriptPath
$rulesPath = Join-Path $scriptDir "..\rules"
$outputPath = Join-Path $scriptDir "..\output"

Write-Log "Script Dir: $scriptDir"
Write-Log "Rules Path: $rulesPath"
Write-Log "Output Path: $outputPath"

if (-not (Test-Path $outputPath)) {
    New-Item -Path $outputPath -ItemType Directory -Force | Out-Null
    Write-Log "Created output dir"
}

$rules = Get-ChildItem -Path $rulesPath -Filter "*.json" -Recurse
Write-Log "Found $($rules.Count) rules"

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$psOutput = Join-Path $outputPath "CIS_Hardening_${timestamp}.ps1"
Write-Log "Target PS Output: $psOutput"

# Load builder
. (Join-Path $scriptDir "ps_script_builder.ps1")
. (Join-Path $scriptDir "gpo_builder.ps1")
. (Join-Path $scriptDir "registry_pol_writer.ps1")

# Process rules
$processedRules = @()
foreach ($file in $rules) {
    $content = Get-Content $file.FullName -Raw | ConvertFrom-Json
    $processedRules += [PSCustomObject]@{
        Rule = $content
    }
}

# Generate PS1
# Generate PS1
New-HardeningScript -Rules $processedRules -OutputPath $psOutput
# -IncludeRollback:$false (Deferred)
Write-Log "Generated PS1"

# Generate GPO Backup
$gpoOutput = Join-Path $outputPath "GPO_Backup_${timestamp}"
if (-not (Test-Path $gpoOutput)) {
    New-Item -Path $gpoOutput -ItemType Directory -Force | Out-Null
}
New-GPOBackup -Rules $processedRules -OutputPath $gpoOutput -GPOName "CIS_Hardening_${timestamp}"
Write-Log "Generated GPO Backup: $gpoOutput"

# Generate Report
# (Static report generation removed. Reports are now generated at runtime.)
# $reportOutput = Join-Path $outputPath "CIS_Report_${timestamp}.html"
# . (Join-Path $scriptDir "report_generator.ps1")
# New-HardeningReport -Rules $processedRules -OutputPath $reportOutput
# Write-Log "Generated Report: $reportOutput"

Write-Log "Done!"
