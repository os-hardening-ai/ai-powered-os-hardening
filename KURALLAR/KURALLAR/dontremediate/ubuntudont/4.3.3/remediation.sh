#!/bin/bash
# CIS 4.3.3 Ensure iptables are flushed with nftables

echo "Applying remediation for CIS 4.3.3..."

iptables -F
ip6tables -F

echo "iptables and ip6tables flushed"
echo "Remediation complete for CIS 4.3.3"
