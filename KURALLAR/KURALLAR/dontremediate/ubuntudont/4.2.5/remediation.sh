#!/bin/bash
# CIS 4.2.5 Ensure ufw outbound connections are configured

echo "Applying remediation for CIS 4.2.5..."

# Set default outgoing policy to allow
ufw default allow outgoing

echo "Remediation complete for CIS 4.2.5"
echo "NOTE: Adjust outbound rules based on your site policy"
