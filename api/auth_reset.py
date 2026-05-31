"""
Parola sıfırlama token deposu (in-memory, TTL).

Tasarım (tez kapsamı — e-posta altyapısı yok):
- `POST /auth/forgot-password` bir tek-kullanımlık reset token üretir; DEV-mode'da
  doğrudan döner (test edilebilirlik), PROD'da e-posta ile gönderilir (SMTP gerekir).
- `POST /auth/reset-password` token + yeni parola ile sıfırlar; token tüketilir.

Token'lar süreç-içi dict'te tutulur (`jti -> (username, exp)`), TTL 15 dk, lazy temizlik.
Tek-instance demo için yeterli; çoklu-instance'ta Redis'e taşınmalı.
"""

from __future__ import annotations

import secrets
import time
from typing import Dict, Optional, Tuple

_TTL_SECONDS = 15 * 60
_store: Dict[str, Tuple[str, float]] = {}  # token -> (username, expires_at)


def _gc(now: float) -> None:
    if len(_store) > 256:
        for t, (_, exp) in list(_store.items()):
            if exp <= now:
                _store.pop(t, None)


def issue(username: str) -> str:
    """Kullanıcı için tek-kullanımlık reset token üret + sakla (TTL 15 dk)."""
    now = time.time()
    _gc(now)
    token = secrets.token_urlsafe(32)
    _store[token] = (username, now + _TTL_SECONDS)
    return token


def consume(token: str) -> Optional[str]:
    """Token geçerli + süresi dolmamışsa username döndürür (ve token'ı tüketir)."""
    rec = _store.pop(token, None)  # tek kullanımlık → her durumda çıkar
    if not rec:
        return None
    username, exp = rec
    if exp <= time.time():
        return None
    return username


def reset_for_tests() -> None:
    _store.clear()
