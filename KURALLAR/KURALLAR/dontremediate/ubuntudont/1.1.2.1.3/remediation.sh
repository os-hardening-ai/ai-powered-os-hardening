#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="/tmp"
FSTAB_FILE="/etc/fstab"
FSTAB_BACKUP="/etc/fstab.backup-noexec-$(date +%Y%m%d-%H%M%S)"

echo "[CHECK] Remediating: ensure noexec on /tmp"

########################################
# 1) Runtime mount üzerinde noexec ekle
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

if echo "${mount_opts}" | grep -qw noexec; then
    echo "[INFO] noexec already present on /tmp runtime mount"
else
    new_opts="${mount_opts},noexec"
    echo "[ACTION] Remounting /tmp with options: ${new_opts}"
    if mount -o "remount,${new_opts}" "${TMP_DIR}"; then
        echo "[SUCCESS] /tmp remounted with noexec (runtime)"
    else
        echo "[ERROR] Failed to remount /tmp with noexec"
        # buradan direkt çıkmak mantıklı, fstab’i değiştirmeyip yarım bırakmak daha doğru
        exit 1
    fi
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
# 3) /etc/fstab içinde /tmp satırına noexec ekle
########################################

# Eğer /tmp için entry yoksa, bu kural ekleme yapmaz; uyarı verir.
if ! grep -Eq '^[[:space:]]*[^#[:space:]]+[[:space:]]+/tmp[[:space:]]+' "${FSTAB_FILE}"; then
    echo "[WARNING] /tmp not found in ${FSTAB_FILE}. Separate partition rule should create it."
    echo "[RESULT] Runtime noexec ok, fstab için upstream kural bekleniyor."
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

    # opsiyonları parçala, noexec olup olmadığına bak
    n = split($4, opts, ",")
    has_noexec = 0
    for (i = 1; i <= n; i++) {
        if (opts[i] == "noexec") {
            has_noexec = 1
        }
    }

    if (!has_noexec) {
        $4 = $4 ",noexec"
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

if echo "${final_opts}" | grep -qw noexec; then
    echo "[RESULT] PASS: /tmp has noexec (runtime) and /etc/fstab updated."
    exit 0
else
    echo "[RESULT] WARNING: /etc/fstab updated, but runtime options missing noexec."
    echo "         Reboot or remount required."
    exit 2
fi
