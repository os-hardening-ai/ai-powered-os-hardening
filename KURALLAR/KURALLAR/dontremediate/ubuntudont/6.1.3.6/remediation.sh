#!/bin/bash

# 6.1.3.6 Ensure rsyslog is configured to send logs to a remote log host (Manual)

echo "Configuring rsyslog to send logs to a remote log host..."
echo ""
echo "Manual configuration required:"
echo "1. Edit /etc/rsyslog.conf or create a file in /etc/rsyslog.d/"
echo "2. Add one of the following lines:"
echo "   - For UDP: *.* @<remote-host>:514"
echo "   - For TCP: *.* @@<remote-host>:514"
echo "   - For TLS: *.* @@(o)<remote-host>:6514"
echo "3. Replace <remote-host> with your log server address"
echo "4. Run: systemctl restart rsyslog"
echo ""
echo "Example:"
echo "echo '*.* @@logserver.example.com:514' >> /etc/rsyslog.d/50-remote.conf"
