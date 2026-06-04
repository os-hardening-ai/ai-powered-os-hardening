from __future__ import annotations
import json
import logging
from typing import List, Optional

from llm.core.session_store import RoleType, Turn

_logger = logging.getLogger(__name__)


class RedisSessionStore:
    """
    Redis-backed session store — drop-in replacement for SessionStore.
    Falls back silently if Redis is unreachable; in that case all ops are no-ops
    and get_history() always returns [].
    """

    def __init__(self, url: str, ttl_seconds: int = 3600, max_history: int = 10) -> None:
        self._ttl = ttl_seconds
        self._max_history = max_history
        self._client = None
        try:
            import redis as _redis
            c = _redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
            c.ping()
            self._client = c
            _logger.info("[RedisSessionStore] Connected: %s", url)
        except Exception as exc:
            _logger.warning("[RedisSessionStore] Unavailable — sessions not persisted: %s", exc)

    @property
    def available(self) -> bool:
        return self._client is not None

    def _key(self, session_id: str, owner: Optional[str] = None) -> str:
        # owner ile namespace → kullanıcı izolasyonu (eskiden global "session:{id}" idi).
        o = (owner or "").strip() or "anon"
        return f"session:{o}:{session_id}"

    def get_history(self, session_id: str, *, owner: Optional[str] = None) -> List[Turn]:
        if not session_id or self._client is None:
            return []
        try:
            raw = self._client.lrange(self._key(session_id, owner), -(self._max_history * 2), -1)
            return [
                Turn(
                    role=d["role"],
                    content=d["content"],
                    intent=d.get("intent"),
                    safety=d.get("safety"),
                )
                for d in (json.loads(x) for x in raw)
            ]
        except Exception as exc:
            _logger.warning("[RedisSessionStore] get_history error: %s", exc)
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
        if not session_id or self._client is None:
            return
        try:
            key = self._key(session_id, owner)
            payload = json.dumps(
                {"role": role, "content": content, "intent": intent, "safety": safety}
            )
            self._client.rpush(key, payload)
            self._client.expire(key, self._ttl)
            self._client.ltrim(key, -(self._max_history * 4), -1)
        except Exception as exc:
            _logger.warning("[RedisSessionStore] add_turn error: %s", exc)

    def reset_session(self, session_id: str, *, owner: Optional[str] = None) -> None:
        if not session_id or self._client is None:
            return
        try:
            self._client.delete(self._key(session_id, owner))
        except Exception as exc:
            _logger.warning("[RedisSessionStore] reset_session error: %s", exc)
