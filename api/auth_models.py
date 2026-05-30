"""
Auth veri modelleri — roller, kimlik nesnesi ve API şemaları.

Roller öneri formundan birebir: sysadmin / security / developer / end_user.
RBAC kontrolü `api.auth.require_role(...)` tarafından bu enum üzerinden yapılır.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field


class Role(str, Enum):
    """Sistem rolleri (öneri formu)."""
    SYSADMIN = "sysadmin"      # tam yetki (süper kullanıcı)
    SECURITY = "security"      # güvenlik analisti — sıkılaştırma + denetim
    DEVELOPER = "developer"    # geliştirici — plan + artifact üretimi
    END_USER = "end_user"      # son kullanıcı — yalnız sohbet/okuma

    @classmethod
    def from_str(cls, value: str) -> "Role":
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Geçersiz rol: {value!r}. Geçerli: {[r.value for r in cls]}")


# Tüm geçerli rol değerleri (hızlı doğrulama için)
ALL_ROLES = frozenset(r.value for r in Role)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Doğrulanmış JWT'den çözülen kimlik. Rota dependency'lerinde kullanılır."""
    username: str
    role: Role


# ── API şemaları ──────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, examples=["admin"])
    password: str = Field(..., min_length=1, max_length=256, examples=["changeme123"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    expires_in: int = Field(..., description="Token geçerlilik süresi (saniye)")


class UserOut(BaseModel):
    username: str
    role: str
