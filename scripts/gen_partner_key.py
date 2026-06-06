#!/usr/bin/env python3
"""Partner API anahtarı üretici — API paylaşım sürecini standartlaştırır.

Kullanım:
    python scripts/gen_partner_key.py <label> [role]
        role: end_user | developer | security | sysadmin   (varsayılan: security)

Çıktı:
    [1] KEY  — kardeş ekibe GÜVENLİ kanaldan verilecek düz anahtar (Authorization: Bearer <KEY>)
    [2] .env — PARTNER_API_KEYS'e eklenecek satır (yalnız SHA-256 HASH saklanır; düz anahtar DEĞİL)

Güvenlik: düz anahtar yalnız bu çıktıda görünür, bir daha üretilemez/saklanmaz. .env'e HASH gider.
"""
import hashlib
import secrets
import sys

VALID_ROLES = {"end_user", "developer", "security", "sysadmin"}
DOMAIN = "hardeningai.site"


def main() -> int:
    if len(sys.argv) < 2:
        print("Kullanım: python scripts/gen_partner_key.py <label> [role]")
        print(f"  role (varsayılan: security): {sorted(VALID_ROLES)}")
        return 1

    label = sys.argv[1].strip()
    role = sys.argv[2].strip() if len(sys.argv) > 2 else "security"

    if role not in VALID_ROLES:
        print(f"Geçersiz rol: {role!r}. Geçerli: {sorted(VALID_ROLES)}")
        return 1
    if ":" in label or "," in label or not label:
        print("label boş olamaz ve ':' / ',' içeremez (PARTNER_API_KEYS ayracı).")
        return 1

    key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(key.encode()).hexdigest()

    print("=" * 72)
    print(f"  Partner: {label}     Rol: {role}")
    print("=" * 72)
    print("\n[1] KEY — kardeş ekibe GÜVENLİ kanaldan ver (bir daha gösterilmez):")
    print(f"    {key}")
    print("\n[2] Sunucuda .env içine EKLE (yalnız HASH saklanır):")
    print(f"    PARTNER_API_KEYS={label}:{key_hash}:{role}")
    print("    (Birden çok partner varsa mevcut değere VİRGÜLLE ekle.)")
    print("\n[3] Uygula (kod + env):")
    print("    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build api")
    print("\n[4] Doğrula:")
    print(f'    curl https://{DOMAIN}/auth/me -H "Authorization: Bearer {key}"')
    print(f'    # beklenen: {{"username":"partner:{label}","role":"{role}"}}')
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
