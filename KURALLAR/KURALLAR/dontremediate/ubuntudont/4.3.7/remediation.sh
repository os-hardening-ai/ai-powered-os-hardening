#!/bin/bash
# CIS 4.3.7 Ensure nftables outbound and established connections are configured

echo "Applying remediation for CIS 4.3.7..."

# Input - allow established connections
nft add rule inet filter input ct state established,related accept 2>/dev/null

# Output - allow new and established connections
nft add rule inet filter output ct state new,established,related accept 2>/dev/null

echo "Remediation complete for CIS 4.3.7"
