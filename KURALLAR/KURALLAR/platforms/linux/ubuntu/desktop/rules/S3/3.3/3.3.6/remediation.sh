#!/bin/bash
# CIS 3.3.6 Ensure secure ICMP redirects are not accepted

echo "Applying remediation for CIS 3.3.6..."

printf '%s\n' \
    "# CIS 3.3.6 - Do not accept secure ICMP redirects" \
    "net.ipv4.conf.all.secure_redirects = 0" \
    "net.ipv4.conf.default.secure_redirects = 0" >> /etc/sysctl.d/60-netipv4_sysctl.conf

sysctl -w net.ipv4.conf.all.secure_redirects=0
sysctl -w net.ipv4.conf.default.secure_redirects=0
sysctl -w net.ipv4.route.flush=1

echo "Remediation complete for CIS 3.3.6"
