"""
Audit log — "kim, ne zaman, ne yaptı" (öneri formu B5).

Bileşenler:
- `AuditStore` — SQLite `audit_log` tablosuna yazar/sorgular (yazım `api.db.write_lock` ile serileştirilir).
- `record_event(...)` — açık olay kaydı (login_success/login_failure/logout vb.).
- `AuditMiddleware` — her HTTP isteğini (gürültülü prob'lar hariç) otomatik kaydeder; kullanıcı
  kimliği rota dependency'si (`get_current_user`) tarafından `request.state.user`'a konmuş olur.
- `audit_router` — `GET /api/audit` (yalnız sysadmin/security) sorgulama ucu.

Yazım `asyncio.to_thread` ile yapılır (event-loop bloklanmaz); audit hatası asla isteği düşürmez.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from starlette.types import ASGIApp, Scope, Receive, Send, Message

from api.auth import require_role
from api.auth_models import Role
from api.db import get_conn, write_lock
from log_manager import get_logger

_logger = get_logger("audit")

# Otomatik kayıttan muaf (gürültü/sağlık prob'ları/dokümantasyon).
_SKIP_PREFIXES = (
    "/health", "/docs", "/redoc", "/openapi.json", "/favicon",
    "/metrics/prometheus",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditStore:
    def record(
        self,
        action: str,
        *,
        username: Optional[str] = None,
        role: Optional[str] = None,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        status: Optional[int] = None,
        ip: Optional[str] = None,
        request_id: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        try:
            with write_lock():
                conn = get_conn()
                conn.execute(
                    "INSERT INTO audit_log "
                    "(ts, username, role, action, endpoint, method, status, ip, request_id, detail) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (_now_iso(), username, role, action, endpoint, method, status, ip, request_id, detail),
                )
                conn.commit()
        except Exception as exc:  # audit asla isteği düşürmez
            _logger.warning("audit insert error: %s", exc)

    def query(
        self,
        limit: int = 50,
        username: Optional[str] = None,
        action: Optional[str] = None,
    ) -> List[dict]:
        limit = max(1, min(limit, 500))
        sql = ("SELECT ts, username, role, action, endpoint, method, status, ip, request_id, detail "
               "FROM audit_log")
        clauses, params = [], []
        if username:
            clauses.append("username = ?"); params.append(username)
        if action:
            clauses.append("action = ?"); params.append(action)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = get_conn().execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]


audit_store = AuditStore()


async def record_event(action: str, **kwargs) -> None:
    """Açık (manuel) audit olayı — login/logout vb. için. Bloklamaz."""
    await asyncio.to_thread(audit_store.record, action, **kwargs)


def _client_ip(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"


def _client_ip_from_scope(scope: Scope) -> str:
    client = scope.get("client")
    if client:
        return client[0]
    return "unknown"


class AuditMiddleware:
    """Her isteği audit_log'a yazar (gürültülü prob'lar hariç).

    Pure ASGI middleware — BaseHTTPMiddleware kullanmaz, bu nedenle SSE/streaming
    yanıtlarını tamponlamaz. Kayıt, final http.response.body sonrası yapılır.
    """

    def __init__(self, app: ASGIApp, enabled: bool = True) -> None:
        self.app = app
        self.enabled = enabled

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "")
        enabled = self.enabled
        status: list[int] = [0]

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status[0] = message.get("status", 0)
            elif message["type"] == "http.response.body" and not message.get("more_body", False):
                if enabled and not any(path.startswith(p) for p in _SKIP_PREFIXES):
                    state = scope.get("state") or {}
                    user = state.get("user")
                    username = getattr(user, "username", None) if user else None
                    role = user.role.value if user is not None else None
                    request_id = state.get("request_id")
                    try:
                        await asyncio.to_thread(
                            audit_store.record,
                            "request",
                            username=username,
                            role=role,
                            endpoint=path,
                            method=method,
                            status=status[0],
                            ip=_client_ip_from_scope(scope),
                            request_id=request_id,
                        )
                    except Exception as exc:
                        _logger.warning("audit middleware error: %s", exc)
            await send(message)

        await self.app(scope, receive, send_wrapper)


# ── Sorgulama ucu ───────────────────────────────────────────────────────────────

audit_router = APIRouter()


@audit_router.get(
    "/audit",
    tags=["monitoring"],
    dependencies=[Depends(require_role(Role.SYSADMIN, Role.SECURITY))],
)
async def get_audit_log(limit: int = 50, user: Optional[str] = None, action: Optional[str] = None):
    """Audit kayıtlarını sorgula (en yeni önce). Yalnız sysadmin/security."""
    rows = await asyncio.to_thread(audit_store.query, limit, user, action)
    return {"count": len(rows), "events": rows}
