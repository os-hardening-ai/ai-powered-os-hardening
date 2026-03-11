#!/bin/bash
# CIS 4.1.1 Ensure a single firewall configuration utility is in use

echo "Applying remediation for CIS 4.1.1..."
echo ""
echo "This script will enable UFW as the single firewall utility."
echo "Modify this script if you prefer nftables instead."
echo ""

# Enable UFW as the default choice
apt-get install -y ufw 2>/dev/null

# Disable nftables if enabled
if systemctl is-enabled nftables.service 2>/dev/null | grep -q "enabled"; then
    systemctl stop nftables.service
    systemctl disable nftables.service
    echo "Disabled nftables.service"
fi

# Enable UFW
systemctl unmask ufw.service 2>/dev/null
systemctl enable ufw.service
systemctl start ufw.service

# Enable UFW (interactive confirmation bypassed)
echo "y" | ufw enable 2>/dev/null

echo ""
echo "Remediation complete for CIS 4.1.1"
echo "UFW is now the active firewall utility"
