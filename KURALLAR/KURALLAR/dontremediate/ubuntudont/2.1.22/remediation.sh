#!/bin/bash
# CIS Benchmark 2.1.22 - Ensure mail transfer agent is configured for local-only mode
echo "Applying remediation for CIS 2.1.22..."

# Check if postfix is installed
if dpkg-query -W -f='${db:Status-Status}' postfix 2>/dev/null | grep -q "installed"; then
    if [ -f /etc/postfix/main.cf ]; then
        # Backup original config
        cp /etc/postfix/main.cf /etc/postfix/main.cf.bak
        
        # Check if inet_interfaces is already set
        if grep -qE '^\s*inet_interfaces\s*=' /etc/postfix/main.cf; then
            # Update existing setting
            sed -i 's/^\s*inet_interfaces\s*=.*/inet_interfaces = loopback-only/' /etc/postfix/main.cf
        else
            # Add new setting
            echo "inet_interfaces = loopback-only" >> /etc/postfix/main.cf
        fi
        
        echo "Updated postfix configuration"
        
        # Restart postfix
        systemctl restart postfix
        echo "Restarted postfix service"
    else
        echo "WARNING: /etc/postfix/main.cf not found"
    fi
else
    echo "INFO: postfix is not installed, no action needed"
fi

echo "Remediation complete for CIS 2.1.22"
