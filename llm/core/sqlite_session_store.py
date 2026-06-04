from __future__ import annotations

"""
SQLite-backed, KULLANICI BAZLI chat history store.
----------------------------------------------------
Eski durum: history Redis'te global `session:{session_id}` altında tutuluyordu →
kullanıcı ayrımı YOKTU; aynı session_id'yi kullanan (veya frontend sabit session_id
gönderen) herkes birbirinin geçmişini görüyordu (gizlilik açığı).

Bu store geçmişi `data/auth.db` içinde `chat_history` tablosunda **(owner, session_id)**
çiftiyle izole eder ve KALICI tutar (restart'ta kaybolmaz; Redis'in 1 saatlik TTL'i yoktu).

- owner = JWT kullanıcı adı (api.auth.peek_username) veya kimliksizse "anon".
- Drop-in: SessionStore/RedisSessionStore ile aynı `get_history`/`add_turn`/`reset_session`
  arayüzü (owner KEYWORD parametresi, default "anon") → router'da minimal değişiklik.
- Ek (GET API için): list_sessions / get_turns / delete_session.
- Otomatik temizleme: cleanup(retention_days) → eski turları siler (DB şişmesi + gizlilik).

Yazımlar api.db'nin paylaşılan bağlantısı + write_lock'u ile serileştirilir (sqlite
tek-yazıcı modeli; auth/audit ile aynı desen).
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from llm.core.session_store import RoleType, Turn

_logger = logging.getLogger(__name__)

_ANON = "anon"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteSessionStore:
    """SQLite tabanlı, kullanıcı-izole, kalıcı chat history store."""

    def __init__(self, max_history: int = 10) -> None:
        self._max_history = max_history
        self._ready = False
        try:
            from api.db import get_conn
            # get_conn(): mevcut paylaşılan bağlantıyı KORUR (bootstrap_auth ya da testlerin
            # reset_for_tests'i kurmuşsa onu kullanır); yoksa default path'te lazy init eder.
            # init_db() çağırmak test bağlantısını ezerdi → get_conn doğru olanı seçer.
            get_conn()
            self._ready = True
            _logger.info("[SqliteSessionStore] hazır (data/auth.db · chat_history)")
        except Exception as exc:
            _logger.warning("[SqliteSessionStore] kurulamadı — history kalıcı değil: %s", exc)

    @property
    def available(self) -> bool:
        return self._ready

    @staticmethod
    def _owner(owner: Optional[str]) -> str:
        o = (owner or "").strip()
        return o or _ANON

    # ── Legacy arayüz (SessionStore/Redis ile uyumlu) ───────────────────────────

    def get_history(self, session_id: str, *, owner: Optional[str] = None) -> List[Turn]:
        """Bu (owner, session_id) için SON max_history turu döndürür (bağlam penceresi)."""
        if not session_id or not self._ready:
            return []
        try:
            from api.db import get_conn
            rows = get_conn().execute(
                "SELECT role, content, intent, safety FROM chat_history "
                "WHERE owner = ? AND session_id = ? ORDER BY id DESC LIMIT ?",
                (self._owner(owner), session_id, self._max_history * 2),
            ).fetchall()
            # DESC çektik → kronolojik sıraya çevir
            return [
                Turn(role=r["role"], content=r["content"], intent=r["intent"], safety=r["safety"])
                for r in reversed(rows)
            ]
        except Exception as exc:
            _logger.warning("[SqliteSessionStore] get_history error: %s", exc)
            return []

    def add_turn(
        self,
        session_id: str,
        role: RoleType,
        content: str,
        intent: Optional[str] = None,
        safety: Optional[str] = None,
        *,
        owner: Optional[str] = None,
    ) -> None:
        """Yeni turu ANINDA kalıcı yazar (soru/cevap geldiği an history'ye eklenir)."""
        if not session_id or not self._ready:
            return
        try:
            from api.db import get_conn, write_lock
            with write_lock():
                conn = get_conn()
                conn.execute(
                    "INSERT INTO chat_history (owner, session_id, role, content, intent, safety, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (self._owner(owner), session_id, role, content, intent, safety, _now_iso()),
                )
                conn.commit()
        except Exception as exc:
            _logger.warning("[SqliteSessionStore] add_turn error: %s", exc)

    def reset_session(self, session_id: str, *, owner: Optional[str] = None) -> None:
        self.delete_session(self._owner(owner), session_id)

    # ── GET API (kullanıcıya kendi geçmişini göstermek için) ────────────────────

    def list_sessions(self, owner: str) -> List[dict]:
        """Kullanıcının oturumları — her biri için son mesaj + zaman + tur sayısı (yeni→eski)."""
        if not self._ready:
            return []
        try:
            from api.db import get_conn
            rows = get_conn().execute(
                """
                SELECT session_id,
                       COUNT(*)        AS turn_count,
                       MAX(created_at) AS last_ts,
                       MAX(id)         AS last_id
                FROM chat_history
                WHERE owner = ?
                GROUP BY session_id
                ORDER BY last_id DESC
                """,
                (self._owner(owner),),
            ).fetchall()
            out: List[dict] = []
            conn = get_conn()
            for r in rows:
                last = conn.execute(
                    "SELECT content FROM chat_history WHERE owner = ? AND session_id = ? "
                    "ORDER BY id DESC LIMIT 1",
                    (self._owner(owner), r["session_id"]),
                ).fetchone()
                out.append({
                    "session_id": r["session_id"],
                    "turn_count": r["turn_count"],
                    "last_ts": r["last_ts"],
                    "last_message": (last["content"][:120] if last else ""),
                })
            return out
        except Exception as exc:
            _logger.warning("[SqliteSessionStore] list_sessions error: %s", exc)
            return []

    def get_turns(self, owner: str, session_id: str) -> List[dict]:
        """Bir oturumun TÜM turları (kronolojik) — sadece sahibi içindir (owner filtreli)."""
        if not self._ready or not session_id:
            return []
        try:
            from api.db import get_conn
            rows = get_conn().execute(
                "SELECT role, content, intent, created_at FROM chat_history "
                "WHERE owner = ? AND session_id = ? ORDER BY id ASC",
                (self._owner(owner), session_id),
            ).fetchall()
            return [
                {"role": r["role"], "content": r["content"], "intent": r["intent"], "ts": r["created_at"]}
                for r in rows
            ]
        except Exception as exc:
            _logger.warning("[SqliteSessionStore] get_turns error: %s", exc)
            return []

    def delete_session(self, owner: str, session_id: str) -> int:
        """Kullanıcının bir oturumunu siler. Silinen tur sayısını döndürür."""
        if not self._ready or not session_id:
            return 0
        try:
            from api.db import get_conn, write_lock
            with write_lock():
                conn = get_conn()
                cur = conn.execute(
                    "DELETE FROM chat_history WHERE owner = ? AND session_id = ?",
                    (self._owner(owner), session_id),
                )
                conn.commit()
                return cur.rowcount or 0
        except Exception as exc:
            _logger.warning("[SqliteSessionStore] delete_session error: %s", exc)
            return 0

    # ── Otomatik temizleme ──────────────────────────────────────────────────────

    def cleanup(self, retention_days: int) -> int:
        """retention_days'ten eski turları siler (DB şişmesi + gizlilik). Silinen sayı döner.
        retention_days <= 0 ise temizleme yapılmaz (süresiz saklama)."""
        if not self._ready or retention_days is None or retention_days <= 0:
            return 0
        try:
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
            from api.db import get_conn, write_lock
            with write_lock():
                conn = get_conn()
                cur = conn.execute("DELETE FROM chat_history WHERE created_at < ?", (cutoff,))
                conn.commit()
                n = cur.rowcount or 0
            if n:
                _logger.info("[SqliteSessionStore] cleanup: %d eski tur silindi (>%dg)", n, retention_days)
            return n
        except Exception as exc:
            _logger.warning("[SqliteSessionStore] cleanup error: %s", exc)
            return 0
