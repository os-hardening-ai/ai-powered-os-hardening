#!/usr/bin/env bash
# CIS 1.1.1.10 Remediation - Disable unused filesystem kernel modules
# Profile: Level 1 - Server, Level 1 - Workstation
#
# SAFETY LEVEL: SEMI-AUTOMATIC with manual confirmation
# This script will ONLY disable modules that are:
#   1. Not currently mounted
#   2. Not in the protected list (xfs, vfat, ext2/3/4)
#   3. Available on the system

set -euo pipefail

# Configuration
CONF_DIR="/etc/modprobe.d"
KERNEL_VER="$(uname -r)"
LOG_PREFIX="[CIS-1.1.1.10]"

# Arrays
declare -a a_ignore=("xfs" "vfat" "ext2" "ext3" "ext4" "overlay")
declare -a a_cve_exists=("afs" "ceph" "cifs" "exfat" "ext" "fat" "fscache" "fuse" "gfs2" "nfs_common" "nfsd" "smbfs_common")
declare -a a_mounted=()
declare -a a_available_modules=()
declare -a a_to_disable=()
declare -a a_disabled=()
declare -a a_skipped=()

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${LOG_PREFIX} [INFO] $1"
}

log_success() {
    echo -e "${LOG_PREFIX} ${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${LOG_PREFIX} ${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${LOG_PREFIX} ${RED}[ERROR]${NC} $1"
}

# Get list of mounted filesystems
get_mounted_filesystems() {
    while IFS= read -r fs_type; do
        a_mounted+=("$fs_type")
    done < <(findmnt -knD 2>/dev/null | awk '{print $2}' | sort -u)
}

# Get available filesystem modules
get_available_modules() {
    local fs_kernel_path
    fs_kernel_path="$(readlink -f /lib/modules/${KERNEL_VER}/kernel/fs 2>/dev/null)" || return 0

    if [[ -d "$fs_kernel_path" ]]; then
        while IFS= read -r -d $'\0' module_dir; do
            local mod_name
            mod_name="$(basename "$module_dir")"
            [[ "$mod_name" =~ overlay ]] && mod_name="${mod_name::-2}"
            a_available_modules+=("$mod_name")
        done < <(find "$fs_kernel_path" -mindepth 1 -maxdepth 1 -type d ! -empty -print0 2>/dev/null)
    fi
}

# Check if module is in protected list
is_protected() {
    local mod_name="$1"
    for protected in "${a_ignore[@]}"; do
        [[ "$mod_name" == "$protected" ]] && return 0
    done
    return 1
}

# Check if module is mounted
is_mounted() {
    local mod_name="$1"
    for mounted in "${a_mounted[@]}"; do
        [[ "$mod_name" == "$mounted" ]] && return 0
    done
    return 1
}

# Check if module has CVE
has_cve() {
    local mod_name="$1"
    for cve_mod in "${a_cve_exists[@]}"; do
        [[ "$mod_name" == "$cve_mod" ]] && return 0
    done
    return 1
}

# Check if module is already disabled
is_already_disabled() {
    local mod_name="$1"
    local showconfig
    showconfig="$(modprobe --showconfig 2>/dev/null | grep -P '^\h*(blacklist|install)\h+'"$mod_name"'\b' || true)"

    if grep -Pq '\bblacklist\h+'"$mod_name"'\b' <<< "$showconfig" && \
       grep -Pq '\binstall\h+'"$mod_name"'\h+(\/usr)?\/bin\/(false|true)\b' <<< "$showconfig"; then
        return 0
    fi
    return 1
}

# Disable a single module
disable_module() {
    local mod_name="$1"
    local conf_file="${CONF_DIR}/${mod_name}.conf"
    local cve_note=""

    has_cve "$mod_name" && cve_note=" (CVE exists)"

    log_info "Disabling module: ${mod_name}${cve_note}"

    # Check if module is built into kernel
    if grep -qw "$mod_name" "/lib/modules/${KERNEL_VER}/modules.builtin" 2>/dev/null; then
        log_warning "Module ${mod_name} is built into kernel - cannot be disabled"
        a_skipped+=("${mod_name} (built-in)")
        return 1
    fi

    # Create modprobe.d directory if needed
    [[ ! -d "$CONF_DIR" ]] && mkdir -p "$CONF_DIR"

    # Create configuration file
    {
        echo "# CIS 1.1.1.10 - Disable unused filesystem: ${mod_name}"
        echo "# Generated: $(date '+%Y-%m-%d %H:%M:%S')"
        has_cve "$mod_name" && echo "# WARNING: This module has known CVE vulnerabilities"
        echo "install ${mod_name} /bin/false"
        echo "blacklist ${mod_name}"
    } > "$conf_file"

    log_success "Configuration file created: ${conf_file}"

    # Unload module if currently loaded
    if lsmod | grep -qw "^${mod_name}"; then
        if modprobe -r "$mod_name" 2>/dev/null; then
            log_success "Module ${mod_name} unloaded from kernel"
        else
            log_warning "Could not unload ${mod_name} - may be in use (will be disabled on reboot)"
        fi
    fi

    a_disabled+=("${mod_name}${cve_note}")
    return 0
}

# Main execution
main() {
    echo "=========================================================================="
    echo " CIS 1.1.1.10 - Remediation: Disable Unused Filesystem Kernel Modules"
    echo "=========================================================================="
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                          ⚠️  WARNING  ⚠️                            ║${NC}"
    echo -e "${RED}║                                                                    ║${NC}"
    echo -e "${RED}║  This script will AUTOMATICALLY disable multiple kernel modules!  ║${NC}"
    echo -e "${RED}║                                                                    ║${NC}"
    echo -e "${RED}║  For PRODUCTION systems, use: remediation_manual.sh               ║${NC}"
    echo -e "${RED}║                                                                    ║${NC}"
    echo -e "${RED}║  This automatic mode is recommended ONLY for:                     ║${NC}"
    echo -e "${RED}║  - Test/development systems                                       ║${NC}"
    echo -e "${RED}║  - Non-critical environments                                      ║${NC}"
    echo -e "${RED}║                                                                    ║${NC}"
    echo -e "${RED}║  Read KULLANIM.md or README.md before continuing!                 ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    read -p "Are you SURE this is NOT a production system? (yes/no): " -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
        log_info "Cancelled. Use remediation_manual.sh for safer operation."
        exit 0
    fi

    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi

    log_info "Gathering system information..."
    get_mounted_filesystems
    get_available_modules

    log_info "Found ${#a_available_modules[@]} available filesystem modules"
    log_info "Found ${#a_mounted[@]} mounted filesystem types"
    echo ""

    # Analyze which modules should be disabled
    log_info "Analyzing modules for safety..."
    for mod_name in "${a_available_modules[@]}"; do
        if is_protected "$mod_name"; then
            a_skipped+=("${mod_name} (protected)")
        elif is_mounted "$mod_name"; then
            local warn_msg="${mod_name} (currently mounted)"
            has_cve "$mod_name" && warn_msg="${warn_msg} ** HAS CVE **"
            a_skipped+=("$warn_msg")
            has_cve "$mod_name" && log_warning "Module ${mod_name} is mounted but has known CVEs!"
        elif is_already_disabled "$mod_name"; then
            a_skipped+=("${mod_name} (already disabled)")
        else
            a_to_disable+=("$mod_name")
        fi
    done

    echo ""
    log_info "=== Analysis Results ==="
    echo ""

    if [[ ${#a_to_disable[@]} -eq 0 ]]; then
        log_success "No modules need to be disabled"
        [[ ${#a_skipped[@]} -gt 0 ]] && {
            echo ""
            log_info "Skipped modules:"
            printf '  - %s\n' "${a_skipped[@]}"
        }
        exit 0
    fi

    echo "Modules to be disabled:"
    for mod in "${a_to_disable[@]}"; do
        local cve_note=""
        has_cve "$mod" && cve_note="${YELLOW} (has CVE)${NC}"
        echo -e "  - ${mod}${cve_note}"
    done

    [[ ${#a_skipped[@]} -gt 0 ]] && {
        echo ""
        echo "Modules that will be skipped:"
        printf '  - %s\n' "${a_skipped[@]}"
    }

    echo ""
    log_warning "This will modify /etc/modprobe.d/ and may unload kernel modules"
    read -p "Do you want to proceed? (yes/no): " -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
        log_info "Remediation cancelled by user"
        exit 0
    fi

    # Perform remediation
    log_info "Starting remediation..."
    echo ""

    for mod_name in "${a_to_disable[@]}"; do
        disable_module "$mod_name" || true
    done

    echo ""
    log_info "=== Remediation Summary ==="
    echo ""

    if [[ ${#a_disabled[@]} -gt 0 ]]; then
        log_success "Successfully disabled ${#a_disabled[@]} module(s):"
        printf '  - %s\n' "${a_disabled[@]}"
    fi

    if [[ ${#a_skipped[@]} -gt 0 ]]; then
        echo ""
        log_info "Skipped ${#a_skipped[@]} module(s):"
        printf '  - %s\n' "${a_skipped[@]}"
    fi

    # Update initramfs
    echo ""
    log_info "Updating initramfs..."
    if command -v update-initramfs >/dev/null 2>&1; then
        update-initramfs -u -k all 2>&1 | grep -v "^update-initramfs:" || true
        log_success "Initramfs updated successfully"
    elif command -v dracut >/dev/null 2>&1; then
        dracut -f 2>&1 || true
        log_success "Initramfs updated with dracut"
    else
        log_warning "No initramfs update tool found (update-initramfs or dracut)"
    fi

    echo ""
    log_success "Remediation completed successfully"
    log_info "Changes will take full effect after system reboot"
    echo ""
}

# Run main function
main "$@"
