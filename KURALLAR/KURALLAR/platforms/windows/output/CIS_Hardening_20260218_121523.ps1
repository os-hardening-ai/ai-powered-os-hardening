#==============================================================================
# CIS Windows Hardening Script
# Generated: 2026-02-18 12:15:24
# Rules: 49 selected
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
    } else {
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
    } catch {
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
    } catch {
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
    } catch {
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
    } catch {
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
    } catch {
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
    } catch {
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
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 1.1.7: $_"
        return $false
    }
}

function Test-CIS_1_2_1 {
    <#
    .SYNOPSIS
        Ensure 'Account lockout duration' is set to '15 or more minute(s)'
    .DESCRIPTION
        This policy setting determines the number of minutes a locked-out account remains locked out before automatically becoming unlocked. The available range is from 0 minutes through 99,999 minutes. If you set the account lockout duration to 0, the account will be locked out until an administrator explicitly unlocks it. If Account lockout threshold is set to a number greater than zero, Account lockout duration must be greater than or equal to the value of Reset account lockout counter after.
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
            if ($content -match 'LockoutDuration\s*=\s*(\d+)') {
                return ([int]$Matches[1] -ge 15)
            }
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 1.2.1: $_"
        return $false
    }
}

function Test-CIS_1_2_2 {
    <#
    .SYNOPSIS
        Ensure 'Account lockout threshold' is set to '5 or fewer invalid logon attempt(s), but not 0'
    .DESCRIPTION
        This account lockout policy setting determines the number of failed sign-in attempts that will cause a user account to be locked. A locked account cannot be used until you reset it or until the number of minutes specified by the Account lockout duration policy setting expires. You can set a value from 1 through 999 failed sign-in attempts, or you can specify that the account will never be locked by setting the value to 0. If Account lockout threshold is set to a number greater than zero, Account lockout duration must be greater than or equal to the value of Reset account lockout counter after.
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
            if ($content -match 'LockoutBadCount\s*=\s*(\d+)') {
                $val = [int]$Matches[1]
                return ($val -le 5 -and $val -gt 0)
            }
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 1.2.2: $_"
        return $false
    }
}

function Test-CIS_1_2_4 {
    <#
    .SYNOPSIS
        Ensure 'Reset account lockout counter after' is set to '15 or more minute(s)'
    .DESCRIPTION
        This policy setting determines the number of minutes that must elapse after a failed logon attempt before the failed logon attempt counter is reset to 0 failed logon attempts. The available range is 1 minute to 99,999 minutes. If Account lockout threshold is set to a number greater than zero, this reset time must be less than or equal to the Account lockout duration.
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
            if ($content -match 'ResetLockoutCount\s*=\s*(\d+)') {
                $val = [int]$Matches[1]
                return ($val -ge 15)
            }
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 1.2.4: $_"
        return $false
    }
}

function Test-CIS_2_2_1 {
    <#
    .SYNOPSIS
        Ensure 'Access Credential Manager as a trusted caller' is set to 'No One'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: No One.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeTrustedCredManAccessPrivilege\s*=\s*(.*)') {
                $val = $Matches[1].Trim()
                return ([string]::IsNullOrWhiteSpace($val))
            }
            return $true
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.1: $_"
        return $false
    }
}

function Test-CIS_2_2_10 {
    <#
    .SYNOPSIS
        Ensure 'Create a pagefile' is set to 'Administrators'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeCreatePagefilePrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.10: $_"
        return $false
    }
}

function Test-CIS_2_2_11 {
    <#
    .SYNOPSIS
        Ensure 'Create a token object' is set to 'No One'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: No One.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeCreateTokenPrivilege\s*=\s*(.*)') {
                $val = $Matches[1].Trim()
                return ([string]::IsNullOrWhiteSpace($val))
            }
            return $true
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.11: $_"
        return $false
    }
}

function Test-CIS_2_2_12 {
    <#
    .SYNOPSIS
        Ensure 'Create global objects' is set to 'Administrators, LOCAL SERVICE, NETWORK SERVICE, SERVICE'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators, LOCAL SERVICE, NETWORK SERVICE, SERVICE.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeCreateGlobalPrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544','*S-1-5-19','*S-1-5-20','*S-1-5-6') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.12: $_"
        return $false
    }
}

function Test-CIS_2_2_13 {
    <#
    .SYNOPSIS
        Ensure 'Create permanent shared objects' is set to 'No One'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: No One.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeCreatePermanentPrivilege\s*=\s*(.*)') {
                $val = $Matches[1].Trim()
                return ([string]::IsNullOrWhiteSpace($val))
            }
            return $true
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.13: $_"
        return $false
    }
}

function Test-CIS_2_2_14 {
    <#
    .SYNOPSIS
        Ensure 'Create symbolic links' is set to 'Administrators'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeCreateSymbolicLinkPrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.14: $_"
        return $false
    }
}

function Test-CIS_2_2_15 {
    <#
    .SYNOPSIS
        Ensure 'Debug programs' is set to 'Administrators'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeDebugPrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.15: $_"
        return $false
    }
}

function Test-CIS_2_2_16 {
    <#
    .SYNOPSIS
        Ensure 'Deny access to this computer from the network' to include 'Guests'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Guests.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeDenyNetworkLogonRight\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() }
                return ($currentSids -contains '*S-1-5-32-546')
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.16: $_"
        return $false
    }
}

function Test-CIS_2_2_17 {
    <#
    .SYNOPSIS
        Ensure 'Deny log on as a batch job' to include 'Guests'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Guests.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeDenyBatchLogonRight\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() }
                return ($currentSids -contains '*S-1-5-32-546')
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.17: $_"
        return $false
    }
}

function Test-CIS_2_2_18 {
    <#
    .SYNOPSIS
        Ensure 'Deny log on as a service' to include 'Guests'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Guests.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeDenyServiceLogonRight\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() }
                return ($currentSids -contains '*S-1-5-32-546')
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.18: $_"
        return $false
    }
}

function Test-CIS_2_2_19 {
    <#
    .SYNOPSIS
        Ensure 'Deny log on locally' to include 'Guests'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Guests.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeDenyInteractiveLogonRight\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() }
                return ($currentSids -contains '*S-1-5-32-546')
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.19: $_"
        return $false
    }
}

function Test-CIS_2_2_2 {
    <#
    .SYNOPSIS
        Ensure 'Access this computer from the network' is set to 'Administrators, Remote Desktop Users'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators, Remote Desktop Users.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeNetworkLogonRight\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544','*S-1-5-32-555') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.2: $_"
        return $false
    }
}

function Test-CIS_2_2_20 {
    <#
    .SYNOPSIS
        Ensure 'Deny log on through Remote Desktop Services' to include 'Guests'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Guests.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeDenyRemoteInteractiveLogonRight\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() }
                return ($currentSids -contains '*S-1-5-32-546')
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.20: $_"
        return $false
    }
}

function Test-CIS_2_2_21 {
    <#
    .SYNOPSIS
        Ensure 'Enable computer and user accounts to be trusted for delegation' is set to 'No One'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: No One.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeEnableDelegationPrivilege\s*=\s*(.*)') {
                $val = $Matches[1].Trim()
                return ([string]::IsNullOrWhiteSpace($val))
            }
            return $true
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.21: $_"
        return $false
    }
}

function Test-CIS_2_2_22 {
    <#
    .SYNOPSIS
        Ensure 'Force shutdown from a remote system' is set to 'Administrators'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeRemoteShutdownPrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.22: $_"
        return $false
    }
}

function Test-CIS_2_2_23 {
    <#
    .SYNOPSIS
        Ensure 'Generate security audits' is set to 'LOCAL SERVICE, NETWORK SERVICE'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: LOCAL SERVICE, NETWORK SERVICE.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeAuditPrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-19','*S-1-5-20') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.23: $_"
        return $false
    }
}

function Test-CIS_2_2_24 {
    <#
    .SYNOPSIS
        Ensure 'Impersonate a client after authentication' is set to 'Administrators, LOCAL SERVICE, NETWORK SERVICE, SERVICE'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators, LOCAL SERVICE, NETWORK SERVICE, SERVICE.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeImpersonatePrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544','*S-1-5-19','*S-1-5-20','*S-1-5-6') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.24: $_"
        return $false
    }
}

function Test-CIS_2_2_25 {
    <#
    .SYNOPSIS
        Ensure 'Increase scheduling priority' is set to 'Administrators, Window Manager\Window Manager Group'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators, Window Manager\Window Manager Group.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeIncreaseBasePriorityPrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544','*S-1-5-90-0') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.25: $_"
        return $false
    }
}

function Test-CIS_2_2_26 {
    <#
    .SYNOPSIS
        Ensure 'Load and unload device drivers' is set to 'Administrators'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeLoadDriverPrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.26: $_"
        return $false
    }
}

function Test-CIS_2_2_27 {
    <#
    .SYNOPSIS
        Ensure 'Lock pages in memory' is set to 'No One'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: No One.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeLockMemoryPrivilege\s*=\s*(.*)') {
                $val = $Matches[1].Trim()
                return ([string]::IsNullOrWhiteSpace($val))
            }
            return $true
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.27: $_"
        return $false
    }
}

function Test-CIS_2_2_28 {
    <#
    .SYNOPSIS
        Ensure 'Log on as a batch job' is set to 'Administrators'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators.
    .NOTES
        CIS Level: 2
        Category: Local Policies
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
            if ($content -match 'SeBatchLogonRight\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.28: $_"
        return $false
    }
}

function Test-CIS_2_2_29 {
    <#
    .SYNOPSIS
        Ensure 'Log on as a service' is configured
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: (configured - verify manually).
    .NOTES
        CIS Level: 2
        Category: Local Policies
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
            if ($content -match 'SeServiceLogonRight\s*=\s*(.*)') {
                $val = $Matches[1].Trim()
                return (-not [string]::IsNullOrWhiteSpace($val))
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.29: $_"
        return $false
    }
}

function Test-CIS_2_2_3 {
    <#
    .SYNOPSIS
        Ensure 'Act as part of the operating system' is set to 'No One'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: No One.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeTcbPrivilege\s*=\s*(.*)') {
                $val = $Matches[1].Trim()
                return ([string]::IsNullOrWhiteSpace($val))
            }
            return $true
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.3: $_"
        return $false
    }
}

function Test-CIS_2_2_30 {
    <#
    .SYNOPSIS
        Ensure 'Manage auditing and security log' is set to 'Administrators'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeSecurityPrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.30: $_"
        return $false
    }
}

function Test-CIS_2_2_31 {
    <#
    .SYNOPSIS
        Ensure 'Modify an object label' is set to 'No One'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: No One.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeRelabelPrivilege\s*=\s*(.*)') {
                $val = $Matches[1].Trim()
                return ([string]::IsNullOrWhiteSpace($val))
            }
            return $true
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.31: $_"
        return $false
    }
}

function Test-CIS_2_2_32 {
    <#
    .SYNOPSIS
        Ensure 'Modify firmware environment values' is set to 'Administrators'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeSystemEnvironmentPrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.32: $_"
        return $false
    }
}

function Test-CIS_2_2_33 {
    <#
    .SYNOPSIS
        Ensure 'Perform volume maintenance tasks' is set to 'Administrators'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeManageVolumePrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.33: $_"
        return $false
    }
}

function Test-CIS_2_2_34 {
    <#
    .SYNOPSIS
        Ensure 'Profile single process' is set to 'Administrators'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeProfileSingleProcessPrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.34: $_"
        return $false
    }
}

function Test-CIS_2_2_35 {
    <#
    .SYNOPSIS
        Ensure 'Profile system performance' is set to 'Administrators, NT SERVICE\WdiServiceHost'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators, NT SERVICE\WdiServiceHost.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeSystemProfilePrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544','*S-1-5-80-3139157870-2983391045-3678747466-658725712-1809340420') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.35: $_"
        return $false
    }
}

function Test-CIS_2_2_36 {
    <#
    .SYNOPSIS
        Ensure 'Replace a process level token' is set to 'LOCAL SERVICE, NETWORK SERVICE'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: LOCAL SERVICE, NETWORK SERVICE.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeAssignPrimaryTokenPrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-19','*S-1-5-20') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.36: $_"
        return $false
    }
}

function Test-CIS_2_2_37 {
    <#
    .SYNOPSIS
        Ensure 'Restore files and directories' is set to 'Administrators'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeRestorePrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.37: $_"
        return $false
    }
}

function Test-CIS_2_2_38 {
    <#
    .SYNOPSIS
        Ensure 'Shut down the system' is set to 'Administrators, Users'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators, Users.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeShutdownPrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544','*S-1-5-32-545') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.38: $_"
        return $false
    }
}

function Test-CIS_2_2_39 {
    <#
    .SYNOPSIS
        Ensure 'Take ownership of files or other objects' is set to 'Administrators'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeTakeOwnershipPrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.39: $_"
        return $false
    }
}

function Test-CIS_2_2_4 {
    <#
    .SYNOPSIS
        Ensure 'Adjust memory quotas for a process' is set to 'Administrators, LOCAL SERVICE, NETWORK SERVICE'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators, LOCAL SERVICE, NETWORK SERVICE.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeIncreaseQuotaPrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544','*S-1-5-19','*S-1-5-20') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.4: $_"
        return $false
    }
}

function Test-CIS_2_2_5 {
    <#
    .SYNOPSIS
        Ensure 'Allow log on locally' is set to 'Administrators, Users'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators, Users.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeInteractiveLogonRight\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544','*S-1-5-32-545') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.5: $_"
        return $false
    }
}

function Test-CIS_2_2_6 {
    <#
    .SYNOPSIS
        Ensure 'Allow log on through Remote Desktop Services' is set to 'Administrators, Remote Desktop Users'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators, Remote Desktop Users.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeRemoteInteractiveLogonRight\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544','*S-1-5-32-555') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.6: $_"
        return $false
    }
}

function Test-CIS_2_2_7 {
    <#
    .SYNOPSIS
        Ensure 'Back up files and directories' is set to 'Administrators'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeBackupPrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.7: $_"
        return $false
    }
}

function Test-CIS_2_2_8 {
    <#
    .SYNOPSIS
        Ensure 'Change the system time' is set to 'Administrators, LOCAL SERVICE'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators, LOCAL SERVICE.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeSystemtimePrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544','*S-1-5-19') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.8: $_"
        return $false
    }
}

function Test-CIS_2_2_9 {
    <#
    .SYNOPSIS
        Ensure 'Change the time zone' is set to 'Administrators, LOCAL SERVICE, Users'
    .DESCRIPTION
        This policy setting determines which users or groups have the right described by this rule. The recommended state for this setting is: Administrators, LOCAL SERVICE, Users.
    .NOTES
        CIS Level: 1
        Category: Local Policies
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
            if ($content -match 'SeTimeZonePrivilege\s*=\s*(.*)') {
                $currentSids = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Sort-Object
                $expectedSids = @('*S-1-5-32-544','*S-1-5-19','*S-1-5-32-545') | Sort-Object
                $diff = Compare-Object $currentSids $expectedSids
                return ($null -eq $diff)
            }
            return $false
        }
        return $false
    } catch {
        return $false
    }
    }
    catch {
        Write-Verbose "Audit failed for 2.2.9: $_"
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

function Set-CIS_1_2_1 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Account lockout duration' is set to '15 or more minute(s)'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("1.2.1", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['1.2.1'] = @{
                Timestamp = Get-Date
                RuleId    = '1.2.1'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $content = $content -replace 'LockoutDuration\s*=\s*\d+', 'LockoutDuration = 15'
    if ($content -notmatch 'LockoutDuration') {
        $content = $content -replace '(\[System Access\])', "`$1`nLockoutDuration = 15"
    }
    $content | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 1.2.1: $_"
            return $false
        }
    }
}

function Set-CIS_1_2_2 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Account lockout threshold' is set to '5 or fewer invalid logon attempt(s), but not 0'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("1.2.2", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['1.2.2'] = @{
                Timestamp = Get-Date
                RuleId    = '1.2.2'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $content = $content -replace 'LockoutBadCount\s*=\s*\d+', 'LockoutBadCount = 5'
    if ($content -notmatch 'LockoutBadCount') {
        $content = $content -replace '(\[System Access\])', "`$1`nLockoutBadCount = 5"
    }
    $content | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 1.2.2: $_"
            return $false
        }
    }
}

function Set-CIS_1_2_4 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Reset account lockout counter after' is set to '15 or more minute(s)'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("1.2.4", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['1.2.4'] = @{
                Timestamp = Get-Date
                RuleId    = '1.2.4'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $content = $content -replace 'ResetLockoutCount\s*=\s*\d+', 'ResetLockoutCount = 15'
    if ($content -notmatch 'ResetLockoutCount') {
        $content = $content -replace '(\[System Access\])', "`$1`nResetLockoutCount = 15"
    }
    $content | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 1.2.4: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_1 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Access Credential Manager as a trusted caller' is set to 'No One'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.1", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.1'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.1'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeTrustedCredManAccessPrivilege\s*=') {
            $newContent += 'SeTrustedCredManAccessPrivilege = '
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeTrustedCredManAccessPrivilege = ' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.1: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_10 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Create a pagefile' is set to 'Administrators'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.10", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.10'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.10'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeCreatePagefilePrivilege\s*=') {
            $newContent += 'SeCreatePagefilePrivilege = *S-1-5-32-544'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeCreatePagefilePrivilege = *S-1-5-32-544' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.10: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_11 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Create a token object' is set to 'No One'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.11", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.11'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.11'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeCreateTokenPrivilege\s*=') {
            $newContent += 'SeCreateTokenPrivilege = '
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeCreateTokenPrivilege = ' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.11: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_12 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Create global objects' is set to 'Administrators, LOCAL SERVICE, NETWORK SERVICE, SERVICE'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.12", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.12'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.12'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeCreateGlobalPrivilege\s*=') {
            $newContent += 'SeCreateGlobalPrivilege = *S-1-5-32-544,*S-1-5-19,*S-1-5-20,*S-1-5-6'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeCreateGlobalPrivilege = *S-1-5-32-544,*S-1-5-19,*S-1-5-20,*S-1-5-6' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.12: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_13 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Create permanent shared objects' is set to 'No One'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.13", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.13'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.13'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeCreatePermanentPrivilege\s*=') {
            $newContent += 'SeCreatePermanentPrivilege = '
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeCreatePermanentPrivilege = ' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.13: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_14 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Create symbolic links' is set to 'Administrators'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.14", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.14'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.14'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeCreateSymbolicLinkPrivilege\s*=') {
            $newContent += 'SeCreateSymbolicLinkPrivilege = *S-1-5-32-544'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeCreateSymbolicLinkPrivilege = *S-1-5-32-544' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.14: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_15 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Debug programs' is set to 'Administrators'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.15", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.15'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.15'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeDebugPrivilege\s*=') {
            $newContent += 'SeDebugPrivilege = *S-1-5-32-544'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeDebugPrivilege = *S-1-5-32-544' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.15: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_16 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Deny access to this computer from the network' to include 'Guests'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.16", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.16'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.16'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeDenyNetworkLogonRight\s*=') {
            $newContent += 'SeDenyNetworkLogonRight = *S-1-5-32-546'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeDenyNetworkLogonRight = *S-1-5-32-546' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.16: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_17 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Deny log on as a batch job' to include 'Guests'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.17", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.17'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.17'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeDenyBatchLogonRight\s*=') {
            $newContent += 'SeDenyBatchLogonRight = *S-1-5-32-546'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeDenyBatchLogonRight = *S-1-5-32-546' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.17: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_18 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Deny log on as a service' to include 'Guests'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.18", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.18'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.18'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeDenyServiceLogonRight\s*=') {
            $newContent += 'SeDenyServiceLogonRight = *S-1-5-32-546'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeDenyServiceLogonRight = *S-1-5-32-546' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.18: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_19 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Deny log on locally' to include 'Guests'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.19", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.19'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.19'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeDenyInteractiveLogonRight\s*=') {
            $newContent += 'SeDenyInteractiveLogonRight = *S-1-5-32-546'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeDenyInteractiveLogonRight = *S-1-5-32-546' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.19: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_2 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Access this computer from the network' is set to 'Administrators, Remote Desktop Users'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.2", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.2'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.2'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeNetworkLogonRight\s*=') {
            $newContent += 'SeNetworkLogonRight = *S-1-5-32-544,*S-1-5-32-555'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeNetworkLogonRight = *S-1-5-32-544,*S-1-5-32-555' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.2: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_20 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Deny log on through Remote Desktop Services' to include 'Guests'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.20", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.20'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.20'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeDenyRemoteInteractiveLogonRight\s*=') {
            $newContent += 'SeDenyRemoteInteractiveLogonRight = *S-1-5-32-546'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeDenyRemoteInteractiveLogonRight = *S-1-5-32-546' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.20: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_21 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Enable computer and user accounts to be trusted for delegation' is set to 'No One'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.21", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.21'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.21'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeEnableDelegationPrivilege\s*=') {
            $newContent += 'SeEnableDelegationPrivilege = '
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeEnableDelegationPrivilege = ' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.21: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_22 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Force shutdown from a remote system' is set to 'Administrators'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.22", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.22'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.22'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeRemoteShutdownPrivilege\s*=') {
            $newContent += 'SeRemoteShutdownPrivilege = *S-1-5-32-544'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeRemoteShutdownPrivilege = *S-1-5-32-544' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.22: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_23 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Generate security audits' is set to 'LOCAL SERVICE, NETWORK SERVICE'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.23", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.23'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.23'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeAuditPrivilege\s*=') {
            $newContent += 'SeAuditPrivilege = *S-1-5-19,*S-1-5-20'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeAuditPrivilege = *S-1-5-19,*S-1-5-20' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.23: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_24 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Impersonate a client after authentication' is set to 'Administrators, LOCAL SERVICE, NETWORK SERVICE, SERVICE'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.24", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.24'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.24'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeImpersonatePrivilege\s*=') {
            $newContent += 'SeImpersonatePrivilege = *S-1-5-32-544,*S-1-5-19,*S-1-5-20,*S-1-5-6'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeImpersonatePrivilege = *S-1-5-32-544,*S-1-5-19,*S-1-5-20,*S-1-5-6' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.24: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_25 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Increase scheduling priority' is set to 'Administrators, Window Manager\Window Manager Group'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.25", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.25'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.25'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeIncreaseBasePriorityPrivilege\s*=') {
            $newContent += 'SeIncreaseBasePriorityPrivilege = *S-1-5-32-544,*S-1-5-90-0'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeIncreaseBasePriorityPrivilege = *S-1-5-32-544,*S-1-5-90-0' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.25: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_26 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Load and unload device drivers' is set to 'Administrators'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.26", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.26'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.26'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeLoadDriverPrivilege\s*=') {
            $newContent += 'SeLoadDriverPrivilege = *S-1-5-32-544'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeLoadDriverPrivilege = *S-1-5-32-544' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.26: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_27 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Lock pages in memory' is set to 'No One'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.27", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.27'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.27'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeLockMemoryPrivilege\s*=') {
            $newContent += 'SeLockMemoryPrivilege = '
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeLockMemoryPrivilege = ' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.27: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_28 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Log on as a batch job' is set to 'Administrators'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.28", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.28'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.28'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeBatchLogonRight\s*=') {
            $newContent += 'SeBatchLogonRight = *S-1-5-32-544'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeBatchLogonRight = *S-1-5-32-544' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.28: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_3 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Act as part of the operating system' is set to 'No One'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.3", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.3'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.3'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeTcbPrivilege\s*=') {
            $newContent += 'SeTcbPrivilege = '
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeTcbPrivilege = ' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.3: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_30 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Manage auditing and security log' is set to 'Administrators'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.30", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.30'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.30'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeSecurityPrivilege\s*=') {
            $newContent += 'SeSecurityPrivilege = *S-1-5-32-544'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeSecurityPrivilege = *S-1-5-32-544' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.30: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_31 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Modify an object label' is set to 'No One'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.31", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.31'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.31'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeRelabelPrivilege\s*=') {
            $newContent += 'SeRelabelPrivilege = '
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeRelabelPrivilege = ' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.31: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_32 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Modify firmware environment values' is set to 'Administrators'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.32", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.32'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.32'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeSystemEnvironmentPrivilege\s*=') {
            $newContent += 'SeSystemEnvironmentPrivilege = *S-1-5-32-544'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeSystemEnvironmentPrivilege = *S-1-5-32-544' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.32: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_33 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Perform volume maintenance tasks' is set to 'Administrators'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.33", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.33'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.33'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeManageVolumePrivilege\s*=') {
            $newContent += 'SeManageVolumePrivilege = *S-1-5-32-544'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeManageVolumePrivilege = *S-1-5-32-544' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.33: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_34 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Profile single process' is set to 'Administrators'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.34", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.34'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.34'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeProfileSingleProcessPrivilege\s*=') {
            $newContent += 'SeProfileSingleProcessPrivilege = *S-1-5-32-544'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeProfileSingleProcessPrivilege = *S-1-5-32-544' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.34: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_35 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Profile system performance' is set to 'Administrators, NT SERVICE\WdiServiceHost'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.35", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.35'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.35'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeSystemProfilePrivilege\s*=') {
            $newContent += 'SeSystemProfilePrivilege = *S-1-5-32-544,*S-1-5-80-3139157870-2983391045-3678747466-658725712-1809340420'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeSystemProfilePrivilege = *S-1-5-32-544,*S-1-5-80-3139157870-2983391045-3678747466-658725712-1809340420' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.35: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_36 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Replace a process level token' is set to 'LOCAL SERVICE, NETWORK SERVICE'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.36", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.36'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.36'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeAssignPrimaryTokenPrivilege\s*=') {
            $newContent += 'SeAssignPrimaryTokenPrivilege = *S-1-5-19,*S-1-5-20'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeAssignPrimaryTokenPrivilege = *S-1-5-19,*S-1-5-20' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.36: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_37 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Restore files and directories' is set to 'Administrators'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.37", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.37'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.37'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeRestorePrivilege\s*=') {
            $newContent += 'SeRestorePrivilege = *S-1-5-32-544'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeRestorePrivilege = *S-1-5-32-544' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.37: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_38 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Shut down the system' is set to 'Administrators, Users'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.38", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.38'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.38'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeShutdownPrivilege\s*=') {
            $newContent += 'SeShutdownPrivilege = *S-1-5-32-544,*S-1-5-32-545'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeShutdownPrivilege = *S-1-5-32-544,*S-1-5-32-545' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.38: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_39 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Take ownership of files or other objects' is set to 'Administrators'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.39", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.39'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.39'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeTakeOwnershipPrivilege\s*=') {
            $newContent += 'SeTakeOwnershipPrivilege = *S-1-5-32-544'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeTakeOwnershipPrivilege = *S-1-5-32-544' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.39: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_4 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Adjust memory quotas for a process' is set to 'Administrators, LOCAL SERVICE, NETWORK SERVICE'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.4", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.4'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.4'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeIncreaseQuotaPrivilege\s*=') {
            $newContent += 'SeIncreaseQuotaPrivilege = *S-1-5-32-544,*S-1-5-19,*S-1-5-20'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeIncreaseQuotaPrivilege = *S-1-5-32-544,*S-1-5-19,*S-1-5-20' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.4: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_5 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Allow log on locally' is set to 'Administrators, Users'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.5", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.5'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.5'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeInteractiveLogonRight\s*=') {
            $newContent += 'SeInteractiveLogonRight = *S-1-5-32-544,*S-1-5-32-545'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeInteractiveLogonRight = *S-1-5-32-544,*S-1-5-32-545' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.5: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_6 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Allow log on through Remote Desktop Services' is set to 'Administrators, Remote Desktop Users'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.6", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.6'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.6'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeRemoteInteractiveLogonRight\s*=') {
            $newContent += 'SeRemoteInteractiveLogonRight = *S-1-5-32-544,*S-1-5-32-555'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeRemoteInteractiveLogonRight = *S-1-5-32-544,*S-1-5-32-555' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.6: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_7 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Back up files and directories' is set to 'Administrators'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.7", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.7'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.7'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeBackupPrivilege\s*=') {
            $newContent += 'SeBackupPrivilege = *S-1-5-32-544'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeBackupPrivilege = *S-1-5-32-544' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.7: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_8 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Change the system time' is set to 'Administrators, LOCAL SERVICE'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.8", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.8'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.8'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeSystemtimePrivilege\s*=') {
            $newContent += 'SeSystemtimePrivilege = *S-1-5-32-544,*S-1-5-19'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeSystemtimePrivilege = *S-1-5-32-544,*S-1-5-19' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.8: $_"
            return $false
        }
    }
}

function Set-CIS_2_2_9 {
    <#
    .SYNOPSIS
        Remediate: Ensure 'Change the time zone' is set to 'Administrators, LOCAL SERVICE, Users'
    .NOTES
        Requires Admin: True
        Requires Reboot: False
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param([switch]$Force)
    
    if ($PSCmdlet.ShouldProcess("2.2.9", "Apply CIS hardening")) {
        try {
            # Backup current value
            $Script:BackupData['2.2.9'] = @{
                Timestamp = Get-Date
                RuleId    = '2.2.9'
            }
            
            $seceditExport = "$env:TEMP\secpol_export.cfg"
    $seceditImport = "$env:TEMP\secpol_import.cfg"
    secedit /export /cfg $seceditExport /quiet
    $content = Get-Content $seceditExport
    $replaced = $false
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match '^SeTimeZonePrivilege\s*=') {
            $newContent += 'SeTimeZonePrivilege = *S-1-5-32-544,*S-1-5-19,*S-1-5-32-545'
            $replaced = $true
        } else {
            $newContent += $line
        }
    }
    if (-not $replaced) {
        $idx = -1
        for ($i = 0; $i -lt $newContent.Count; $i++) {
            if ($newContent[$i] -match '^\[Privilege Rights\]') { $idx = $i; break }
        }
        if ($idx -ge 0) {
            $before = $newContent[0..$idx]
            $after = if ($idx + 1 -lt $newContent.Count) { $newContent[($idx+1)..($newContent.Count-1)] } else { @() }
            $newContent = $before + 'SeTimeZonePrivilege = *S-1-5-32-544,*S-1-5-19,*S-1-5-32-545' + $after
        }
    }
    $newContent | Set-Content $seceditImport -Force
    secedit /configure /db secedit.sdb /cfg $seceditImport /quiet
    Remove-Item $seceditExport, $seceditImport -Force -ErrorAction SilentlyContinue
            
            return $true
        }
        catch {
            Write-Error "Remediation failed for 2.2.9: $_"
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
    },
    {
        "Id":  "1.2.1",
        "RemediateFunc":  "Set-CIS_1_2_1",
        "AuditFunc":  "Test-CIS_1_2_1",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Account Policies",
        "Title":  "Ensure \u0027Account lockout duration\u0027 is set to \u002715 or more minute(s)\u0027"
    },
    {
        "Id":  "1.2.2",
        "RemediateFunc":  "Set-CIS_1_2_2",
        "AuditFunc":  "Test-CIS_1_2_2",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Account Policies",
        "Title":  "Ensure \u0027Account lockout threshold\u0027 is set to \u00275 or fewer invalid logon attempt(s), but not 0\u0027"
    },
    {
        "Id":  "1.2.4",
        "RemediateFunc":  "Set-CIS_1_2_4",
        "AuditFunc":  "Test-CIS_1_2_4",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Account Policies",
        "Title":  "Ensure \u0027Reset account lockout counter after\u0027 is set to \u002715 or more minute(s)\u0027"
    },
    {
        "Id":  "2.2.1",
        "RemediateFunc":  "Set-CIS_2_2_1",
        "AuditFunc":  "Test-CIS_2_2_1",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Access Credential Manager as a trusted caller\u0027 is set to \u0027No One\u0027"
    },
    {
        "Id":  "2.2.10",
        "RemediateFunc":  "Set-CIS_2_2_10",
        "AuditFunc":  "Test-CIS_2_2_10",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Create a pagefile\u0027 is set to \u0027Administrators\u0027"
    },
    {
        "Id":  "2.2.11",
        "RemediateFunc":  "Set-CIS_2_2_11",
        "AuditFunc":  "Test-CIS_2_2_11",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Create a token object\u0027 is set to \u0027No One\u0027"
    },
    {
        "Id":  "2.2.12",
        "RemediateFunc":  "Set-CIS_2_2_12",
        "AuditFunc":  "Test-CIS_2_2_12",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Create global objects\u0027 is set to \u0027Administrators, LOCAL SERVICE, NETWORK SERVICE, SERVICE\u0027"
    },
    {
        "Id":  "2.2.13",
        "RemediateFunc":  "Set-CIS_2_2_13",
        "AuditFunc":  "Test-CIS_2_2_13",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Create permanent shared objects\u0027 is set to \u0027No One\u0027"
    },
    {
        "Id":  "2.2.14",
        "RemediateFunc":  "Set-CIS_2_2_14",
        "AuditFunc":  "Test-CIS_2_2_14",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Create symbolic links\u0027 is set to \u0027Administrators\u0027"
    },
    {
        "Id":  "2.2.15",
        "RemediateFunc":  "Set-CIS_2_2_15",
        "AuditFunc":  "Test-CIS_2_2_15",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Debug programs\u0027 is set to \u0027Administrators\u0027"
    },
    {
        "Id":  "2.2.16",
        "RemediateFunc":  "Set-CIS_2_2_16",
        "AuditFunc":  "Test-CIS_2_2_16",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Deny access to this computer from the network\u0027 to include \u0027Guests\u0027"
    },
    {
        "Id":  "2.2.17",
        "RemediateFunc":  "Set-CIS_2_2_17",
        "AuditFunc":  "Test-CIS_2_2_17",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Deny log on as a batch job\u0027 to include \u0027Guests\u0027"
    },
    {
        "Id":  "2.2.18",
        "RemediateFunc":  "Set-CIS_2_2_18",
        "AuditFunc":  "Test-CIS_2_2_18",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Deny log on as a service\u0027 to include \u0027Guests\u0027"
    },
    {
        "Id":  "2.2.19",
        "RemediateFunc":  "Set-CIS_2_2_19",
        "AuditFunc":  "Test-CIS_2_2_19",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Deny log on locally\u0027 to include \u0027Guests\u0027"
    },
    {
        "Id":  "2.2.2",
        "RemediateFunc":  "Set-CIS_2_2_2",
        "AuditFunc":  "Test-CIS_2_2_2",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Access this computer from the network\u0027 is set to \u0027Administrators, Remote Desktop Users\u0027"
    },
    {
        "Id":  "2.2.20",
        "RemediateFunc":  "Set-CIS_2_2_20",
        "AuditFunc":  "Test-CIS_2_2_20",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Deny log on through Remote Desktop Services\u0027 to include \u0027Guests\u0027"
    },
    {
        "Id":  "2.2.21",
        "RemediateFunc":  "Set-CIS_2_2_21",
        "AuditFunc":  "Test-CIS_2_2_21",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Enable computer and user accounts to be trusted for delegation\u0027 is set to \u0027No One\u0027"
    },
    {
        "Id":  "2.2.22",
        "RemediateFunc":  "Set-CIS_2_2_22",
        "AuditFunc":  "Test-CIS_2_2_22",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Force shutdown from a remote system\u0027 is set to \u0027Administrators\u0027"
    },
    {
        "Id":  "2.2.23",
        "RemediateFunc":  "Set-CIS_2_2_23",
        "AuditFunc":  "Test-CIS_2_2_23",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Generate security audits\u0027 is set to \u0027LOCAL SERVICE, NETWORK SERVICE\u0027"
    },
    {
        "Id":  "2.2.24",
        "RemediateFunc":  "Set-CIS_2_2_24",
        "AuditFunc":  "Test-CIS_2_2_24",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Impersonate a client after authentication\u0027 is set to \u0027Administrators, LOCAL SERVICE, NETWORK SERVICE, SERVICE\u0027"
    },
    {
        "Id":  "2.2.25",
        "RemediateFunc":  "Set-CIS_2_2_25",
        "AuditFunc":  "Test-CIS_2_2_25",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Increase scheduling priority\u0027 is set to \u0027Administrators, Window Manager\\Window Manager Group\u0027"
    },
    {
        "Id":  "2.2.26",
        "RemediateFunc":  "Set-CIS_2_2_26",
        "AuditFunc":  "Test-CIS_2_2_26",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Load and unload device drivers\u0027 is set to \u0027Administrators\u0027"
    },
    {
        "Id":  "2.2.27",
        "RemediateFunc":  "Set-CIS_2_2_27",
        "AuditFunc":  "Test-CIS_2_2_27",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Lock pages in memory\u0027 is set to \u0027No One\u0027"
    },
    {
        "Id":  "2.2.28",
        "RemediateFunc":  "Set-CIS_2_2_28",
        "AuditFunc":  "Test-CIS_2_2_28",
        "RequiresReboot":  false,
        "Level":  2,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Log on as a batch job\u0027 is set to \u0027Administrators\u0027"
    },
    {
        "Id":  "2.2.29",
        "RemediateFunc":  "Set-CIS_2_2_29",
        "AuditFunc":  "Test-CIS_2_2_29",
        "RequiresReboot":  false,
        "Level":  2,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Log on as a service\u0027 is configured"
    },
    {
        "Id":  "2.2.3",
        "RemediateFunc":  "Set-CIS_2_2_3",
        "AuditFunc":  "Test-CIS_2_2_3",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Act as part of the operating system\u0027 is set to \u0027No One\u0027"
    },
    {
        "Id":  "2.2.30",
        "RemediateFunc":  "Set-CIS_2_2_30",
        "AuditFunc":  "Test-CIS_2_2_30",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Manage auditing and security log\u0027 is set to \u0027Administrators\u0027"
    },
    {
        "Id":  "2.2.31",
        "RemediateFunc":  "Set-CIS_2_2_31",
        "AuditFunc":  "Test-CIS_2_2_31",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Modify an object label\u0027 is set to \u0027No One\u0027"
    },
    {
        "Id":  "2.2.32",
        "RemediateFunc":  "Set-CIS_2_2_32",
        "AuditFunc":  "Test-CIS_2_2_32",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Modify firmware environment values\u0027 is set to \u0027Administrators\u0027"
    },
    {
        "Id":  "2.2.33",
        "RemediateFunc":  "Set-CIS_2_2_33",
        "AuditFunc":  "Test-CIS_2_2_33",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Perform volume maintenance tasks\u0027 is set to \u0027Administrators\u0027"
    },
    {
        "Id":  "2.2.34",
        "RemediateFunc":  "Set-CIS_2_2_34",
        "AuditFunc":  "Test-CIS_2_2_34",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Profile single process\u0027 is set to \u0027Administrators\u0027"
    },
    {
        "Id":  "2.2.35",
        "RemediateFunc":  "Set-CIS_2_2_35",
        "AuditFunc":  "Test-CIS_2_2_35",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Profile system performance\u0027 is set to \u0027Administrators, NT SERVICE\\WdiServiceHost\u0027"
    },
    {
        "Id":  "2.2.36",
        "RemediateFunc":  "Set-CIS_2_2_36",
        "AuditFunc":  "Test-CIS_2_2_36",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Replace a process level token\u0027 is set to \u0027LOCAL SERVICE, NETWORK SERVICE\u0027"
    },
    {
        "Id":  "2.2.37",
        "RemediateFunc":  "Set-CIS_2_2_37",
        "AuditFunc":  "Test-CIS_2_2_37",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Restore files and directories\u0027 is set to \u0027Administrators\u0027"
    },
    {
        "Id":  "2.2.38",
        "RemediateFunc":  "Set-CIS_2_2_38",
        "AuditFunc":  "Test-CIS_2_2_38",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Shut down the system\u0027 is set to \u0027Administrators, Users\u0027"
    },
    {
        "Id":  "2.2.39",
        "RemediateFunc":  "Set-CIS_2_2_39",
        "AuditFunc":  "Test-CIS_2_2_39",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Take ownership of files or other objects\u0027 is set to \u0027Administrators\u0027"
    },
    {
        "Id":  "2.2.4",
        "RemediateFunc":  "Set-CIS_2_2_4",
        "AuditFunc":  "Test-CIS_2_2_4",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Adjust memory quotas for a process\u0027 is set to \u0027Administrators, LOCAL SERVICE, NETWORK SERVICE\u0027"
    },
    {
        "Id":  "2.2.5",
        "RemediateFunc":  "Set-CIS_2_2_5",
        "AuditFunc":  "Test-CIS_2_2_5",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Allow log on locally\u0027 is set to \u0027Administrators, Users\u0027"
    },
    {
        "Id":  "2.2.6",
        "RemediateFunc":  "Set-CIS_2_2_6",
        "AuditFunc":  "Test-CIS_2_2_6",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Allow log on through Remote Desktop Services\u0027 is set to \u0027Administrators, Remote Desktop Users\u0027"
    },
    {
        "Id":  "2.2.7",
        "RemediateFunc":  "Set-CIS_2_2_7",
        "AuditFunc":  "Test-CIS_2_2_7",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Back up files and directories\u0027 is set to \u0027Administrators\u0027"
    },
    {
        "Id":  "2.2.8",
        "RemediateFunc":  "Set-CIS_2_2_8",
        "AuditFunc":  "Test-CIS_2_2_8",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Change the system time\u0027 is set to \u0027Administrators, LOCAL SERVICE\u0027"
    },
    {
        "Id":  "2.2.9",
        "RemediateFunc":  "Set-CIS_2_2_9",
        "AuditFunc":  "Test-CIS_2_2_9",
        "RequiresReboot":  false,
        "Level":  1,
        "Category":  "Local Policies",
        "Title":  "Ensure \u0027Change the time zone\u0027 is set to \u0027Administrators, LOCAL SERVICE, Users\u0027"
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