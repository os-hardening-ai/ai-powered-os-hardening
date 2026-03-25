#!/bin/bash
# CIS 3.3.1 Ensure IP forwarding is disabled

echo "Applying remediation for CIS 3.3.1..."

# Create sysctl configuration
printf '%s\n' \
    "# CIS 3.3.1 - Disable IP forwarding" \
    "net.ipv4.ip_forward = 0" >> /etc/sysctl.d/60-netipv4_sysctl.conf

printf '%s\n' \
    "# CIS 3.3.1 - Disable IPv6 forwarding" \
    "net.ipv6.conf.all.forwarding = 0" >> /etc/sysctl.d/60-netipv6_sysctl.conf

# Apply settings immediately
sysctl -w net.ipv4.ip_forward=0 2>/dev/null
sysctl -w net.ipv6.conf.all.forwarding=0 2>/dev/null
sysctl -w net.ipv4.route.flush=1 2>/dev/null
sysctl -w net.ipv6.route.flush=1 2>/dev/null

echo "IP forwarding disabled"
echo "Remediation complete for CIS 3.3.1"
