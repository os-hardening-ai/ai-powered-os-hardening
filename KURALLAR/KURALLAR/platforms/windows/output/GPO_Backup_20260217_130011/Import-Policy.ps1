#Requires -RunAsAdministrator
#Requires -Modules GroupPolicy
<#
.SYNOPSIS
    Imports the CIS Hardening GPO backup into your Active Directory environment.

.DESCRIPTION
    This script imports the pre-configured CIS Benchmark hardening policy
    into your domain as a new Group Policy Object.

    Generated: 2026-02-17T13:00:11
    GPO Name:  CIS_Hardening_20260217_130011
    Rules:     7
#   - CIS 1.1.1: Ensure 'Enforce password history' is set to '24 or more password(s)'
#   - CIS 1.1.2: Ensure 'Maximum password age' is set to '365 or fewer days, but not 0'
#   - CIS 1.1.3: Ensure 'Minimum password age' is set to '1 or more day(s)'
#   - CIS 1.1.4: Ensure 'Minimum password length' is set to '14 or more character(s)'
#   - CIS 1.1.5: Ensure 'Password must meet complexity requirements' is set to 'Enabled'
#   - CIS 1.1.6: Ensure 'Relax minimum password length limits' is set to 'Enabled'
#   - CIS 1.1.7: Ensure 'Store passwords using reversible encryption' is set to 'Disabled'

.PARAMETER TargetName
    Name for the imported GPO. Defaults to 'CIS_Hardening_20260217_130011'.

.PARAMETER Force
    Skip the confirmation prompt.

.EXAMPLE
    .\Import-Policy.ps1
    # Imports with default name, prompts for confirmation

.EXAMPLE
    .\Import-Policy.ps1 -TargetName "Production CIS Policy" -Force
    # Imports with custom name, no confirmation

.NOTES
    - Must be run on a Domain Controller or a machine with RSAT-GroupPolicy installed
    - Requires Domain Admin or equivalent GPO management permissions
    - The imported GPO is NOT linked to any OU by default â€” link it manually after review
#>
[CmdletBinding()]
param(
    [Parameter()]
    [string]$TargetName = "CIS_Hardening_20260217_130011",

    [Parameter()]
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# â”€â”€ Pre-flight checks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
try {
    Import-Module GroupPolicy -ErrorAction Stop
} catch {
    Write-Error "GroupPolicy module not found. Install RSAT or run this on a Domain Controller."
    exit 1
}

# Resolve paths relative to this script's location
$backupPath = $PSScriptRoot
$backupId   = "{ED1C8F85-AABE-429E-9BE2-98A0BCC34E87}"

# â”€â”€ Confirmation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Write-Host ""
Write-Host "â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—" -ForegroundColor Cyan
Write-Host "â•‘          CIS Hardening GPO Import Utility                  â•‘" -ForegroundColor Cyan
Write-Host "â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backup Path : $backupPath"  -ForegroundColor Gray
Write-Host "  Backup ID   : $backupId"    -ForegroundColor Gray
Write-Host "  Target GPO  : $TargetName"  -ForegroundColor White
Write-Host "  Rules Count : 7"          -ForegroundColor Gray
Write-Host ""

if (-not $Force) {
    $confirm = Read-Host "Import this GPO into your domain? (Y/N)"
    if ($confirm -notin @('Y', 'y', 'Yes', 'yes')) {
        Write-Host "Import cancelled." -ForegroundColor Yellow
        exit 0
    }
}

# â”€â”€ Import â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Write-Host ""
Write-Host "[*] Importing GPO backup..." -ForegroundColor Cyan

try {
    $result = Import-GPO `
        -BackupId $backupId `
        -Path $backupPath `
        -TargetName $TargetName `
        -CreateIfNeeded

    Write-Host ""
    Write-Host "[+] GPO imported successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  GPO Name    : $($result.DisplayName)" -ForegroundColor White
    Write-Host "  GPO ID      : $($result.Id)"          -ForegroundColor Gray
    Write-Host "  Domain      : $($result.DomainName)"  -ForegroundColor Gray
    Write-Host ""
    Write-Host "[!] IMPORTANT: The GPO is NOT linked to any OU yet." -ForegroundColor Yellow
    Write-Host "    Review the settings in GPMC, then link it to the appropriate OU." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "    Example to link via PowerShell:" -ForegroundColor Gray
    Write-Host "    New-GPLink -Name '$TargetName' -Target 'OU=Workstations,DC=yourdomain,DC=com'" -ForegroundColor DarkGray
    Write-Host ""
} catch {
    Write-Host ""
    Write-Host "[X] Import failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "    Common causes:" -ForegroundColor Yellow
    Write-Host "    - Not running as Domain Admin" -ForegroundColor Gray
    Write-Host "    - GroupPolicy module not available" -ForegroundColor Gray
    Write-Host "    - Backup folder structure is incomplete" -ForegroundColor Gray
    exit 1
}
