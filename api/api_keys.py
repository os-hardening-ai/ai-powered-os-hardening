"""
Partner (M2M) API anahtarı çözümü — kardeş ekip / sunucudan-sunucuya entegrasyon.

Kullanıcı-JWT'ye EK olarak, makine-makine çağrılar için hash'li API anahtarı sağlar.
Anahtarlar PARTNER_API_KEYS ortam değişkeninde tutulur (ayrı DB gerekmez):

    PARTNER_API_KEYS="label:<sha256(key)>:role,label2:<sha256(key2)>:role2"

Anahtar üretme:
    python -c "import secrets,hashlib;k=secrets.token_urlsafe(32);print(k, hashlib.sha256(k.encode()).hexdigest())"

Tasarım: anahtar düz metin saklanmaz (yalnız SHA-256); env her çağrıda okunur (test/yeniden
yükleme dostu, maliyet ≈ tek hash). İptal = env'den çıkar.
"""
from __future__ import annotations

import hashlib
import os
from typing import Optional

from api.auth_models import AuthenticatedUser, Role


def _parse_keys(raw: str) -> dict[str, tuple[str, Role]]:
    out: dict[str, tuple[str, Role]] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        bits = [b.strip() for b in part.split(":")]
        if len(bits) != 3:
            continue  # bozuk girdi sessizce atlanır
        label, key_hash, role = bits
        try:
            out[key_hash] = (label, Role.from_str(role))
        except ValueError:
            continue  # geçersiz rol → anahtar yüklenmez
    return out


def resolve_api_key(token: Optional[str]) -> Optional[AuthenticatedUser]:
    """Düz API anahtarını doğrula → partner servis-hesabı (AuthenticatedUser) veya None."""
    if not token:
        return None
    keys = _parse_keys(os.getenv("PARTNER_API_KEYS", ""))
    hit = keys.get(hashlib.sha256(token.encode()).hexdigest())
    if hit is None:
        return None
    label, role = hit
    return AuthenticatedUser(username=f"partner:{label}", role=role)
