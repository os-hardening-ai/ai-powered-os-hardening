"""
Kullanıcı deposu — SQLite `users` tablosu + bcrypt parola hash.

Sorumluluklar:
- create / get / verify_credentials (sabit-zamanlı bcrypt karşılaştırması).
- seed_defaults: tablo boşsa başlangıç hesapları oluştur (idempotent).

Parola asla düz metin saklanmaz; yalnızca bcrypt hash (`password_hash`).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import bcrypt

from api.auth_models import Role
from api.db import get_conn, write_lock
from log_manager import get_logger

_logger = get_logger("auth_store")

# bcrypt parola girdisi en fazla 72 bayt işler (4.x üstü fazlasında hata verir) → kırp.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(pw, password_hash.encode("utf-8"))
    except Exception:
        return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserStore:
    """`users` tablosu üzerinde ince bir sarmalayıcı."""

    def get(self, username: str) -> Optional[dict]:
        row = get_conn().execute(
            "SELECT username, password_hash, role, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return dict(row) if row else None

    def exists(self, username: str) -> bool:
        return self.get(username) is not None

    def count(self) -> int:
        return int(get_conn().execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"])

    def create(self, username: str, password: str, role: Role) -> None:
        """Yeni kullanıcı ekle. Aynı username varsa ValueError."""
        role_val = role.value if isinstance(role, Role) else Role.from_str(role).value
        with write_lock():
            conn = get_conn()
            exists = conn.execute(
                "SELECT 1 FROM users WHERE username = ?", (username,)
            ).fetchone()
            if exists:
                raise ValueError(f"Kullanıcı zaten var: {username!r}")
            conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                (username, hash_password(password), role_val, _now_iso()),
            )
            conn.commit()
        _logger.info("user created username=%s role=%s", username, role_val)

    def verify_credentials(self, username: str, password: str) -> Optional[Role]:
        """Kullanıcı adı + parola doğruysa Role döndürür, yoksa None."""
        rec = self.get(username)
        if not rec:
            # kullanıcı yoksa bile bcrypt çağrısı yap (zamanlama sızıntısını azalt)
            verify_password(password, "$2b$12$" + "x" * 53)
            return None
        if not verify_password(password, rec["password_hash"]):
            return None
        try:
            return Role.from_str(rec["role"])
        except ValueError:
            _logger.warning("Geçersiz rol DB'de: username=%s role=%s", username, rec["role"])
            return None

    def list_users(self) -> List[dict]:
        rows = get_conn().execute(
            "SELECT username, role, created_at FROM users ORDER BY username"
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Seeding ────────────────────────────────────────────────────────────────

    def seed_defaults(self, dev_mode: bool) -> List[Tuple[str, str, str]]:
        """Tablo boşsa başlangıç hesaplarını oluştur (idempotent).

        dev_mode=True  → 4 demo hesap (her rol), parola AUTH_DEMO_PASSWORD veya 'changeme123'.
        dev_mode=False → yalnız 'admin' (sysadmin), parola AUTH_ADMIN_PASSWORD; yoksa rastgele.

        Döndürür: yeni oluşturulan (username, password, role) listesi (log/print için).
        Var olan kullanıcılar dokunulmaz; parolalar yalnız oluşturma anında bilinir.
        """
        if self.count() > 0:
            return []

        created: List[Tuple[str, str, str]] = []
        if dev_mode:
            demo_pw = os.environ.get("AUTH_DEMO_PASSWORD", "changeme123")
            seeds = [
                ("admin", demo_pw, Role.SYSADMIN),
                ("sec", demo_pw, Role.SECURITY),
                ("dev", demo_pw, Role.DEVELOPER),
                ("user", demo_pw, Role.END_USER),
            ]
        else:
            admin_pw = os.environ.get("AUTH_ADMIN_PASSWORD", "").strip()
            if not admin_pw:
                import secrets
                admin_pw = secrets.token_urlsafe(16)
            seeds = [("admin", admin_pw, Role.SYSADMIN)]

        for username, password, role in seeds:
            try:
                self.create(username, password, role)
                created.append((username, password, role.value))
            except ValueError:
                pass  # yarış durumu — zaten var
        return created


# Modül-düzeyi singleton (durumsuz; bağlantıyı api.db yönetir)
user_store = UserStore()
