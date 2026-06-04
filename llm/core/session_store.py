# session_store.py
from __future__ import annotations

"""
Basit Session / Hafıza Yapısı
-----------------------------
Kullanıcıya ait önceki soru-cevap çiftlerini session_id bazında tutar.
Amaç:
- Aynı session_id ile gelen isteklerde son N turu history olarak kullanabilmek.
- Örn: history'den kısa bir özet üretip RequestContext.retrieved_context içine eklemek.

Bu yapı basit bir in-memory store'dur. Production için redis_session_store.py kullanılır;
router_chat.py startup'ta Redis'e bağlanmayı dener, başarısız olursa bu sınıfa fallback yapar.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional


RoleType = Literal["user", "assistant"]


@dataclass
class Turn:
    """
    Tek bir sohbet turu (user + assistant mesajı) için minimal kayıt.
    Gerekirse intent, safety vb. alanlar eklenebilir.
    """
    role: RoleType
    content: str
    intent: Optional[str] = None
    safety: Optional[str] = None


@dataclass
class SessionStore:
    """
    In-memory session store.

    Kullanım:
        store = SessionStore(max_history=5)
        store.add_turn("session-123", "user", "ssh'yi nasıl güvenli hale getiririm?", intent="os_hardening")
        store.add_turn("session-123", "assistant", "Önce port ayarlarından başlayalım...", intent="os_hardening")

        history = store.get_history("session-123")
    """
    max_history: int = 5
    _sessions: Dict[str, List[Turn]] = field(default_factory=dict)

    @staticmethod
    def _scoped(session_id: str, owner: Optional[str]) -> str:
        """Owner verilirse anahtarı namespace'le → kullanıcı izolasyonu. Owner yoksa
        DÜZ session_id (geriye dönük uyum — owner geçmeyen eski çağrılar aynı davranır)."""
        o = (owner or "").strip()
        return f"{o}\x1f{session_id}" if o else session_id

    def get_history(self, session_id: str, *, owner: Optional[str] = None) -> List[Turn]:
        """
        Verilen (owner, session_id) için son max_history adımı döndürür.
        """
        turns = self._sessions.get(self._scoped(session_id, owner), [])
        if len(turns) <= self.max_history:
            return list(turns)
        return turns[-self.max_history :]

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
        """
        Yeni bir turn (mesaj) ekler.
        """
        key = self._scoped(session_id, owner)
        if key not in self._sessions:
            self._sessions[key] = []

        self._sessions[key].append(
            Turn(role=role, content=content, intent=intent, safety=safety)
        )

        # Max history sınırını koru (memory leak önlemi)
        if len(self._sessions[key]) > self.max_history * 4:
            self._sessions[key] = self._sessions[key][-self.max_history :]

    def reset_session(self, session_id: str, *, owner: Optional[str] = None) -> None:
        """
        Belirli bir (owner, session_id) session'ını sıfırlar.
        """
        key = self._scoped(session_id, owner)
        if key in self._sessions:
            del self._sessions[key]


# Opsiyonel global instance (küçük projeler / demo için)
global_session_store = SessionStore(max_history=5)
