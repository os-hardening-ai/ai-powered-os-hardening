#!/bin/bash

# 6.2.2.3 Ensure system is disabled when audit logs are full (Automated)

echo "Configuring system behavior when audit logs are full..."

# Configure appropriate actions
sed -i 's/^space_left_action\s*=.*/space_left_action = email/' /etc/audit/auditd.conf
sed -i 's/^admin_space_left_action\s*=.*/admin_space_left_action = halt/' /etc/audit/auditd.conf
sed -i 's/^disk_full_action\s*=.*/disk_full_action = halt/' /etc/audit/auditd.conf
sed -i 's/^disk_error_action\s*=.*/disk_error_action = halt/' /etc/audit/auditd.conf

# Add settings if they don't exist
grep -q "^space_left_action" /etc/audit/auditd.conf || echo "space_left_action = email" >> /etc/audit/auditd.conf
grep -q "^admin_space_left_action" /etc/audit/auditd.conf || echo "admin_space_left_action = halt" >> /etc/audit/auditd.conf
grep -q "^disk_full_action" /etc/audit/auditd.conf || echo "disk_full_action = halt" >> /etc/audit/auditd.conf
grep -q "^disk_error_action" /etc/audit/auditd.conf || echo "disk_error_action = halt" >> /etc/audit/auditd.conf

systemctl restart auditd

echo "System will now halt when audit logs are full"
