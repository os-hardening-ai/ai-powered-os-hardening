#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="/tmp"
FSTAB_FILE="/etc/fstab"
FSTAB_BACKUP="/etc/fstab.backup-nodev-$(date +%Y%m%d-%H%M%S)"

echo "[CHECK] Remediating: ensure nodev on /tmp"

########################################
# 1) Runtime mount üzerinde nodev ekle
########################################

# Mevcut mount opsiyonlarını al
if command -v findmnt >/dev/null 2>&1; then
    mount_opts=$(findmnt -n -o OPTIONS "${TMP_DIR}" 2>/dev/null || true)
else
    # findmnt yoksa, fallback olarak mount çıktısından çek
    mount_opts=$(mount | awk '$3=="/tmp"{gsub(/[()]/,"",$6);print $6}' | head -n1)
fi

if [[ -z "${mount_opts}" ]]; then
    echo "[ERROR] Could not determine /tmp mount options."
    exit 1
fi

if echo "${mount_opts}" | grep -qw nodev; then
    echo "[INFO] nodev already present on /tmp runtime mount"
else
    new_opts="${mount_opts},nodev"
    echo "[ACTION] Remounting /tmp with options: ${new_opts}"
    mount -o "remount,${new_opts}" "${TMP_DIR}"
    echo "[SUCCESS] /tmp remounted with nodev (runtime)"
fi

########################################
# 2) /etc/fstab yedeği
########################################

if [[ -f "${FSTAB_FILE}" ]]; then
    cp -p "${FSTAB_FILE}" "${FSTAB_BACKUP}"
    echo "[BACKUP] ${FSTAB_FILE} backed up to ${FSTAB_BACKUP}"
else
    echo "[ERROR] ${FSTAB_FILE} not found."
    exit 1
fi

########################################
# 3) /etc/fstab içinde /tmp satırına nodev ekle
########################################

# Eğer /tmp için entry yoksa, bu kural ekleme yapmaz; uyarı verir.
if ! grep -Eq '^[[:space:]]*[^#[:space:]]+[[:space:]]+/tmp[[:space:]]+' "${FSTAB_FILE}"; then
    echo "[WARNING] /tmp not found in ${FSTAB_FILE}. Separate partition rule should create it."
    echo "[RESULT] Runtime nodev ok, fstab için upstream kural bekleniyor."
    exit 2
fi

tmpfile=$(mktemp)

awk -v mp="${TMP_DIR}" '
BEGIN { OFS="\t" }

# Yorum satırlarını aynen geç
/^#/ { print; next }

# /tmp entrysi olan satır
$2 == mp {
    # 4. alan opsiyonlar; boş veya "-" ise defaults yap
    if ($4 == "" || $4 == "-") {
        $4 = "defaults"
    }

    # opsiyonları parçala, nodev olup olmadığına bak
    n = split($4, opts, ",")
    has_nodev = 0
    for (i = 1; i <= n; i++) {
        if (opts[i] == "nodev") {
            has_nodev = 1
        }
    }

    if (!has_nodev) {
        $4 = $4 ",nodev"
    }

    print
    next
}

# diğer satırlar
{ print }
' "${FSTAB_FILE}" > "${tmpfile}"

mv "${tmpfile}" "${FSTAB_FILE}"

########################################
# 4) Son doğrulama (opsiyonel ama faydalı)
########################################

final_opts=$(findmnt -n -o OPTIONS "${TMP_DIR}" 2>/dev/null || echo "${mount_opts}")

echo "[VERIFY] /tmp mount options after remediation:"
echo "  ${final_opts}"

if echo "${final_opts}" | grep -qw nodev; then
    echo "[RESULT] PASS: /tmp has nodev (runtime) and /etc/fstab updated."
    exit 0
else
    echo "[RESULT] WARNING: /etc/fstab updated, but runtime options missing nodev."
    echo "         Reboot or rerun remount may be required."
    exit 2
fi
