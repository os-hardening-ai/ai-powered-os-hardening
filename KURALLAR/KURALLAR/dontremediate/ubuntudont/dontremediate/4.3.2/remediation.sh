#!/bin/bash
# CIS 4.3.2 Ensure ufw is uninstalled or disabled with nftables

echo "Applying remediation for CIS 4.3.2..."

ufw disable 2>/dev/null
systemctl stop ufw.service 2>/dev/null
systemctl mask ufw.service 2>/dev/null

echo "Remediation complete for CIS 4.3.2"
