#==============================================================================
# CIS Windows Hardening Script
# Generated: 2026-01-30 19:25:19
# Rules: 7 selected
# Generator: CIS Windows Hardening Generator v1.0
# Report Logic: Runtime-embedded
#==============================================================================
#Requires -Version 5.1
#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [Parameter()]
    [switch]$AuditOnly,
    
    [Parameter()]
    [switch]$Remediate,
    
    # [Parameter()]
    # [switch]$Rollback,
    
    [Parameter()]
    [switch]$GenerateReport,
    
    [Parameter()]
    [string]$ReportPath = "$env:USERPROFILE\CIS_Report_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
)

#region Script Variables
$Script:Results = @()
$Script:BackupData = @{}
$Script:StartTime = Get-Date
#endregion

#region Helper Functions
function Write-RuleStatus {
    param(
        [string]$RuleId,
        [string]$Title,
        [string]$Status,
        [string]$Details = ""
    )
    
    $statusColors = @{
        "Pass"       = "Green"
        "Fail"       = "Red"
        "Remediated" = "Yellow"
        "Error"      = "Magenta"
        "Skipped"    = "Gray"
    }
    
    $statusSymbols = @{
        "Pass"       = "[+]"
        "Fail"       = "[X]"
        "Remediated" = "[>]"
        "Error"      = "[!]"
        "Skipped"    = "[-]"
    }
    
    Write-Host "$($statusSymbols[$Status]) " -NoNewline -ForegroundColor $statusColors[$Status]
    Write-Host "$RuleId " -NoNewline -ForegroundColor Cyan
    Write-Host "- $Title " -NoNewline
    if ($Details) {
        Write-Host "($Details)" -ForegroundColor Gray
    }
    else {
        Write-Host ""
    }
}
#endregion

#region Audit Functions
function Test-CIS_1_1_1 {
    <#
    .SYNOPSIS
        Ensure 'Enforce password history' is set to '24 or more password(s)'
    .DESCRIPTION
        This policy setting determines the number of renewed, unique passwords that have to be associated with a user account before you can reuse an old password. The value for this policy setting must be between 0 and 24 passwords. The default value for standalone systems is 0 passwords, but the default setting when joined to a domain is 24 passwords. To maintain the effectiveness of this policy setting, use the Minimum password age setting to prevent users from repeatedly changing their password. The recommended state for this setting is: 24 or more password(s).
    .NOTES
        CIS Level: 1
        Category: Account Policies
    #>
    [CmdletBinding()]
    param()
    
    try {
        try {
            $output = net accounts 2>&1
            $historyLine = $output | Select-String 'Length of password history maintained'
            if ($historyLine) {
                $value = [int]($historyLine -replace '.*:\s*(\d+).*', '$1')
                return ($value -ge 24)
            }
        
            # Alternative: Check via secedit export
            $tempFile = "$env:TEMP\secpol_audit_$([guid]::NewGuid().ToString('N')).cfg"
            secedit /export /cfg $tempFile /quiet 2>&1 | Out-Null
        
            if (Test-Path $tempFile) {
                $content = Get-Content $tempFile -Raw
                Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
            
                if ($content -match 'PasswordHistorySize\s*=\s*(\d+)') {
                    $value = [int]$Matches[1]
                    return ($value -ge 24)
                }
            }
        
            return $false
        }
        catch {
            return $false
        }
    }
    catch {
        Write-Verbose "Audit failed for 1.1.1: $_"
        return $false
    }
}

function Test-CIS_1_1_2 {
    <#
    .SYNOPSIS
        Ensure 'Maximum password age' is set to '365 or fewer days, but not 0'
    .DESCRIPTION
        This policy setting defines how long a user can use their password before it expires. Values for this policy setting range from 0 to 999 days. If you set the value to 0, the password will never expire. Because attackers can crack passwords, the more frequently you change the password the less opportunity an attacker has to use a cracked password. The recommended state for this setting is 365 or fewer days, but not 0.
    .NOTES
        CIS Level: 1
        Category: Account Policies
    #>
    [CmdletBinding()]
    param()
    
    try {
        try {
            $output = net accounts 2>&1
            $maxAgeLine = $output | Select-String 'Maximum password age'
            if ($maxAgeLine) {
                $valueStr = ($maxAgeLine -replace '.*:\s*', '').Trim()
                if ($valueStr -match 'Unlimited' -or $valueStr -eq '0') {
                    return $false
                }
                $value = [int]($valueStr -replace '[^0-9]', '')
                return ($value -ge 1 -and $value -le 365)
            }
            return $false
        }
        catch {
            return $false
        }
    }
    catch {
        Write-Verbose "Audit failed for 1.1.2: $_"
        return $false
    }
}

function Test-CIS_1_1_3 {
    <#
    .SYNOPSIS
        Ensure 'Minimum password age' is set to '1 or more day(s)'
    .DESCRIPTION
        This policy setting determines the number of days that you must use a password before you can change it. The range of values for this policy setting is between 1 and 999 days. You may also set the value to 0 to allow immediate password changes. The default value for this setting is 0 days. The recommended state for this setting is: 1 or more day(s).
    .NOTES
        CIS Level: 1
        Category: Account Policies
    #>
    [CmdletBinding()]
    param()
    
    try {
        try {
            $output = net accounts 2>&1
            $minAgeLine = $output | Select-String 'Minimum password age'
            if ($minAgeLine) {
                $value = [int](($minAgeLine -replace '.*:\s*', '').Trim() -replace '[^0-9]', '')
                return ($value -ge 1)
            }
            return $false
        }
        catch {
            return $false
        }
    }
    catch {
        Write-Verbose "Audit failed for 1.1.3: $_"
        return $false
    }
}

function Test-CIS_1_1_4 {
    <#
    .SYNOPSIS
        Ensure 'Minimum password length' is set to '14 or more character(s)'
    .DESCRIPTION
        This policy setting determines the least number of characters that make up a password for a user account. In enterprise environments, the ideal value for the Minimum password length setting is 14 characters, however you should adjust this value to meet your organization's business requirements. The recommended state for this setting is: 14 or more character(s).
    .NOTES
        CIS Level: 1
        Category: Account Policies
    #>
    [CmdletBinding()]
    param()
    
    try {
        try {
            $output = net accounts 2>&1
            $minLenLine = $output | Select-String 'Minimum password length'
            if ($minLenLine) {
                $value = [int](($minLenLine -replace '.*:\s*', '').Trim() -replace '[^0-9]', '')
                return ($value -ge 14)
            }
            return $false
        }
        catch {
            return $false
        }
    }
    catch {
        Write-Verbose "Audit failed for 1.1.4: $_"
        return $false
    }
}

function Test-CIS_1_1_5 {
    <#
    .SYNOPSIS
        Ensure 'Password must meet complexity requirements' is set to 'Enabled'
    .DESCRIPTION
        This policy setting checks all new passwords to ensure that they meet basic requirements for strong passwords. When enabled, passwords must: not contain the user's account name, be at least six characters in length, and contain characters from three of five categories (uppercase, lowercase, digits, non-alphabetic, Unicode). The recommended state for this setting is: Enabled.
    .NOTES
        CIS Level: 1
        Category: Account Policies
    #>
    [CmdletBinding()]
    param()
    
    try {
        try {
            $tempFile = "$env:TEMP\secpol_audit_$([guid]::NewGuid().ToString('N')).cfg"
            secedit /export /cfg $tempFile /quiet 2>&1 | Out-Null
            if (Test-Path $tempFile) {
                $content = Get-Content $tempFile -Raw
                Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
                if ($content -match 'PasswordComplexity\s*=\s*(\d+)') {
                    return ([int]$Matches[1] -eq 1)
                }
            }
            return $false
        }
        catch {
            return $false
        }
    }
    catch {
        Write-Verbose "Audit failed for 1.1.5: $_"
        return $false
    }
}

function Test-CIS_1_1_6 {
    <#
    .SYNOPSIS
        Ensure 'Relax minimum password length limits' is set to 'Enabled'
    .DESCRIPTION
        This policy setting determines whether the minimum password length setting can be increased beyond the legacy limit of 14 characters. The recommended state for this setting is: Enabled. Note: This setting only affects local accounts on the computer. Domain accounts are only affected by settings on the Domain Controllers.
    .NOTES
        CIS Level: 1
        Category: Account Policies
    #>
    [CmdletBinding()]
    param()
    
    try {
        try {
            $value = (Get-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\SAM' -Name 'RelaxMinimumPasswordLengthLimits' -ErrorAction SilentlyContinue).RelaxMinimumPasswordLengthLimits
            return ($value -eq 1)
        }
        catch {
            return $false
        }
    }
    catch {
        Write-Verbose "Audit failed for 1.1.6: $_"
        return $false
    }
}

function Test-CIS_1_1_7 {
    <#
    .SYNOPSIS
        Ensure 'Store passwords using reversible encryption' is set to 'Disabled'
    .DESCRIPTION
        This policy setting determines whether the operating system stores passwords in a way that uses reversible encryption, which provides support for application protocols that require knowledge of the user's password for authentication purposes. Passwords that are stored with reversible encryption are essentially the same as plaintext versions of the passwords. The recommended state for this setting is: Disabled.
    .NOTES
        CIS Level: 1
        Category: Account Policies
    #>
    [CmdletBinding()]
    param()
    
    try {
        try {
            $tempFile = "$env:TEMP\secpol_audit_$([guid]::NewGuid().ToString('N')).cfg"
            secedit /export /cfg $tempFile /quiet 2>&1 | Out-Null
            if (Test-Path $tempFile) {
                $content = Get-Content $tempFile -Raw
                Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
                if ($content -match 'ClearTextPassword\s*=\s*(\d+)') {
                    return ([int]$Matches[1] -eq 0)
                }
                # If not explicitly set, default is 0 (Disabled)
                return $true
            }
            return $false
        }
        catch {
            return $false
        }
    }
    catch {
        Write-Verbose "Audit failed for 1.1.7: $_"
        return $false
    }
}
#endregion

#region Remediation Functions
function Set-CIS_1_1_1 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Enforce password history' is set to '24 or more password(s)'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("1.1.1", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['1.1.1'] = @{
                Timestamp = Get-Date
                RuleId    = '1.1.1'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
            $seceditImport = "$env:TEMP\secpol_import.cfg"
    
            # Export current security policy
            secedit /export /cfg $seceditExport /quiet
    
            # Read and modify
            $content = Get-Content $seceditExport
            $content = $content -replace 'PasswordHistorySize\s*=\s*\d+', 'PasswordHistorySize = 24'
    
            # If setting doesn't exist, add it
            if ($content -notmatch 'PasswordHistorySize') {
                $content = $content -replace '(\[System Access\])', "`$1`nPasswordHistorySize = 24"
            }
    
            $content | Set-Content $seceditImport -Force
    
            # Import modified policy
            secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    
            # Cleanup
            Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 1.1.1: $_"
            return $false
        }
    }
}

function Set-CIS_1_1_2 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Maximum password age' is set to '365 or fewer days, but not 0'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("1.1.2", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['1.1.2'] = @{
                Timestamp = Get-Date
                RuleId    = '1.1.2'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
            $seceditImport = "$env:TEMP\secpol_import.cfg"
            secedit /export /cfg $seceditExport /quiet
            $content = Get-Content $seceditExport
            $content = $content -replace 'MaximumPasswordAge\s*=\s*\d+', 'MaximumPasswordAge = 365'
            if ($content -notmatch 'MaximumPasswordAge') {
                $content = $content -replace '(\[System Access\])', "`$1`nMaximumPasswordAge = 365"
            }
            $content | Set-Content $seceditImport -Force
            secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
            Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 1.1.2: $_"
            return $false
        }
    }
}

function Set-CIS_1_1_3 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Minimum password age' is set to '1 or more day(s)'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("1.1.3", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['1.1.3'] = @{
                Timestamp = Get-Date
                RuleId    = '1.1.3'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
            $seceditImport = "$env:TEMP\secpol_import.cfg"
            secedit /export /cfg $seceditExport /quiet
            $content = Get-Content $seceditExport
            $content = $content -replace 'MinimumPasswordAge\s*=\s*\d+', 'MinimumPasswordAge = 1'
            if ($content -notmatch 'MinimumPasswordAge') {
                $content = $content -replace '(\[System Access\])', "`$1`nMinimumPasswordAge = 1"
            }
            $content | Set-Content $seceditImport -Force
            secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
            Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 1.1.3: $_"
            return $false
        }
    }
}

function Set-CIS_1_1_4 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Minimum password length' is set to '14 or more character(s)'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("1.1.4", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['1.1.4'] = @{
                Timestamp = Get-Date
                RuleId    = '1.1.4'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
            $seceditImport = "$env:TEMP\secpol_import.cfg"
            secedit /export /cfg $seceditExport /quiet
            $content = Get-Content $seceditExport
            $content = $content -replace 'MinimumPasswordLength\s*=\s*\d+', 'MinimumPasswordLength = 14'
            if ($content -notmatch 'MinimumPasswordLength') {
                $content = $content -replace '(\[System Access\])', "`$1`nMinimumPasswordLength = 14"
            }
            $content | Set-Content $seceditImport -Force
            secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
            Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 1.1.4: $_"
            return $false
        }
    }
}

function Set-CIS_1_1_5 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Password must meet complexity requirements' is set to 'Enabled'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("1.1.5", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['1.1.5'] = @{
                Timestamp = Get-Date
                RuleId    = '1.1.5'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
            $seceditImport = "$env:TEMP\secpol_import.cfg"
            secedit /export /cfg $seceditExport /quiet
            $content = Get-Content $seceditExport
            $content = $content -replace 'PasswordComplexity\s*=\s*\d+', 'PasswordComplexity = 1'
            if ($content -notmatch 'PasswordComplexity') {
                $content = $content -replace '(\[System Access\])', "`$1`nPasswordComplexity = 1"
            }
            $content | Set-Content $seceditImport -Force
            secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
            Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 1.1.5: $_"
            return $false
        }
    }
}

function Set-CIS_1_1_6 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Relax minimum password length limits' is set to 'Enabled'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("1.1.6", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['1.1.6'] = @{
                Timestamp = Get-Date
                RuleId    = '1.1.6'
            }
            
            if (-not (Test-Path 'HKLM:\System\CurrentControlSet\Control\SAM')) {
                New-Item -Path 'HKLM:\System\CurrentControlSet\Control\SAM' -Force | Out-Null
            }
            Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\SAM' -Name 'RelaxMinimumPasswordLengthLimits' -Value 1 -Type DWord -Force
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 1.1.6: $_"
            return $false
        }
    }
}

function Set-CIS_1_1_7 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Store passwords using reversible encryption' is set to 'Disabled'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("1.1.7", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['1.1.7'] = @{
                Timestamp = Get-Date
                RuleId    = '1.1.7'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
            $seceditImport = "$env:TEMP\secpol_import.cfg"
            secedit /export /cfg $seceditExport /quiet
            $content = Get-Content $seceditExport
            $content = $content -replace 'ClearTextPassword\s*=\s*\d+', 'ClearTextPassword = 0'
            if ($content -notmatch 'ClearTextPassword') {
                $content = $content -replace '(\[System Access\])', "`$1`nClearTextPassword = 0"
            }
            $content | Set-Content $seceditImport -Force
            secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
            Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 1.1.7: $_"
            return $false
        }
    }
}
#endregion

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
#region Rule Registry
$Script:RuleRegistry = @'
[
    {
        "Id":  "1.1.1",
        "RemediateFunc":  "Set-CIS_1_1_1",
        "AuditFunc":  "Test-CIS_1_1_1",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Account Policies",
        "Title":  "Ensure \u0027Enforce password history\u0027 is set to \u002724 or more password(s)\u0027"
    },
    {
        "Id":  "1.1.2",
        "RemediateFunc":  "Set-CIS_1_1_2",
        "AuditFunc":  "Test-CIS_1_1_2",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Account Policies",
        "Title":  "Ensure \u0027Maximum password age\u0027 is set to \u0027365 or fewer days, but not 0\u0027"
    },
    {
        "Id":  "1.1.3",
        "RemediateFunc":  "Set-CIS_1_1_3",
        "AuditFunc":  "Test-CIS_1_1_3",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Account Policies",
        "Title":  "Ensure \u0027Minimum password age\u0027 is set to \u00271 or more day(s)\u0027"
    },
    {
        "Id":  "1.1.4",
        "RemediateFunc":  "Set-CIS_1_1_4",
        "AuditFunc":  "Test-CIS_1_1_4",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Account Policies",
        "Title":  "Ensure \u0027Minimum password length\u0027 is set to \u002714 or more character(s)\u0027"
    },
    {
        "Id":  "1.1.5",
        "RemediateFunc":  "Set-CIS_1_1_5",
        "AuditFunc":  "Test-CIS_1_1_5",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Account Policies",
        "Title":  "Ensure \u0027Password must meet complexity requirements\u0027 is set to \u0027Enabled\u0027"
    },
    {
        "Id":  "1.1.6",
        "RemediateFunc":  "Set-CIS_1_1_6",
        "AuditFunc":  "Test-CIS_1_1_6",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Account Policies",
        "Title":  "Ensure \u0027Relax minimum password length limits\u0027 is set to \u0027Enabled\u0027"
    },
    {
        "Id":  "1.1.7",
        "RemediateFunc":  "Set-CIS_1_1_7",
        "AuditFunc":  "Test-CIS_1_1_7",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Account Policies",
        "Title":  "Ensure \u0027Store passwords using reversible encryption\u0027 is set to \u0027Disabled\u0027"
    }
]
'@ | ConvertFrom-Json
#endregion

#region Main Execution
function Invoke-CISHardening {
    [CmdletBinding()]
    param(
        [switch]$AuditOnly,
        [switch]$Remediate
        # [switch]$Rollback
    )
    
    Write-Host ""
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host "              CIS WINDOWS HARDENING - EXECUTION                   " -ForegroundColor Cyan
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host ""
    
    $passCount = 0
    $failCount = 0
    $remediatedCount = 0
    $errorCount = 0
    
    foreach ($rule in $Script:RuleRegistry) {
        $result = [PSCustomObject]@{
            RuleId       = $rule.Id
            Title        = $rule.Title
            Level        = $rule.Level
            Category     = $rule.Category
            BeforeStatus = 'Unknown'
            AfterStatus  = 'Unknown'
            Action       = 'None'
            Details      = ''
            Timestamp    = Get-Date
        }
        
        # Phase 1: Audit BEFORE
        try {
            $auditResult = & $rule.AuditFunc
            $result.BeforeStatus = if ($auditResult) { 'Pass' } else { 'Fail' }
        }
        catch {
            $result.BeforeStatus = 'Error'
            $result.Details = $_.Exception.Message
        }
        
        # Phase 2: Remediate if needed and requested
        if ($Remediate -and $result.BeforeStatus -eq 'Fail') {
            try {
                $remediateResult = & $rule.RemediateFunc -Force
                if ($remediateResult) {
                    $result.Action = 'Remediated'
                    $remediatedCount++
                }
                else {
                    $result.Action = 'Failed'
                }
            }
            catch {
                $result.Action = 'Error'
                $result.Details = $_.Exception.Message
                $errorCount++
            }
        }
        
        # Phase 3: Rollback if requested
        # (Rollback deferred)
        
        # Phase 4: Audit AFTER (if remediated)
        if ($result.Action -eq 'Remediated') {
            try {
                $auditResult = & $rule.AuditFunc
                $result.AfterStatus = if ($auditResult) { 'Pass' } else { 'Fail' }
            }
            catch {
                $result.AfterStatus = 'Error'
            }
        }
        else {
            $result.AfterStatus = $result.BeforeStatus
        }
        
        # Update counters
        if ($result.AfterStatus -eq 'Pass') { $passCount++ }
        elseif ($result.AfterStatus -eq 'Fail') { $failCount++ }
        
        # Output status
        $displayStatus = if ($result.Action -eq 'Remediated') { 'Remediated' } else { $result.AfterStatus }
        Write-RuleStatus -RuleId $rule.Id -Title $rule.Title -Status $displayStatus -Details $result.Details
        
        $Script:Results += $result
    }
    
    # Summary
    Write-Host ""
    Write-Host "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•" -ForegroundColor Cyan
    Write-Host "SUMMARY" -ForegroundColor Cyan
    Write-Host "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•" -ForegroundColor Cyan
    Write-Host "  Total Rules:  $($Script:RuleRegistry.Count)"
    Write-Host "  Passed:       " -NoNewline; Write-Host $passCount -ForegroundColor Green
    Write-Host "  Failed:       " -NoNewline; Write-Host $failCount -ForegroundColor Red
    Write-Host "  Remediated:   " -NoNewline; Write-Host $remediatedCount -ForegroundColor Yellow
    Write-Host "  Errors:       " -NoNewline; Write-Host $errorCount -ForegroundColor Magenta
    Write-Host ""
    
    $compliance = [math]::Round(($passCount / $Script:RuleRegistry.Count) * 100, 1)
    $complianceColor = if ($compliance -ge 80) { 'Green' } elseif ($compliance -ge 50) { 'Yellow' } else { 'Red' }
    Write-Host "  Compliance:   $compliance%" -ForegroundColor $complianceColor
    Write-Host ""
    
    return $Script:Results
}

# Auto-execute based on parameters
if ($AuditOnly) {
    Invoke-CISHardening -AuditOnly
    if ($GenerateReport) { Export-CISReport }
}
elseif ($Remediate) {
    Invoke-CISHardening -Remediate
    if ($GenerateReport) { Export-CISReport }
}
# elseif ($Rollback) {
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