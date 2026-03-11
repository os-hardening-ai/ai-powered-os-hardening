# CIS Windows Hardening GPO Backup

Generated: 2026-02-18 12:15:24
GPO Name: CIS_Hardening_20260218_121523
Rules Included: 49

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
Import-GPO -BackupId "{9D243F12-F766-41F9-911F-A89668A2D1D7}" -Path "<path-to-this-folder>" -TargetName "CIS_Hardening_20260218_121523" -CreateIfNeeded
```

## Rules Included

- CIS 1.1.1: Ensure 'Enforce password history' is set to '24 or more password(s)'
- CIS 1.1.2: Ensure 'Maximum password age' is set to '365 or fewer days, but not 0'
- CIS 1.1.3: Ensure 'Minimum password age' is set to '1 or more day(s)'
- CIS 1.1.4: Ensure 'Minimum password length' is set to '14 or more character(s)'
- CIS 1.1.5: Ensure 'Password must meet complexity requirements' is set to 'Enabled'
- CIS 1.1.6: Ensure 'Relax minimum password length limits' is set to 'Enabled'
- CIS 1.1.7: Ensure 'Store passwords using reversible encryption' is set to 'Disabled'
- CIS 1.2.1: Ensure 'Account lockout duration' is set to '15 or more minute(s)'
- CIS 1.2.2: Ensure 'Account lockout threshold' is set to '5 or fewer invalid logon attempt(s), but not 0'
- CIS 1.2.4: Ensure 'Reset account lockout counter after' is set to '15 or more minute(s)'
- CIS 2.2.1: Ensure 'Access Credential Manager as a trusted caller' is set to 'No One'
- CIS 2.2.10: Ensure 'Create a pagefile' is set to 'Administrators'
- CIS 2.2.11: Ensure 'Create a token object' is set to 'No One'
- CIS 2.2.12: Ensure 'Create global objects' is set to 'Administrators, LOCAL SERVICE, NETWORK SERVICE, SERVICE'
- CIS 2.2.13: Ensure 'Create permanent shared objects' is set to 'No One'
- CIS 2.2.14: Ensure 'Create symbolic links' is set to 'Administrators'
- CIS 2.2.15: Ensure 'Debug programs' is set to 'Administrators'
- CIS 2.2.16: Ensure 'Deny access to this computer from the network' to include 'Guests'
- CIS 2.2.17: Ensure 'Deny log on as a batch job' to include 'Guests'
- CIS 2.2.18: Ensure 'Deny log on as a service' to include 'Guests'
- CIS 2.2.19: Ensure 'Deny log on locally' to include 'Guests'
- CIS 2.2.2: Ensure 'Access this computer from the network' is set to 'Administrators, Remote Desktop Users'
- CIS 2.2.20: Ensure 'Deny log on through Remote Desktop Services' to include 'Guests'
- CIS 2.2.21: Ensure 'Enable computer and user accounts to be trusted for delegation' is set to 'No One'
- CIS 2.2.22: Ensure 'Force shutdown from a remote system' is set to 'Administrators'
- CIS 2.2.23: Ensure 'Generate security audits' is set to 'LOCAL SERVICE, NETWORK SERVICE'
- CIS 2.2.24: Ensure 'Impersonate a client after authentication' is set to 'Administrators, LOCAL SERVICE, NETWORK SERVICE, SERVICE'
- CIS 2.2.25: Ensure 'Increase scheduling priority' is set to 'Administrators, Window Manager\Window Manager Group'
- CIS 2.2.26: Ensure 'Load and unload device drivers' is set to 'Administrators'
- CIS 2.2.27: Ensure 'Lock pages in memory' is set to 'No One'
- CIS 2.2.28: Ensure 'Log on as a batch job' is set to 'Administrators'
- CIS 2.2.29: Ensure 'Log on as a service' is configured
- CIS 2.2.3: Ensure 'Act as part of the operating system' is set to 'No One'
- CIS 2.2.30: Ensure 'Manage auditing and security log' is set to 'Administrators'
- CIS 2.2.31: Ensure 'Modify an object label' is set to 'No One'
- CIS 2.2.32: Ensure 'Modify firmware environment values' is set to 'Administrators'
- CIS 2.2.33: Ensure 'Perform volume maintenance tasks' is set to 'Administrators'
- CIS 2.2.34: Ensure 'Profile single process' is set to 'Administrators'
- CIS 2.2.35: Ensure 'Profile system performance' is set to 'Administrators, NT SERVICE\WdiServiceHost'
- CIS 2.2.36: Ensure 'Replace a process level token' is set to 'LOCAL SERVICE, NETWORK SERVICE'
- CIS 2.2.37: Ensure 'Restore files and directories' is set to 'Administrators'
- CIS 2.2.38: Ensure 'Shut down the system' is set to 'Administrators, Users'
- CIS 2.2.39: Ensure 'Take ownership of files or other objects' is set to 'Administrators'
- CIS 2.2.4: Ensure 'Adjust memory quotas for a process' is set to 'Administrators, LOCAL SERVICE, NETWORK SERVICE'
- CIS 2.2.5: Ensure 'Allow log on locally' is set to 'Administrators, Users'
- CIS 2.2.6: Ensure 'Allow log on through Remote Desktop Services' is set to 'Administrators, Remote Desktop Users'
- CIS 2.2.7: Ensure 'Back up files and directories' is set to 'Administrators'
- CIS 2.2.8: Ensure 'Change the system time' is set to 'Administrators, LOCAL SERVICE'
- CIS 2.2.9: Ensure 'Change the time zone' is set to 'Administrators, LOCAL SERVICE, Users'


## Important Notes

- **Review before deployment** â€” Always verify settings in GPMC before linking
- **Test first** â€” Apply to a test OU with a few machines before organization-wide rollout
- **Not linked by default** â€” The imported GPO must be manually linked to target OUs
- **Portable** â€” Domain metadata in XML files are generic placeholders; Import-GPO handles remapping automatically
