"""
Kimlik doğrulama uçları — /auth/login, /auth/logout, /auth/me.

- POST /auth/login  (PUBLIC): kullanıcı adı+parola → JWT access token.
- POST /auth/logout (auth)  : mevcut token'ın jti'sini blacklist'e alır.
- GET  /auth/me     (auth)  : mevcut kullanıcı bilgisi.

Login başarı/başarısızlığı ve logout, audit_log'a açık olay olarak yazılır.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.audit import record_event
from api.auth import create_access_token, get_current_user
from api.auth_blacklist import block_token
from api.auth_models import (
    AuthenticatedUser,
    LoginRequest,
    TokenResponse,
    UserOut,
)
from api.auth_store import user_store
from api.errors import APIError, ErrorCode, ErrorType
from log_manager import get_logger

router = APIRouter()
_logger = get_logger("api_auth")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/auth/login", response_model=TokenResponse, tags=["auth"])
async def login(payload: LoginRequest, request: Request) -> TokenResponse:
    """Kullanıcı adı + parola doğrula → JWT access token üret."""
    ip = _client_ip(request)
    role = user_store.verify_credentials(payload.username, payload.password)
    if role is None:
        await record_event(
            "login_failure",
            username=payload.username,
            endpoint="/auth/login",
            method="POST",
            status=401,
            ip=ip,
            detail="invalid credentials",
        )
        raise APIError(
            status_code=401,
            error_code=ErrorCode.UNAUTHORIZED,
            message="Kullanıcı adı veya parola hatalı.",
            error_type=ErrorType.AUTHENTICATION_ERROR,
        )

    user = AuthenticatedUser(username=payload.username, role=role)
    token, expires_in = create_access_token(user)
    await record_event(
        "login_success",
        username=user.username,
        role=role.value,
        endpoint="/auth/login",
        method="POST",
        status=200,
        ip=ip,
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=role.value,
        expires_in=expires_in,
    )


@router.post("/auth/logout", tags=["auth"])
async def logout(request: Request, user: AuthenticatedUser = Depends(get_current_user)) -> dict:
    """Mevcut token'ı iptal et (jti blacklist). Token doğal süresine kadar engellenir."""
    jti = getattr(request.state, "jwt_jti", None)
    exp = getattr(request.state, "jwt_exp", None)
    if jti and exp:
        block_token(jti, float(exp))
    await record_event(
        "logout",
        username=user.username,
        role=user.role.value,
        endpoint="/auth/logout",
        method="POST",
        status=200,
        ip=_client_ip(request),
    )
    return {"message": "Çıkış yapıldı. Token iptal edildi."}


@router.get("/auth/me", response_model=UserOut, tags=["auth"])
async def me(user: AuthenticatedUser = Depends(get_current_user)) -> UserOut:
    """Mevcut kimliği döndürür."""
    return UserOut(username=user.username, role=user.role.value)
