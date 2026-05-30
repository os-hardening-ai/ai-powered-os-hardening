"""
JWT token blacklist (logout) — `jti` bazlı.

JWT stateless'tır; logout için iptal edilen token'ın `jti`'sini, token'ın doğal
son kullanma anına kadar bir kara listede tutarız. Sonraki isteklerde
`get_current_user` bu listeyi kontrol eder.

Depolama: Redis (`SETEX blacklist:{jti} <kalan-saniye> 1`) — varsa; yoksa süreç-içi
in-memory dict (`jti -> exp_epoch`, tembel temizlik). Bağlantı deseni projedeki
canonical `redis.from_url(url, socket_connect_timeout=2)` + ping ile aynıdır.

Erişilebilirlik politikası: `is_blocked` Redis hatasında FAIL-OPEN döner (token
zaten exp ile düşeceği için risk sınırlı) — kesinti tüm API'yi kilitlemesin.
"""

from __future__ import annotations

import os
import time
from typing import Dict, Optional

from log_manager import get_logger

_logger = get_logger("auth_blacklist")

_PREFIX = "blacklist:"


class _RedisBlacklist:
    def __init__(self, client) -> None:
        self.client = client

    def block(self, jti: str, ttl_seconds: int) -> None:
        try:
            if ttl_seconds > 0:
                self.client.setex(_PREFIX + jti, ttl_seconds, "1")
        except Exception as exc:
            _logger.warning("[blacklist] Redis block error: %s", exc)

    def is_blocked(self, jti: str) -> bool:
        try:
            return self.client.exists(_PREFIX + jti) == 1
        except Exception as exc:  # fail-open
            _logger.warning("[blacklist] Redis read error (fail-open): %s", exc)
            return False


class _InMemoryBlacklist:
    def __init__(self) -> None:
        self._d: Dict[str, float] = {}

    def _gc(self, now: float) -> None:
        if len(self._d) > 256:
            for k, exp in list(self._d.items()):
                if exp <= now:
                    self._d.pop(k, None)

    def block(self, jti: str, ttl_seconds: int) -> None:
        now = time.time()
        self._gc(now)
        self._d[jti] = now + max(ttl_seconds, 0)

    def is_blocked(self, jti: str) -> bool:
        exp = self._d.get(jti)
        if exp is None:
            return False
        if exp <= time.time():
            self._d.pop(jti, None)
            return False
        return True


_backend = None


def _build_backend():
    url = os.environ.get("REDIS_URL")
    if not url:
        try:
            from config.config_loader import get_config
            url = get_config().redis.url
        except Exception:
            url = None
    if url:
        try:
            import redis as _redis
            c = _redis.from_url(url, socket_connect_timeout=2)
            c.ping()
            _logger.info("[blacklist] Redis-backed: %s", url)
            return _RedisBlacklist(c)
        except Exception as exc:
            _logger.warning("[blacklist] Redis yok, in-memory fallback: %s", exc)
    return _InMemoryBlacklist()


def _get_backend():
    global _backend
    if _backend is None:
        _backend = _build_backend()
    return _backend


def block_token(jti: str, expires_at_epoch: float) -> None:
    """Token'ı kalan süresi kadar kara listeye al."""
    if not jti:
        return
    ttl = int(expires_at_epoch - time.time())
    _get_backend().block(jti, max(ttl, 1))


def is_blocked(jti: Optional[str]) -> bool:
    if not jti:
        return False
    return _get_backend().is_blocked(jti)


def reset_for_tests() -> None:
    """Testler için backend'i sıfırla (in-memory'ye düşer veya yeniden kurulur)."""
    global _backend
    _backend = None
