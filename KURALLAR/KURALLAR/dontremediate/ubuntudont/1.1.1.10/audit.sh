#!/usr/bin/env bash
# CIS 1.1.1.10 - Ensure unused filesystems kernel modules are not available
# Profile: Level 1 - Server, Level 1 - Workstation
# This is the comprehensive audit script from CIS Benchmark

{
    a_output=(); a_output2=(); a_modprope_config=(); a_excluded=(); a_available_modules=(); a_builtin=()
    a_ignore=("xfs" "vfat" "ext2" "ext3" "ext4")
    a_cve_exists=("afs" "ceph" "cifs" "exfat" "ext" "fat" "fscache" "fuse" "gfs2" "nfs_common" "nfsd" "smbfs_common")

    f_module_chk()
    {
        l_out2=""; grep -Pq -- "\b$l_mod_name\b" <<< "${a_cve_exists[*]}" && l_out2=" <- CVE exists!"

        # Check if module is built into kernel (cannot be disabled)
        if grep -qw "$l_mod_name" "/lib/modules/$(uname -r)/modules.builtin" 2>/dev/null; then
            a_builtin+=(" - Kernel module: \"$l_mod_name\" is built into kernel (cannot be disabled)$l_out2")
            return
        fi

        if ! grep -Pq -- '\bblacklist\h+'"$l_mod_name"'\b' <<< "${a_modprope_config[*]}"; then
            a_output2+=(" - Kernel module: \"$l_mod_name\" is not fully disabled $l_out2")
        elif ! grep -Pq -- '\binstall\h+'"$l_mod_name"'\h+(\/usr)?\/bin\/(false|true)\b' <<< "${a_modprope_config[*]}"; then
            a_output2+=(" - Kernel module: \"$l_mod_name\" is not fully disabled $l_out2")
        fi
        if lsmod | grep "$l_mod_name" &> /dev/null; then # Check if the module is currently loaded
            l_output2+=(" - Kernel module: \"$l_mod_name\" is loaded" "")
        fi
    }

    while IFS= read -r -d $'\0' l_module_dir; do
        a_available_modules+=("$(basename "$l_module_dir")")
    done < <(find "$(readlink -f /lib/modules/"$(uname -r)"/kernel/fs)" -mindepth 1 -maxdepth 1 -type d ! -empty -print0 2>/dev/null)

    while IFS= read -r l_exclude; do
        if grep -Pq -- "\b$l_exclude\b" <<< "${a_cve_exists[*]}"; then
            a_output2+=(" - ** WARNING: kernel module: \"$l_exclude\" has a CVE and is currently mounted! **")
        elif grep -Pq -- "\b$l_exclude\b" <<< "${a_available_modules[*]}"; then
            a_output+=(" - Kernel module: \"$l_exclude\" is currently mounted - do NOT unload or disable")
        fi
        ! grep -Pq -- "\b$l_exclude\b" <<< "${a_ignore[*]}" && a_ignore+=("$l_exclude")
    done < <(findmnt -knD 2>/dev/null | awk '{print $2}' | sort -u)

    while IFS= read -r l_config; do
        a_modprope_config+=("$l_config")
    done < <(modprobe --showconfig 2>/dev/null | grep -P '^\h*(blacklist|install)')

    for l_mod_name in "${a_available_modules[@]}"; do # Iterate over all filesystem modules
        [[ "$l_mod_name" =~ overlay ]] && l_mod_name="${l_mod_name::-2}"
        if grep -Pq -- "\b$l_mod_name\b" <<< "${a_ignore[*]}"; then
            a_excluded+=(" - Kernel module: \"$l_mod_name\"")
        else
            f_module_chk
        fi
    done

    echo "=== CIS 1.1.1.10 Audit: Unused Filesystem Kernel Modules ==="
    echo ""

    [ "${#a_excluded[@]}" -gt 0 ] && printf '%s\n' "" " -- INFO: Intentionally Skipped Modules --" \
        "${a_excluded[@]}"

    [ "${#a_builtin[@]}" -gt 0 ] && printf '%s\n' "" " -- INFO: Built-in Modules (Cannot Be Disabled) --" \
        "${a_builtin[@]}"

    if [ "${#a_output2[@]}" -le 0 ]; then
        printf '%s\n' "" "[ PASS ] No unused filesystem kernel modules are enabled" "${a_output[@]}" ""
    else
        printf '%s\n' "" "[ FAIL ] ** REVIEW the following **" "${a_output2[@]}"
        [ "${#a_output[@]}" -gt 0 ] && printf '%s\n' "" "-- Correctly Configured: --" "${a_output[@]}" ""
    fi

    echo ""
    echo "=== Audit Complete ==="
    echo ""

    # Summary
    local l_disabled_count=$((${#a_available_modules[@]} - ${#a_excluded[@]} - ${#a_builtin[@]} - ${#a_output2[@]}))
    echo "Summary:"
    echo "  - Total filesystem modules found: ${#a_available_modules[@]}"
    echo "  - Properly disabled: $l_disabled_count"
    echo "  - Protected/mounted (skipped): ${#a_excluded[@]}"
    echo "  - Built into kernel: ${#a_builtin[@]}"
    echo "  - Need attention: ${#a_output2[@]}"
    echo ""

    if [ "${#a_output2[@]}" -le 0 ]; then
        echo "Result: PASS - All loadable filesystem modules are properly configured"
    else
        echo "WARNING: Disabling or denylisting filesystem modules that are in use may be FATAL."
        echo "         Review this list carefully before running remediation."
    fi
}
