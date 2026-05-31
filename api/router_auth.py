"""
Kimlik doğrulama uçları — /auth/login, /auth/logout, /auth/me.

- POST /auth/login  (PUBLIC): kullanıcı adı+parola → JWT access token.
- POST /auth/logout (auth)  : mevcut token'ın jti'sini blacklist'e alır.
- GET  /auth/me     (auth)  : mevcut kullanıcı bilgisi.

Login başarı/başarısızlığı ve logout, audit_log'a açık olay olarak yazılır.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request

from api import auth_reset
from api.email_sender import send_reset_email, smtp_configured
from api.audit import record_event
from api.auth import create_access_token, get_current_user, is_dev_mode
from api.auth_blacklist import block_token
from api.auth_models import (
    AuthenticatedUser,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    Role,
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


@router.post("/auth/register", response_model=TokenResponse, tags=["auth"])
async def register(payload: RegisterRequest, request: Request) -> TokenResponse:
    """Yeni kullanıcı kaydı (varsayılan rol: end_user) + otomatik giriş (token döner)."""
    ip = _client_ip(request)
    try:
        user_store.create(payload.username, payload.password, Role.END_USER, email=payload.email)
    except ValueError:
        await record_event(
            "register_failure", username=payload.username, endpoint="/auth/register",
            method="POST", status=409, ip=ip, detail="username exists",
        )
        raise APIError(
            status_code=409, error_code=ErrorCode.VALIDATION_ERROR,
            message="Bu kullanıcı adı zaten alınmış.", error_type=ErrorType.VALIDATION_ERROR,
        )
    user = AuthenticatedUser(username=payload.username, role=Role.END_USER)
    token, expires_in = create_access_token(user)
    await record_event(
        "register_success", username=payload.username, role="end_user",
        endpoint="/auth/register", method="POST", status=200, ip=ip,
    )
    return TokenResponse(access_token=token, token_type="bearer", role="end_user", expires_in=expires_in)


@router.post("/auth/forgot-password", response_model=ForgotPasswordResponse, tags=["auth"])
async def forgot_password(payload: ForgotPasswordRequest, request: Request) -> ForgotPasswordResponse:
    """Parola sıfırlama token'ı üretir. Kullanıcı enumeration'a karşı her durumda aynı mesaj döner;
    token yalnız kullanıcı VARSA üretilir ve DEV-mode'da yanıtta döner (prod'da e-posta — SMTP gerekir)."""
    ip = _client_ip(request)
    rec = user_store.get(payload.username)
    token = auth_reset.issue(payload.username) if rec else None
    email = (rec or {}).get("email")
    emailed = False
    if token and email and smtp_configured():
        try:
            await asyncio.to_thread(send_reset_email, email, token)
            emailed = True
        except Exception as exc:  # e-posta hatası akışı bozmasın
            _logger.warning("[forgot] reset e-postası gönderilemedi: %s", exc)
    await record_event(
        "forgot_password", username=payload.username, endpoint="/auth/forgot-password",
        method="POST", status=200, ip=ip,
        detail=("emailed" if emailed else "issued" if token else "unknown_user"),
    )
    # SMTP ile e-posta gittiyse token'ı yanıtta DÖNDÜRME (güvenlik).
    # E-posta gönderilemediyse (SMTP yok) ve dev-mode ise, akış çalışsın diye token'ı döndür.
    return ForgotPasswordResponse(
        message="Eğer bu hesap varsa, parola sıfırlama talimatları e-postayla gönderildi.",
        reset_token=(token if (token and not emailed and is_dev_mode()) else None),
    )


@router.post("/auth/reset-password", tags=["auth"])
async def reset_password(payload: ResetPasswordRequest, request: Request) -> dict:
    """Reset token + yeni parola ile parolayı sıfırlar (token tek kullanımlık)."""
    ip = _client_ip(request)
    username = auth_reset.consume(payload.token)
    if not username:
        await record_event(
            "reset_password_failure", endpoint="/auth/reset-password",
            method="POST", status=400, ip=ip, detail="invalid/expired token",
        )
        raise APIError(
            status_code=400, error_code=ErrorCode.VALIDATION_ERROR,
            message="Geçersiz veya süresi dolmuş sıfırlama token'ı.",
            error_type=ErrorType.VALIDATION_ERROR,
        )
    if not user_store.update_password(username, payload.new_password):
        raise APIError(
            status_code=404, error_code=ErrorCode.NOT_FOUND,
            message="Kullanıcı bulunamadı.", error_type=ErrorType.VALIDATION_ERROR,
        )
    await record_event(
        "reset_password_success", username=username, endpoint="/auth/reset-password",
        method="POST", status=200, ip=ip,
    )
    return {"message": "Parola güncellendi. Yeni parolayla giriş yapabilirsiniz."}


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
