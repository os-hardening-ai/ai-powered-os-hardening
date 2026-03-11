#!/usr/bin/env bash
# CIS 1.1.1.10 Manual Remediation - Disable a specific filesystem kernel module
# Profile: Level 1 - Server, Level 1 - Workstation
#
# SAFETY LEVEL: MANUAL (Safest option)
# Usage: ./remediation_manual.sh <module_name>
# Example: ./remediation_manual.sh gfs2
#
# This script allows you to manually disable ONE module at a time after careful review

set -euo pipefail

# Check arguments
if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <module_name>"
    echo ""
    echo "Example: $0 gfs2"
    echo ""
    echo "Modules with known CVEs:"
    echo "  afs, ceph, cifs, exfat, ext, fat, fscache, fuse, gfs2, nfs_common, nfsd, smbfs_common"
    echo ""
    echo "NEVER disable these (commonly used):"
    echo "  xfs, vfat, ext2, ext3, ext4, overlay"
    exit 1
fi

# Configuration
MOD_NAME="$1"
CONF_DIR="/etc/modprobe.d"
CONF_FILE="${CONF_DIR}/${MOD_NAME}.conf"
KERNEL_VER="$(uname -r)"

# Protected modules
declare -a PROTECTED=("xfs" "vfat" "ext2" "ext3" "ext4" "overlay")
declare -a CVE_MODULES=("afs" "ceph" "cifs" "exfat" "ext" "fat" "fscache" "fuse" "gfs2" "nfs_common" "nfsd" "smbfs_common")

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================================================="
echo " CIS 1.1.1.10 - Manual Remediation for: ${MOD_NAME}"
echo "=========================================================================="
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}[ERROR]${NC} This script must be run as root"
    exit 1
fi

# Check if module is protected
for protected in "${PROTECTED[@]}"; do
    if [[ "$MOD_NAME" == "$protected" ]]; then
        echo -e "${RED}[FATAL]${NC} Module '${MOD_NAME}' is in the protected list!"
        echo "Disabling this module may make your system unbootable."
        exit 1
    fi
done

# Check if module has CVE
HAS_CVE=false
for cve_mod in "${CVE_MODULES[@]}"; do
    if [[ "$MOD_NAME" == "$cve_mod" ]]; then
        HAS_CVE=true
        echo -e "${YELLOW}[WARNING]${NC} Module '${MOD_NAME}' has known CVE vulnerabilities"
        break
    fi
done

# Check if module is built into kernel
if grep -qw "$MOD_NAME" "/lib/modules/${KERNEL_VER}/modules.builtin" 2>/dev/null; then
    echo -e "${YELLOW}[WARNING]${NC} Module '${MOD_NAME}' is built into the kernel"
    echo "This module cannot be disabled as it's compiled into the kernel."
    exit 0
fi

# Check if module exists
if ! find "/lib/modules/${KERNEL_VER}/kernel/fs" -type f -name "${MOD_NAME}.ko*" 2>/dev/null | grep -q .; then
    echo -e "${YELLOW}[INFO]${NC} Module '${MOD_NAME}' not found in filesystem modules"
    echo "This module may not be available on your system."
    exit 0
fi

# Check if module is currently loaded
IS_LOADED=false
if lsmod | grep -qw "^${MOD_NAME}"; then
    IS_LOADED=true
    echo -e "${RED}[WARNING]${NC} Module '${MOD_NAME}' is currently LOADED in the kernel"
fi

# Check if module is mounted
IS_MOUNTED=false
if findmnt -knD 2>/dev/null | awk '{print $2}' | grep -qw "$MOD_NAME"; then
    IS_MOUNTED=true
    echo -e "${RED}[CRITICAL]${NC} Filesystem type '${MOD_NAME}' is currently MOUNTED!"
    echo "Do NOT disable this module while it's in use!"
    echo ""
    echo "Mounted filesystems using this type:"
    findmnt -t "$MOD_NAME" 2>/dev/null
    echo ""
    exit 1
fi

# Check if already disabled
ALREADY_DISABLED=false
if [[ -f "$CONF_FILE" ]]; then
    if grep -q "install ${MOD_NAME} /bin/false" "$CONF_FILE" 2>/dev/null && \
       grep -q "blacklist ${MOD_NAME}" "$CONF_FILE" 2>/dev/null; then
        ALREADY_DISABLED=true
        echo -e "${GREEN}[INFO]${NC} Module '${MOD_NAME}' is already disabled in ${CONF_FILE}"
    fi
fi

# Display current status
echo ""
echo "=== Module Status ==="
echo "Module name: ${MOD_NAME}"
echo "Has CVE: $(${HAS_CVE} && echo 'YES' || echo 'NO')"
echo "Currently loaded: $(${IS_LOADED} && echo 'YES' || echo 'NO')"
echo "Currently mounted: $(${IS_MOUNTED} && echo 'YES' || echo 'NO')"
echo "Already disabled: $(${ALREADY_DISABLED} && echo 'YES' || echo 'NO')"
echo ""

if ${ALREADY_DISABLED}; then
    echo -e "${GREEN}[SUCCESS]${NC} No action needed - module is already properly disabled"
    exit 0
fi

# Confirmation
echo "This script will:"
echo "  1. Create ${CONF_FILE}"
echo "  2. Add 'install ${MOD_NAME} /bin/false' directive"
echo "  3. Add 'blacklist ${MOD_NAME}' directive"
if ${IS_LOADED}; then
    echo "  4. Attempt to unload the module from memory"
fi
echo "  5. Update initramfs"
echo ""

${HAS_CVE} && echo -e "${YELLOW}Note: This module has known CVE vulnerabilities and should be disabled if not needed.${NC}"

echo ""
read -p "Are you sure you want to disable '${MOD_NAME}'? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    echo "Operation cancelled."
    exit 0
fi

# Perform remediation
echo "Starting remediation..."
echo ""

# Create modprobe.d directory if needed
if [[ ! -d "$CONF_DIR" ]]; then
    mkdir -p "$CONF_DIR"
    echo "[CREATED] ${CONF_DIR} directory"
fi

# Create configuration file
{
    echo "# CIS 1.1.1.10 - Disable unused filesystem: ${MOD_NAME}"
    echo "# Generated: $(date '+%Y-%m-%d %H:%M:%S')"
    ${HAS_CVE} && echo "# WARNING: This module has known CVE vulnerabilities"
    echo "# To re-enable, delete this file and run: modprobe ${MOD_NAME}"
    echo ""
    echo "install ${MOD_NAME} /bin/false"
    echo "blacklist ${MOD_NAME}"
} > "$CONF_FILE"

echo -e "${GREEN}[SUCCESS]${NC} Configuration file created: ${CONF_FILE}"

# Unload module if loaded
if ${IS_LOADED}; then
    echo ""
    echo "Attempting to unload module..."
    if modprobe -r "$MOD_NAME" 2>/dev/null; then
        echo -e "${GREEN}[SUCCESS]${NC} Module '${MOD_NAME}' unloaded from kernel"
    elif rmmod "$MOD_NAME" 2>/dev/null; then
        echo -e "${GREEN}[SUCCESS]${NC} Module '${MOD_NAME}' removed from kernel"
    else
        echo -e "${YELLOW}[WARNING]${NC} Could not unload module (may be in use)"
        echo "The module will be disabled on next reboot"
    fi
fi

# Update initramfs
echo ""
echo "Updating initramfs..."
if command -v update-initramfs >/dev/null 2>&1; then
    if update-initramfs -u -k all 2>&1 | grep -v "^update-initramfs:"; then
        echo -e "${GREEN}[SUCCESS]${NC} Initramfs updated"
    fi
elif command -v dracut >/dev/null 2>&1; then
    if dracut -f 2>&1; then
        echo -e "${GREEN}[SUCCESS]${NC} Initramfs updated with dracut"
    fi
else
    echo -e "${YELLOW}[WARNING]${NC} No initramfs tool found"
    echo "You may need to manually update initramfs"
fi

echo ""
echo "=========================================================================="
echo -e "${GREEN}[COMPLETE]${NC} Module '${MOD_NAME}' has been successfully disabled"
echo "=========================================================================="
echo ""
echo "The module is now:"
echo "  - Configured to not load: ${CONF_FILE}"
if ${IS_LOADED}; then
    echo "  - Unloaded from current kernel session"
fi
echo "  - Will remain disabled after reboot"
echo ""
echo "To verify, run:"
echo "  lsmod | grep ${MOD_NAME}    # Should return nothing"
echo "  modprobe ${MOD_NAME}        # Should fail"
echo ""
