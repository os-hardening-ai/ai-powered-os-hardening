# CIS Windows Hardening GPO Backup

Generated: 2026-01-30 19:25:19
GPO Name: CIS_Hardening_20260130_192519
Rules Included: 7

## How to Import

### Option 1: Using Group Policy Management Console (GPMC)
1. Open Group Policy Management Console
2. Right-click on "Group Policy Objects"
3. Select "Import Settings..."
4. Browse to this folder
5. Select the backup to import

### Option 2: Using PowerShell
`powershell

Import-Module GroupPolicy
Import-GPO -BackupId "{0C0C801A-DFE1-4218-AB3D-7907F4937915}" -Path "C:\Users\cagri\OneDrive\Belgeler\GitHub\sh-bitirme-proje\platforms\windows\tools\..\output\GPO_Backup_20260130_192519" -TargetName "CIS_Hardening_20260130_192519" -CreateIfNeeded
`

## Rules Included

- CIS 1.1.1: Ensure 'Enforce password history' is set to '24 or more password(s)'
- CIS 1.1.2: Ensure 'Maximum password age' is set to '365 or fewer days, but not 0'
- CIS 1.1.3: Ensure 'Minimum password age' is set to '1 or more day(s)'
- CIS 1.1.4: Ensure 'Minimum password length' is set to '14 or more character(s)'
- CIS 1.1.5: Ensure 'Password must meet complexity requirements' is set to 'Enabled'
- CIS 1.1.6: Ensure 'Relax minimum password length limits' is set to 'Enabled'
- CIS 1.1.7: Ensure 'Store passwords using reversible encryption' is set to 'Disabled'


## Notes

- This GPO backup was auto-generated and should be reviewed before deployment
- Test in a non-production environment first
- Some settings may need to be adjusted for your environment
- Replace 'DOMAIN' with your actual domain name in the XML files if needed
