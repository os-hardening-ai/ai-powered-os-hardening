"""
JWT tabanlı kimlik doğrulama + RBAC.

(Eski sürüm `X-API-Key` shared-secret kullanıyordu; kullanıcı kararıyla TAMAMEN JWT'ye
geçildi.)

Sağladıkları:
- `create_access_token(user)` / `decode_token(token)` — PyJWT (HS256), claim'ler:
  `sub` (kullanıcı adı), `role`, `jti` (logout/blacklist için), `iat`, `exp`.
- `bearer` — FastAPI HTTPBearer scheme (Swagger "Authorize" düğmesi).
- `get_current_user(...)` — Bearer JWT doğrula → `AuthenticatedUser`; hata → APIError 401.
  EventSource/SSE kolaylığı için `?access_token=` query fallback'i de kabul eder.
- `require_role(*allowed)` — RBAC dependency fabrikası; rol uymazsa APIError 403.
- `peek_username(request)` — best-effort (doğrulamadan) kullanıcı adı; rate-limit anahtarı için.
- `bootstrap_auth()` — DB init + dev/prod seeding (uygulama başlangıcında çağrılır).

Dev mode: `JWT_SECRET` ayarlı DEĞİLSE sabit dev-secret kullanılır + gürültülü uyarı +
4 demo hesap seed'lenir. Prod'da `JWT_SECRET` (>=32 karakter) zorunludur.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.auth_blacklist import is_blocked
from api.auth_models import ALL_ROLES, AuthenticatedUser, Role
from api.errors import APIError, ErrorCode, ErrorType
from log_manager import get_logger

_logger = get_logger("api_auth")

# Dev-mode sabit secret (yalnız JWT_SECRET ayarlı değilken). Sabit olması, dev'de
# sunucu yeniden başlasa bile mevcut token'ların/Swagger oturumunun çalışmasını sağlar.
_DEV_SECRET = "dev-insecure-jwt-secret-change-me-please-0123456789"

_warned_dev = False


def _cfg():
    from config.config_loader import get_config
    return get_config().auth


def is_dev_mode() -> bool:
    """JWT_SECRET ayarlı değilse True (dev). config.auth.jwt_secret env'den de gelebilir."""
    return not bool(_cfg().jwt_secret)


def _secret() -> str:
    global _warned_dev
    secret = _cfg().jwt_secret
    if secret:
        return secret
    if not _warned_dev:
        _warned_dev = True
        _logger.warning(
            "JWT_SECRET ayarlı DEĞİL — DEV MODE: sabit dev-secret + demo hesaplar kullanılıyor. "
            "Production'da JWT_SECRET (>=32 karakter) ayarlayın."
        )
    return _DEV_SECRET


def _algorithm() -> str:
    return _cfg().algorithm


def _expiry_minutes() -> int:
    return _cfg().access_token_expiry_minutes


# ── Token üretimi / çözümü ──────────────────────────────────────────────────────

def create_access_token(user: AuthenticatedUser) -> tuple[str, int]:
    """JWT üret. Döndürür: (token, expires_in_seconds)."""
    now = datetime.now(timezone.utc)
    expires_in = _expiry_minutes() * 60
    payload = {
        "sub": user.username,
        "role": user.role.value if isinstance(user.role, Role) else str(user.role),
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, _secret(), algorithm=_algorithm())
    return token, expires_in


def decode_token(token: str) -> dict:
    """JWT doğrula + çöz. Geçersiz/expired → APIError 401."""
    try:
        return jwt.decode(token, _secret(), algorithms=[_algorithm()])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token süresi doldu. Lütfen tekrar giriş yapın.")
    except jwt.InvalidTokenError:
        raise _unauthorized("Geçersiz token.")


def _unauthorized(message: str) -> APIError:
    return APIError(
        status_code=401,
        error_code=ErrorCode.UNAUTHORIZED,
        message=message,
        error_type=ErrorType.AUTHENTICATION_ERROR,
    )


# ── FastAPI dependency'leri ─────────────────────────────────────────────────────

# auto_error=False → header yoksa kendi 401'imizi (FastAPI'nin 403'ü yerine) atarız.
bearer = HTTPBearer(auto_error=False, description="JWT access token (Bearer)")


def _extract_token(request: Request, creds: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    if creds and creds.scheme.lower() == "bearer" and creds.credentials:
        return creds.credentials
    # EventSource/SSE: Authorization header gönderemez → query fallback (loglar path-only).
    qp = request.query_params.get("access_token")
    return qp or None


async def get_current_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> AuthenticatedUser:
    """Korumalı rotalar için: geçerli JWT → AuthenticatedUser. Aksi halde 401."""
    token = _extract_token(request, creds)
    if not token:
        raise _unauthorized("Kimlik doğrulama gerekli: 'Authorization: Bearer <token>'.")

    # Partner (M2M) API anahtarı — JWT'den önce dene (sunucudan-sunucuya servis hesabı).
    from api.api_keys import resolve_api_key
    svc_user = resolve_api_key(token)
    if svc_user is not None:
        request.state.user = svc_user
        return svc_user

    payload = decode_token(token)

    jti = payload.get("jti")
    if is_blocked(jti):
        raise _unauthorized("Token iptal edilmiş (çıkış yapılmış).")

    username = payload.get("sub")
    role_val = payload.get("role")
    if not username or role_val not in ALL_ROLES:
        raise _unauthorized("Token içeriği geçersiz.")

    user = AuthenticatedUser(username=username, role=Role.from_str(role_val))
    # Sonraki middleware/loglar için kimliği request.state'e koy (rate-limit, audit).
    request.state.user = user
    request.state.jwt_jti = jti
    request.state.jwt_exp = payload.get("exp")
    return user


def require_role(*allowed: Role):
    """RBAC dependency fabrikası. Kullanım:
        dependencies=[Depends(require_role(Role.SYSADMIN, Role.SECURITY))]
    """
    allowed_vals = {r.value if isinstance(r, Role) else str(r) for r in allowed}

    async def _checker(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role.value not in allowed_vals:
            raise APIError(
                status_code=403,
                error_code=ErrorCode.FORBIDDEN,
                message=f"Bu işlem için yetersiz yetki. Gerekli rol: {sorted(allowed_vals)}.",
                error_type=ErrorType.VALIDATION_ERROR,
                details={"your_role": user.role.value, "required": sorted(allowed_vals)},
            )
        return user

    return _checker


def peek_username(request: Request) -> Optional[str]:
    """Best-effort kullanıcı adı (rate-limit anahtarı için middleware'de kullanılır).

    Header VEYA query token'ı doğrular; başarısızsa None (sessiz). request.state'te
    zaten çözülmüş kimlik varsa onu kullanır (çift-decode'dan kaçınır).
    """
    user = getattr(request.state, "user", None)
    if user is not None:
        return getattr(user, "username", None)
    try:
        auth = request.headers.get("authorization", "")
        token = None
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        if not token:
            token = request.query_params.get("access_token")
        if not token:
            return None
        payload = jwt.decode(token, _secret(), algorithms=[_algorithm()])
        if is_blocked(payload.get("jti")):
            return None
        return payload.get("sub")
    except Exception:
        return None


# ── Başlangıç (DB init + seeding) ───────────────────────────────────────────────

def bootstrap_auth() -> None:
    """Uygulama başlangıcında: DB'yi kur + (boşsa) hesapları seed'le.

    Dev'de seed'lenen demo hesapların parolaları loglanır (yalnız dev kolaylığı).
    """
    from api.db import init_db
    from api.auth_store import user_store

    init_db()
    dev = is_dev_mode()
    if dev:
        _secret()  # dev uyarısını bir kez tetikle
    created = user_store.seed_defaults(dev_mode=dev)
    if created:
        if dev:
            lines = ", ".join(f"{u}/{p} ({r})" for u, p, r in created)
            _logger.warning("[seed] DEV demo hesapları oluşturuldu: %s", lines)
            print(f"[AUTH][DEV] Demo hesaplar: {lines}")
        else:
            for u, p, r in created:
                _logger.warning("[seed] Hesap oluşturuldu username=%s role=%s (parola tek-sefer)", u, r)
                print(f"[AUTH] Oluşturulan hesap: {u} ({r}) — parola: {p}")
