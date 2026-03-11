#!/bin/bash

# CIS 1.2.2.1 - Ensure updates, patches, and additional security software are installed (Manual)
# This is a MANUAL remediation that requires site-specific policy considerations

echo "==================================================================="
echo "CIS 1.2.2.1 - Ensure updates, patches, and additional security"
echo "               software are installed (Manual)"
echo "==================================================================="
echo ""
echo "This control requires MANUAL remediation with consideration of:"
echo "  - Site policy on update testing periods"
echo "  - Change management procedures"
echo "  - System compatibility requirements"
echo "  - Scheduled maintenance windows"
echo ""

# Check for available updates first
echo "==================================================================="
echo "Step 1: Checking for available updates..."
echo "==================================================================="
echo ""
apt update
echo ""

upgrade_count=$(apt list --upgradable 2>/dev/null | grep -c "upgradable")

if [ "$upgrade_count" -eq 0 ]; then
    echo "✓ System is already up to date. No remediation needed."
    echo ""
    exit 0
fi

echo "Found $upgrade_count package(s) available for upgrade."
echo ""

echo "==================================================================="
echo "Step 2: Review Available Updates"
echo "==================================================================="
echo ""
apt list --upgradable 2>/dev/null
echo ""

echo "==================================================================="
echo "Step 3: Choose Remediation Method"
echo "==================================================================="
echo ""
echo "OPTION 1: Standard Upgrade (Recommended for most systems)"
echo "  Command: apt upgrade"
echo "  Effect: Upgrades packages without removing installed packages"
echo "  Use when: Regular updates and patches"
echo ""
echo "OPTION 2: Distribution Upgrade (For major updates)"
echo "  Command: apt dist-upgrade"
echo "  Effect: Intelligently handles dependency changes, may remove packages"
echo "  Use when: Major version updates or complex dependency resolution needed"
echo ""
echo "OPTION 3: Security-Only Updates"
echo "  Command: apt upgrade -s | grep -i security"
echo "  Effect: Review security-specific updates"
echo "  Use when: Only security patches should be applied"
echo ""

echo "==================================================================="
echo "MANUAL ACTION REQUIRED"
echo "==================================================================="
echo ""
echo "To install updates after reviewing and testing per site policy:"
echo ""
echo "  # For standard updates:"
echo "  sudo apt upgrade -y"
echo ""
echo "  # For distribution upgrade:"
echo "  sudo apt dist-upgrade -y"
echo ""
echo "  # To install security updates only (example):"
echo "  sudo apt install --only-upgrade \$(apt list --upgradable 2>/dev/null | grep security | cut -d'/' -f1)"
echo ""
echo "IMPORTANT NOTES:"
echo "  - Review all updates before installation"
echo "  - Test updates in non-production environment if required"
echo "  - Follow organizational change management procedures"
echo "  - Create backups or snapshots before major updates"
echo "  - Schedule updates during approved maintenance windows"
echo "  - Reboot may be required for kernel or init system updates"
echo ""
echo "==================================================================="
echo "NO AUTOMATED REMEDIATION PERFORMED - MANUAL ACTION REQUIRED"
echo "==================================================================="
