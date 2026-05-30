"""
API key authentication (header-based).

Design (chosen approach):
- A single shared secret is read from the `API_KEY` environment variable.
- Clients send it in the `X-API-Key` header.
- If `API_KEY` is NOT configured, auth is DISABLED (development mode) and a
  one-time warning is logged — this avoids locking out the local/demo setup,
  while production simply sets `API_KEY` to turn protection on.
- Comparison is constant-time (`secrets.compare_digest`) to avoid timing leaks.

Apply as a FastAPI dependency on protected routers:
    app.include_router(chat_router, dependencies=[Depends(require_api_key)])

Health endpoints stay public so liveness/readiness probes keep working.
"""

from __future__ import annotations

import os
import secrets
from typing import Optional

from fastapi import Header

from api.errors import APIError, ErrorCode, ErrorType
from log_manager import get_logger

_logger = get_logger("api_auth")

API_KEY_ENV = "API_KEY"

_warned = False


def _expected_key() -> Optional[str]:
    """Configured API key, or None if auth is disabled (env unset/empty)."""
    key = (os.environ.get(API_KEY_ENV) or "").strip()
    return key or None


def auth_enabled() -> bool:
    return _expected_key() is not None


def _warn_disabled_once() -> None:
    global _warned
    if not _warned:
        _warned = True
        _logger.warning(
            "API auth DISABLED — '%s' env var not set. All endpoints are public. "
            "Set %s to require an X-API-Key header.",
            API_KEY_ENV, API_KEY_ENV,
        )


async def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    """FastAPI dependency: enforce the X-API-Key header when auth is configured."""
    expected = _expected_key()
    if expected is None:
        _warn_disabled_once()
        return  # dev mode — auth not configured
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise APIError(
            status_code=401,
            error_code=ErrorCode.UNAUTHORIZED,
            message="Missing or invalid API key. Provide a valid X-API-Key header.",
            error_type=ErrorType.AUTHENTICATION_ERROR,
            details=None,
        )
