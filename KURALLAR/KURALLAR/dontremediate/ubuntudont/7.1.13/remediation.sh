#!/bin/bash

# 7.1.13 Ensure SUID and SGID files are reviewed (Manual)

echo "This is a manual remediation task."
echo "Review the SUID and SGID files listed in the audit and remove the bit from unauthorized files:"
echo ""
echo "To remove SUID bit: chmod u-s <file>"
echo "To remove SGID bit: chmod g-s <file>"
echo ""
echo "Example authorized SUID/SGID files:"
echo "  - /usr/bin/sudo"
echo "  - /usr/bin/passwd"
echo "  - /usr/bin/su"
echo "  - /usr/bin/mount"
echo "  - /usr/bin/umount"
