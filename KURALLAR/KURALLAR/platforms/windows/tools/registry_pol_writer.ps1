#Requires -Version 5.1
<#
.SYNOPSIS
    Registry.pol Binary Writer for CIS Windows Hardening
.DESCRIPTION
    Generates Registry.pol files in binary format for GPO.
#>

function New-RegistryPol {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][array]$Rules,
        [Parameter(Mandatory)][string]$OutputPath
    )
    
    $entries = @()
    foreach ($ruleItem in $Rules) {
        $rule = $ruleItem.Rule
        if ($rule.registry_config -and $rule.registry_config.path) {
            $entries += @{
                Key       = $rule.registry_config.path -replace 'HKLM:\\', ''
                ValueName = $rule.registry_config.value_name
                Type      = $rule.registry_config.value_type
                Data      = $rule.registry_config.value_data
            }
        }
    }
    
    if ($entries.Count -eq 0) { return $null }
    
    $stream = [System.IO.MemoryStream]::new()
    $writer = [System.IO.BinaryWriter]::new($stream)
    
    try {
        # PReg header
        $writer.Write([byte[]]@(0x50, 0x52, 0x65, 0x67))
        $writer.Write([int32]1)
        
        foreach ($entry in $entries) {
            $writer.Write([char]'[')
            $writer.Write([System.Text.Encoding]::Unicode.GetBytes($entry.Key + "`0"))
            $writer.Write([byte[]]@(0x3B, 0x00))
            $writer.Write([System.Text.Encoding]::Unicode.GetBytes($entry.ValueName + "`0"))
            $writer.Write([byte[]]@(0x3B, 0x00))
            $typeVal = switch ($entry.Type) {
                "REG_SZ" { 1 }
                "REG_EXPAND_SZ" { 2 }
                "REG_BINARY" { 3 }
                "REG_DWORD" { 4 }
                "REG_MULTI_SZ" { 7 }
                "REG_QWORD" { 11 }
                Default { 1 }
            }
            $writer.Write([int32]$typeVal)
            $writer.Write([byte[]]@(0x3B, 0x00))
            
            $dataBytes = switch ($entry.Type) {
                "REG_DWORD" { 
                    [BitConverter]::GetBytes([int32]$entry.Data) 
                }
                "REG_QWORD" {
                    [BitConverter]::GetBytes([int64]$entry.Data)
                }
                "REG_MULTI_SZ" {
                    $arr = $entry.Data
                    if ($arr -is [string]) { $arr = @($arr) }
                    
                    $byteList = [System.Collections.Generic.List[byte]]::new()
                    foreach ($str in $arr) {
                        $bytes = [System.Text.Encoding]::Unicode.GetBytes($str + "`0")
                        $byteList.AddRange($bytes)
                    }
                    # Terminating null (Empty string at end)
                    $byteList.AddRange([System.Text.Encoding]::Unicode.GetBytes("`0"))
                    $byteList.ToArray()
                }
                Default { 
                    # REG_SZ, REG_EXPAND_SZ
                    [System.Text.Encoding]::Unicode.GetBytes([string]$entry.Data + "`0") 
                }
            }
            $writer.Write([int32]$dataBytes.Length)
            $writer.Write([byte[]]@(0x3B, 0x00))
            $writer.Write($dataBytes)
            $writer.Write([byte[]]@(0x5D, 0x00))
        }
        
        $writer.Flush()
        [System.IO.File]::WriteAllBytes($OutputPath, $stream.ToArray())
        return $OutputPath
    }
    finally {
        $writer.Dispose()
        $stream.Dispose()
    }
}

# Function available when dot-sourced
