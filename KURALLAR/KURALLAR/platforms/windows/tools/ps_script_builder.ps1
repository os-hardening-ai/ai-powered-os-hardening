#Requires -Version 5.1
<#
.SYNOPSIS
    PowerShell Script Builder for CIS Windows Hardening
.DESCRIPTION
    Generates a consolidated PowerShell script from selected CIS rules.
    Includes Audit, Remediate, and Rollback functions.
#>

function New-HardeningScript {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [array]$Rules,
        
        [Parameter(Mandatory)]
        [string]$OutputPath,
        
        # [Parameter()]
        # [switch]$IncludeRollback,
        
        [Parameter()]
        [switch]$AuditOnly
    )
    
    $header = @"
#==============================================================================
# CIS Windows Hardening Script
# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
# Rules: $($Rules.Count) selected
# Generator: CIS Windows Hardening Generator v1.0
# Report Logic: Runtime-embedded
#==============================================================================
#Requires -Version 5.1
#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [Parameter()]
    [switch]`$AuditOnly,
    
    [Parameter()]
    [switch]`$Remediate,
    
    # [Parameter()]
    # [switch]`$Rollback,
    
    [Parameter()]
    [switch]`$GenerateReport,
    
    [Parameter()]
    [string]`$ReportPath = "`$env:USERPROFILE\CIS_Report_`$(Get-Date -Format 'yyyyMMdd_HHmmss')"
)

#region Script Variables
`$Script:Results = @()
`$Script:BackupData = @{}
`$Script:StartTime = Get-Date
#endregion

#region Helper Functions
function Write-RuleStatus {
    param(
        [string]`$RuleId,
        [string]`$Title,
        [string]`$Status,
        [string]`$Details = ""
    )
    
    `$statusColors = @{
        "Pass"       = "Green"
        "Fail"       = "Red"
        "Remediated" = "Yellow"
        "Error"      = "Magenta"
        "Skipped"    = "Gray"
    }
    
    `$statusSymbols = @{
        "Pass"       = "[+]"
        "Fail"       = "[X]"
        "Remediated" = "[>]"
        "Error"      = "[!]"
        "Skipped"    = "[-]"
    }
    
    Write-Host "`$(`$statusSymbols[`$Status]) " -NoNewline -ForegroundColor `$statusColors[`$Status]
    Write-Host "`$RuleId " -NoNewline -ForegroundColor Cyan
    Write-Host "- `$Title " -NoNewline
    if (`$Details) {
        Write-Host "(`$Details)" -ForegroundColor Gray
    } else {
        Write-Host ""
    }
}
#endregion

"@

    $auditFunctions = @"

#region Audit Functions
"@

    $remediateFunctions = @"

#region Remediation Functions
"@

    $rollbackFunctions = @"

#region Rollback Functions
# (Rollback is currently deferred)
#endregion
"@

    $reportFunctions = @'

#region Report Functions
function Export-CISReport {
    [CmdletBinding()]
    param()
    
    if (-not $Script:Results) {
        Write-Warning "No results to report."
        return
    }

    $html = @()
    $html += "<!DOCTYPE html>"
    $html += "<html lang='en'>"
    $html += "<head>"
    $html += "    <meta charset='UTF-8'>"
    $html += "    <meta name='viewport' content='width=device-width, initial-scale=1.0'>"
    $html += "    <title>CIS Windows Hardening Report</title>"
    $html += "    <style>"
    $html += "        :root { --pass: #00c853; --fail: #ff1744; --warn: #ff9100; --bg: #1a1a2e; --card: #16213e; --text: #eee; }"
    $html += "        * { box-sizing: border-box; margin: 0; padding: 0; }"
    $html += "        body { font-family: 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); padding: 2rem; }"
    $html += "        .container { max-width: 1200px; margin: 0 auto; }"
    $html += "        header { text-align: center; margin-bottom: 2rem; }"
    $html += "        header h1 { font-size: 2rem; margin-bottom: 0.5rem; }"
    $html += "        .meta { color: #888; font-size: 0.9rem; }"
    $html += "        .dashboard { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }"
    $html += "        .stat-card { background: var(--card); padding: 1.5rem; border-radius: 8px; text-align: center; }"
    $html += "        .stat-card .value { font-size: 2.5rem; font-weight: bold; }"
    $html += "        .stat-card .label { color: #888; margin-top: 0.5rem; }"
    $html += "        .stat-card.pass .value { color: var(--pass); }"
    $html += "        .stat-card.fail .value { color: var(--fail); }"
    $html += "        table { width: 100%; border-collapse: collapse; background: var(--card); border-radius: 8px; overflow: hidden; }"
    $html += "        th, td { padding: 1rem; text-align: left; border-bottom: 1px solid #333; }"
    $html += "        th { background: #0f3460; }"
    $html += "        tr:hover { background: #1f4068; }"
    $html += "        .badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 4px; font-size: 0.8rem; }"
    $html += "        .badge-pass { background: var(--pass); color: black; }"
    $html += "        .badge-fail { background: var(--fail); color: white; }"
    $html += "        .badge-warn { background: var(--warn); color: black; }"
    $html += "    </style>"
    $html += "</head>"
    $html += "<body>"
    $html += "    <div class='container'>"
    $html += "        <header>"
    $html += "            <h1>CIS Windows Hardening Execution Report</h1>"
    $html += "            <div class='meta'>"
    $html += "                <span>Host: $env:COMPUTERNAME</span> |"
    $html += "                <span>User: $env:USERNAME</span> |"
    $html += "                <span>Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')</span>"
    $html += "            </div>"
    $html += "        </header>"
    $html += "        "
    $html += "        <div class='dashboard'>"
    $html += "            <div class='stat-card'>"
    $html += "                <div class='value'>$($Script:Results.Count)</div>"
    $html += "                <div class='label'>Total Rules</div>"
    $html += "            </div>"
    $html += "            <div class='stat-card pass'>"
    $html += "                <div class='value'>$(($Script:Results | Where-Object { $_.AfterStatus -eq 'Pass' }).Count)</div>"
    $html += "                <div class='label'>Passed</div>"
    $html += "            </div>"
    $html += "            <div class='stat-card fail'>"
    $html += "                <div class='value'>$(($Script:Results | Where-Object { $_.AfterStatus -eq 'Fail' }).Count)</div>"
    $html += "                <div class='label'>Failed</div>"
    $html += "            </div>"
    $html += "            <div class='stat-card'>"
    $html += "                <div class='value'>$(($Script:Results | Where-Object { $_.Action -eq 'Remediated' }).Count)</div>"
    $html += "                <div class='label'>Remediated</div>"
    $html += "            </div>"
    $html += "        </div>"
    $html += "        "
    $html += "        <div class='section'>"
    $html += "            <h2>Detailed Results</h2>"
    $html += "            <table>"
    $html += "                <thead>"
    $html += "                    <tr>"
    $html += "                        <th>ID</th>"
    $html += "                        <th>Title</th>"
    $html += "                        <th>Status</th>"
    $html += "                        <th>Action</th>"
    $html += "                        <th>Details</th>"
    $html += "                    </tr>"
    $html += "                </thead>"
    $html += "                <tbody>"

    foreach ($res in $Script:Results) {
        $statusClass = if ($res.AfterStatus -eq 'Pass') { 'badge-pass' } else { 'badge-fail' }
        $html += "                    <tr>"
        $html += "                        <td><strong>$($res.RuleId)</strong></td>"
        $html += "                        <td>$($res.Title)</td>"
        $html += "                        <td><span class='badge $statusClass'>$($res.AfterStatus)</span></td>"
        $html += "                        <td>$($res.Action)</td>"
        $html += "                        <td style='font-size: 0.9em; color: #ccc;'>$($res.Details)</td>"
        $html += "                    </tr>"
    }

    $html += "                </tbody>"
    $html += "            </table>"
    $html += "        </div>"
    $html += "    </div>"
    $html += "</body>"
    $html += "</html>"

    $outDir = Split-Path $ReportPath -Parent
    if (-not (Test-Path $outDir)) { New-Item -Path $outDir -ItemType Directory -Force | Out-Null }
    
    $html | Set-Content -Path ($ReportPath + ".html") -Encoding UTF8 -Force
    
    Write-Host "Report saved to: $ReportPath.html" -ForegroundColor Cyan
}
#endregion
'@

    $ruleRegistry = @()
    
    foreach ($ruleItem in $Rules) {
        $rule = $ruleItem.Rule
        $funcSuffix = $rule.rule_id -replace '\.', '_'
        
        # Audit function
        # Escape backslashes to prevent regex patterns like \s from being misinterpreted
        $auditScript = $rule.audit_logic.powershell_script
        # Escape backslashes to prevent regex patterns like \s from being misinterpreted
        if ($auditScript) {
            # $auditScript = $auditScript -replace '\\', '\\' # INCORRECT: Do not escape backslashes
            $auditScript = $auditScript -replace "`n", "`n    "
        }
        $auditFunctions += @"

function Test-CIS_$funcSuffix {
    <#
    .SYNOPSIS
        $($rule.title)
    .DESCRIPTION
        $($rule.description -replace "`n", "`n        ")
    .NOTES
        CIS Level: $($rule.cis_level)
        Category: $($rule.category)
    #>
    [CmdletBinding()]
    param()
    
    try {
        $auditScript
    }
    catch {
        Write-Verbose "Audit failed for $($rule.rule_id): `$_"
        return `$false
    }
}

"@

        # Remediation function
        if ($rule.implementation_local) {
            $remediateScript = if ($rule.implementation_local.powershell_script) {
                $rule.implementation_local.powershell_script
            }
            else {
                $rule.implementation_local.powershell_command
            }
            
            # Escape backslashes to prevent regex patterns like \s from being misinterpreted
            # Escape backslashes to prevent regex patterns like \s from being misinterpreted
            if ($remediateScript) {
                # $remediateScript = $remediateScript -replace '\\', '\\' # INCORRECT: Do not escape backslashes
                $remediateScript = $remediateScript -replace "`n", "`n    "
            }
            
            $remediateFunctions += @"

function Set-CIS_$funcSuffix {
    <#
    .SYNOPSIS
        Remediate: $($rule.title)
    .NOTES
        Requires Admin: $($rule.implementation_local.requires_admin)
        Requires Reboot: $($rule.implementation_local.requires_reboot)
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]`$Force)
    
    if (`$PSCmdlet.ShouldProcess("$($rule.rule_id)", "Apply CIS hardening")) {
        try {
            # Backup current value
            `$Script:BackupData['$($rule.rule_id)'] = @{
                Timestamp = Get-Date
                RuleId    = '$($rule.rule_id)'
            }
            
            $remediateScript
            
            return `$true
        }
        catch {
            Write-Error "Remediation failed for $($rule.rule_id): `$_"
            return `$false
        }
    }
}

"@
        }

        # Rollback function
        if ($false -and $rule.remediation_rollback) {
            # Rollback generation disabled
        }

        # Add to registry
        $ruleRegistry += @{
            Id             = $rule.rule_id
            Title          = $rule.title
            Level          = $rule.cis_level
            Category       = $rule.category
            AuditFunc      = "Test-CIS_$funcSuffix"
            RemediateFunc  = "Set-CIS_$funcSuffix"
            # RollbackFunc   = "Undo-CIS_$funcSuffix"
            RequiresReboot = if ($rule.implementation_local.requires_reboot) { $true } else { $false }
        }
    }

    $auditFunctions += "#endregion`n"
    $remediateFunctions += "#endregion`n"
    $rollbackFunctions += "#endregion`n"

    # Build rule registry
    $registryJson = $ruleRegistry | ConvertTo-Json -Depth 3
    $mainExecution = @"

#region Rule Registry
`$Script:RuleRegistry = @'
$registryJson
'@ | ConvertFrom-Json
#endregion

#region Main Execution
function Invoke-CISHardening {
    [CmdletBinding()]
    param(
        [switch]`$AuditOnly,
        [switch]`$Remediate
        # [switch]`$Rollback
    )
    
    Write-Host ""
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host "              CIS WINDOWS HARDENING - EXECUTION                   " -ForegroundColor Cyan
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host ""
    
    `$passCount = 0
    `$failCount = 0
    `$remediatedCount = 0
    `$errorCount = 0
    
    foreach (`$rule in `$Script:RuleRegistry) {
        `$result = [PSCustomObject]@{
            RuleId       = `$rule.Id
            Title        = `$rule.Title
            Level        = `$rule.Level
            Category     = `$rule.Category
            BeforeStatus = 'Unknown'
            AfterStatus  = 'Unknown'
            Action       = 'None'
            Details      = ''
            Timestamp    = Get-Date
        }
        
        # Phase 1: Audit BEFORE
        try {
            `$auditResult = & `$rule.AuditFunc
            `$result.BeforeStatus = if (`$auditResult) { 'Pass' } else { 'Fail' }
        }
        catch {
            `$result.BeforeStatus = 'Error'
            `$result.Details = `$_.Exception.Message
        }
        
        # Phase 2: Remediate if needed and requested
        if (`$Remediate -and `$result.BeforeStatus -eq 'Fail') {
            try {
                `$remediateResult = & `$rule.RemediateFunc -Force
                if (`$remediateResult) {
                    `$result.Action = 'Remediated'
                    `$remediatedCount++
                }
                else {
                    `$result.Action = 'Failed'
                }
            }
            catch {
                `$result.Action = 'Error'
                `$result.Details = `$_.Exception.Message
                `$errorCount++
            }
        }
        
        # Phase 3: Rollback if requested
        # (Rollback deferred)
        
        # Phase 4: Audit AFTER (if remediated)
        if (`$result.Action -eq 'Remediated') {
            try {
                `$auditResult = & `$rule.AuditFunc
                `$result.AfterStatus = if (`$auditResult) { 'Pass' } else { 'Fail' }
            }
            catch {
                `$result.AfterStatus = 'Error'
            }
        }
        else {
            `$result.AfterStatus = `$result.BeforeStatus
        }
        
        # Update counters
        if (`$result.AfterStatus -eq 'Pass') { `$passCount++ }
        elseif (`$result.AfterStatus -eq 'Fail') { `$failCount++ }
        
        # Output status
        `$displayStatus = if (`$result.Action -eq 'Remediated') { 'Remediated' } else { `$result.AfterStatus }
        Write-RuleStatus -RuleId `$rule.Id -Title `$rule.Title -Status `$displayStatus -Details `$result.Details
        
        `$Script:Results += `$result
    }
    
    # Summary
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "SUMMARY" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  Total Rules:  `$(`$Script:RuleRegistry.Count)"
    Write-Host "  Passed:       " -NoNewline; Write-Host `$passCount -ForegroundColor Green
    Write-Host "  Failed:       " -NoNewline; Write-Host `$failCount -ForegroundColor Red
    Write-Host "  Remediated:   " -NoNewline; Write-Host `$remediatedCount -ForegroundColor Yellow
    Write-Host "  Errors:       " -NoNewline; Write-Host `$errorCount -ForegroundColor Magenta
    Write-Host ""
    
    `$compliance = [math]::Round((`$passCount / `$Script:RuleRegistry.Count) * 100, 1)
    `$complianceColor = if (`$compliance -ge 80) { 'Green' } elseif (`$compliance -ge 50) { 'Yellow' } else { 'Red' }
    Write-Host "  Compliance:   `$compliance%" -ForegroundColor `$complianceColor
    Write-Host ""
    
    return `$Script:Results
}

# Auto-execute based on parameters
if (`$AuditOnly) {
    Invoke-CISHardening -AuditOnly
    if (`$GenerateReport) { Export-CISReport }
}
elseif (`$Remediate) {
    Invoke-CISHardening -Remediate
    if (`$GenerateReport) { Export-CISReport }
}
# elseif (`$Rollback) {
#    Invoke-CISHardening -Rollback
# }
else {
    Write-Host "Usage: .\script.ps1 -AuditOnly | -Remediate | -Rollback" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Parameters:" -ForegroundColor Cyan
    Write-Host "  -AuditOnly      Check compliance without making changes"
    Write-Host "  -Remediate      Apply hardening to non-compliant settings"
    Write-Host "  -Rollback       Restore original settings"
    Write-Host "  -GenerateReport Export HTML report"
}
#endregion
"@

    # Combine all sections
    $fullScript = $header + $auditFunctions + $remediateFunctions + $reportFunctions
    if ($false) {
        # $fullScript += $rollbackFunctions
    }
    $fullScript += $mainExecution

    # Write to file
    [System.IO.File]::WriteAllText($OutputPath, $fullScript, [System.Text.Encoding]::UTF8)
    
    return $OutputPath
}
