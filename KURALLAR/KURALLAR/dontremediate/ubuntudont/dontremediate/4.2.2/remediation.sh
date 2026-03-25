#!/bin/bash
# CIS 4.2.2 Ensure iptables-persistent is not installed with ufw

echo "Applying remediation for CIS 4.2.2..."

if dpkg -l iptables-persistent 2>/dev/null | grep -q "^ii"; then
    apt-get purge -y iptables-persistent
    echo "Removed iptables-persistent"
else
    echo "iptables-persistent is not installed"
fi

echo "Remediation complete for CIS 4.2.2"
