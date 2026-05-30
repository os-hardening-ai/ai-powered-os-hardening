"""
Paylaşılan SQLite bağlantı katmanı — auth (users) + audit_log için.

Tasarım:
- Tek dosya (`config.auth.db_path`, vars. `data/auth.db`), tek paylaşılan bağlantı.
- WAL mode → eşzamanlı okuma + tek yazıcı (FastAPI thread-pool ile uyumlu).
- Yazımlar tek `threading.Lock` ile serileştirilir (sqlite tek-yazıcı modeli).
- `check_same_thread=False` → bağlantı thread'ler arası paylaşılır (audit middleware
  `asyncio.to_thread` içinden yazar; rota dependency'leri başka thread'de okur).

Şema burada `CREATE TABLE IF NOT EXISTS` ile garanti edilir (migration aracı yok —
tez kapsamı için yeterli; alan eklenince ALTER ile genişletilebilir).
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Optional

from log_manager import get_logger

_logger = get_logger("auth_db")

_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()
_db_path: Optional[str] = None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    username    TEXT,
    role        TEXT,
    action      TEXT NOT NULL,
    endpoint    TEXT,
    method      TEXT,
    status      INTEGER,
    ip          TEXT,
    request_id  TEXT,
    detail      TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_ts   ON audit_log(ts);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(username);
"""


def _resolve_db_path() -> str:
    try:
        from config.config_loader import get_config
        return get_config().auth.db_path
    except Exception:
        return "data/auth.db"


def init_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Bağlantıyı (idempotent) kur + şemayı garanti et. Singleton döndürür."""
    global _conn, _db_path
    with _lock:
        path = db_path or _resolve_db_path()
        # Aynı path için zaten açıksa tekrar kullan
        if _conn is not None and _db_path == path:
            return _conn
        # Farklı path istendi (örn. test) → eskiyi kapat
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
        except Exception as exc:  # bazı dosya sistemlerinde WAL desteklenmez
            _logger.warning("PRAGMA ayarlanamadı: %s", exc)
        conn.executescript(_SCHEMA)
        conn.commit()
        _conn, _db_path = conn, path
        _logger.info("SQLite hazır: %s", path)
        return conn


def get_conn() -> sqlite3.Connection:
    """Paylaşılan bağlantı (yoksa kur)."""
    if _conn is None:
        return init_db()
    return _conn


def write_lock() -> threading.Lock:
    """Yazımları serileştirmek için paylaşılan kilit (UserStore + AuditStore kullanır)."""
    return _lock


def reset_for_tests(db_path: str) -> sqlite3.Connection:
    """Testler için: bağlantıyı verilen path'e (örn. :memory: veya tmp dosya) yeniden kur."""
    global _conn, _db_path
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
        _conn, _db_path = None, None
    return init_db(db_path)
