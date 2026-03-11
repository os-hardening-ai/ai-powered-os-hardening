# CIS Windows Hardening GPO Backup

Generated: 2026-02-17 13:00:11
GPO Name: CIS_Hardening_20260217_130011
Rules Included: 7

## Quick Start

### Option 1: Use the Import Script (Recommended)
```powershell
# Run as Domain Admin on a Domain Controller or RSAT-enabled machine
.\Import-Policy.ps1
```

### Option 2: Using Group Policy Management Console (GPMC)
1. Open Group Policy Management Console
2. Right-click on "Group Policy Objects"
3. Select "Import Settings..."
4. Browse to this folder
5. Select the backup to import

### Option 3: Manual PowerShell
```powershell
Import-Module GroupPolicy
Import-GPO -BackupId "{ED1C8F85-AABE-429E-9BE2-98A0BCC34E87}" -Path "<path-to-this-folder>" -TargetName "CIS_Hardening_20260217_130011" -CreateIfNeeded
```

## Rules Included

- CIS 1.1.1: Ensure 'Enforce password history' is set to '24 or more password(s)'
- CIS 1.1.2: Ensure 'Maximum password age' is set to '365 or fewer days, but not 0'
- CIS 1.1.3: Ensure 'Minimum password age' is set to '1 or more day(s)'
- CIS 1.1.4: Ensure 'Minimum password length' is set to '14 or more character(s)'
- CIS 1.1.5: Ensure 'Password must meet complexity requirements' is set to 'Enabled'
- CIS 1.1.6: Ensure 'Relax minimum password length limits' is set to 'Enabled'
- CIS 1.1.7: Ensure 'Store passwords using reversible encryption' is set to 'Disabled'


## Important Notes

- **Review before deployment** â€” Always verify settings in GPMC before linking
- **Test first** â€” Apply to a test OU with a few machines before organization-wide rollout
- **Not linked by default** â€” The imported GPO must be manually linked to target OUs
- **Portable** â€” Domain metadata in XML files are generic placeholders; Import-GPO handles remapping automatically
