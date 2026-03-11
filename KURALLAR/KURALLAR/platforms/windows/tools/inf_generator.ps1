#Requires -Version 5.1
<#
.SYNOPSIS
    Security Template (INF) Generator for CIS Windows Hardening
.DESCRIPTION
    Generates a standalone security template (.inf) file that can be applied
    using secedit.exe or imported into Group Policy.
#>

function New-SecurityTemplate {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [array]$Rules,
        
        [Parameter(Mandatory)]
        [string]$OutputPath,
        
        [Parameter()]
        [string]$TemplateName = "CIS Windows Hardening",
        
        [Parameter()]
        [string]$Description = "Security template generated from CIS Benchmark rules"
    )
    
    # Initialize sections
    $sections = @{
        "[System Access]"           = @()
        "[Event Audit]"             = @()
        "[Registry Values]"         = @()
        "[Privilege Rights]"        = @()
        "[Service General Setting]" = @()
    }
    
    # Process rules
    foreach ($ruleItem in $Rules) {
        $rule = $ruleItem.Rule
        
        # Check for INF configuration
        if ($rule.implementation_gpo -and $rule.implementation_gpo.inf_section) {
            $section = $rule.implementation_gpo.inf_section
            
            # Ensure section exists
            if (-not $sections.ContainsKey($section)) {
                $sections[$section] = @()
            }
            
            $sections[$section] += @{
                RuleId  = $rule.rule_id
                Title   = $rule.title
                Key     = $rule.implementation_gpo.inf_key
                Value   = $rule.implementation_gpo.inf_value
                Comment = "CIS $($rule.rule_id) - $($rule.title)"
            }
        }
        
        # Also check for registry-based rules that can be converted to INF format
        if ($rule.registry_config -and $rule.registry_config.path) {
            $regPath = $rule.registry_config.path
            $valueName = $rule.registry_config.value_name
            $valueType = $rule.registry_config.value_type
            $valueData = $rule.registry_config.value_data
            
            # Convert REG type to INF type number
            $infType = switch ($valueType) {
                "REG_SZ" { "1" }
                "REG_EXPAND_SZ" { "2" }
                "REG_BINARY" { "3" }
                "REG_DWORD" { "4" }
                "REG_MULTI_SZ" { "7" }
                default { "1" }
            }
            
            # Convert registry path to INF format
            $infPath = $regPath -replace 'HKLM:\\', 'MACHINE\' -replace 'HKCU:\\', 'USER\' -replace '\\\\', '\'
            
            $sections["[Registry Values]"] += @{
                RuleId  = $rule.rule_id
                Title   = $rule.title
                Key     = "$infPath\$valueName"
                Value   = "$infType,$valueData"
                Comment = "CIS $($rule.rule_id) - $($rule.title)"
            }
        }
    }
    
    # Build INF content
    $infContent = @"
; ==============================================================================
; $TemplateName
; $Description
; Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
; Rules: $($Rules.Count)
; Generator: CIS Windows Hardening Generator v1.0
; ==============================================================================

[Unicode]
Unicode=yes

[Profile Description]
Description=$Description

"@
    
    # Add each section
    foreach ($sectionName in $sections.Keys | Sort-Object) {
        $entries = $sections[$sectionName]
        
        if ($entries.Count -gt 0) {
            $infContent += "$sectionName`r`n"
            
            foreach ($entry in $entries) {
                $infContent += "; $($entry.Comment)`r`n"
                $infContent += "$($entry.Key) = $($entry.Value)`r`n"
            }
            
            $infContent += "`r`n"
        }
    }
    
    # Add version section
    $infContent += @"
[Version]
signature="`$CHICAGO`$"
Revision=1
"@
    
    # Write to file (Unicode encoding required for secedit)
    $infContent | Set-Content -Path $OutputPath -Encoding Unicode -Force
    
    # Generate application script
    $applyScriptPath = $OutputPath -replace '\.inf$', '_apply.ps1'
    $applyScript = @"
#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Applies the CIS security template to the local system
.DESCRIPTION
    Uses secedit.exe to apply the security template.
    Must be run as Administrator.
#>

`$templatePath = "$OutputPath"
`$dbPath = "`$env:TEMP\secedit_cis.sdb"
`$logPath = "`$env:TEMP\secedit_cis.log"

Write-Host "Applying CIS Security Template..." -ForegroundColor Cyan
Write-Host "Template: `$templatePath" -ForegroundColor Gray

# Apply the template
`$result = secedit /configure /db `$dbPath /cfg `$templatePath /log `$logPath /quiet

if (`$LASTEXITCODE -eq 0) {
    Write-Host "[+] Security template applied successfully!" -ForegroundColor Green
} else {
    Write-Host "[X] Failed to apply security template. Check log: `$logPath" -ForegroundColor Red
}

# Cleanup
Remove-Item `$dbPath -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Log file: `$logPath" -ForegroundColor Gray
"@
    
    $applyScript | Set-Content -Path $applyScriptPath -Encoding UTF8 -Force
    
    # Generate rollback template (with defaults)
    # Generate rollback template (with defaults)
    # $rollbackPath = $OutputPath -replace '\.inf$', '_rollback.inf'
    # New-RollbackTemplate -Rules $Rules -OutputPath $rollbackPath
    
    return $OutputPath
}

function New-RollbackTemplate {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [array]$Rules,
        
        [Parameter(Mandatory)]
        [string]$OutputPath
    )
    
    $sections = @{
        "[System Access]"   = @()
        "[Registry Values]" = @()
    }
    
    foreach ($ruleItem in $Rules) {
        $rule = $ruleItem.Rule
        
        # Check for rollback info
        if ($rule.remediation_rollback -and $null -ne $rule.remediation_rollback.original_value) {
            
            if ($rule.implementation_gpo -and $rule.implementation_gpo.inf_section) {
                $section = $rule.implementation_gpo.inf_section
                
                if (-not $sections.ContainsKey($section)) {
                    $sections[$section] = @()
                }
                
                $sections[$section] += @{
                    RuleId  = $rule.rule_id
                    Title   = $rule.title
                    Key     = $rule.implementation_gpo.inf_key
                    Value   = $rule.remediation_rollback.original_value
                    Comment = "ROLLBACK: CIS $($rule.rule_id) - Restore default"
                }
            }
        }
    }
    
    # Build rollback INF
    $infContent = @"
; ==============================================================================
; CIS Windows Hardening - ROLLBACK Template
; This template restores Windows default values
; Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
; ==============================================================================

[Unicode]
Unicode=yes

"@
    
    foreach ($sectionName in $sections.Keys | Sort-Object) {
        $entries = $sections[$sectionName]
        
        if ($entries.Count -gt 0) {
            $infContent += "$sectionName`r`n"
            
            foreach ($entry in $entries) {
                $infContent += "; $($entry.Comment)`r`n"
                $infContent += "$($entry.Key) = $($entry.Value)`r`n"
            }
            
            $infContent += "`r`n"
        }
    }
    
    $infContent += @"
[Version]
signature="`$CHICAGO`$"
Revision=1
"@
    
    $infContent | Set-Content -Path $OutputPath -Encoding Unicode -Force
    
    return $OutputPath
}

# Export functions
# Functions available when dot-sourced
