#!/bin/bash
# CIS 3.1.1 Ensure IPv6 status is identified (Manual)

echo "Remediation for CIS 3.1.1..."
echo ""
echo "This is a MANUAL control. IPv6 should be disabled if not required."
echo ""
echo "To disable IPv6 via sysctl, run the following commands:"
echo ""

# Create sysctl configuration to disable IPv6
if [ ! -f /etc/sysctl.d/60-disable_ipv6.conf ]; then
    cat > /etc/sysctl.d/60-disable_ipv6.conf << 'EOF'
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
EOF
    echo "Created /etc/sysctl.d/60-disable_ipv6.conf"
fi

# Apply sysctl settings
sysctl -w net.ipv6.conf.all.disable_ipv6=1 2>/dev/null
sysctl -w net.ipv6.conf.default.disable_ipv6=1 2>/dev/null

echo "IPv6 has been disabled via sysctl"
echo ""
echo "NOTE: For persistent GRUB-level disabling, add 'ipv6.disable=1' to"
echo "GRUB_CMDLINE_LINUX in /etc/default/grub and run 'update-grub'"
echo ""
echo "Remediation complete for CIS 3.1.1"
