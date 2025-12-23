# session_store.py
from __future__ import annotations

"""
Basit Session / Hafıza Yapısı
-----------------------------
Kullanıcıya ait önceki soru-cevap çiftlerini session_id bazında tutar.
Amaç:
- Aynı session_id ile gelen isteklerde son N turu history olarak kullanabilmek.
- Örn: history'den kısa bir özet üretip RequestContext.retrieved_context içine eklemek.

Bu yapı basit bir in-memory store'dur; prod ortamda Redis vb. ile değiştirilebilir.
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

    def get_history(self, session_id: str) -> List[Turn]:
        """
        Verilen session_id için son max_history adımı döndürür.
        """
        turns = self._sessions.get(session_id, [])
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
    ) -> None:
        """
        Yeni bir turn (mesaj) ekler.
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = []

        self._sessions[session_id].append(
            Turn(role=role, content=content, intent=intent, safety=safety)
        )

        # Max history sınırını koru (memory leak önlemi)
        if len(self._sessions[session_id]) > self.max_history * 4:
            self._sessions[session_id] = self._sessions[session_id][-self.max_history :]

    def reset_session(self, session_id: str) -> None:
        """
        Belirli bir session'ı sıfırlar.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]


# Opsiyonel global instance (küçük projeler / demo için)
global_session_store = SessionStore(max_history=5)
