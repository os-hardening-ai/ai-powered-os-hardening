"""İletişim formu — public POST /api/contact → öneri/görüş ekibe e-posta ile iletilir.

SMTP env (yoksa mesaj yalnız loglanır, istek yine 200 döner — dev kolaylığı):
  SMTP_HOST (vars. "smtp.gmail.com:587"), SMTP_USER, SMTP_PASS, CONTACT_TO (vars. SMTP_USER)
Ek bağımlılık yok (stdlib smtplib + hafif e-posta regex; email-validator gerekmez).
"""
from __future__ import annotations

import os
import re
import smtplib
import ssl
from email.message import EmailMessage

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from log_manager import get_logger

router = APIRouter()
_logger = get_logger("contact")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ContactRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: str = Field(..., min_length=5, max_length=120)
    subject: str = Field("oneri", max_length=32)
    message: str = Field(..., min_length=10, max_length=4000)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("Geçerli bir e-posta adresi girin.")
        return v


def _send_email(p: ContactRequest) -> bool:
    """SMTP yapılandırılmışsa e-posta gönderir; değilse False (çağıran loglar)."""
    user = os.getenv("SMTP_USER", "").strip()
    pwd = os.getenv("SMTP_PASS", "").strip()
    if not (user and pwd):
        return False
    host = os.getenv("SMTP_HOST", "smtp.gmail.com:587")
    hostname, _, port_s = host.partition(":")
    to_addr = os.getenv("CONTACT_TO", user)

    msg = EmailMessage()
    msg["Subject"] = f"[İletişim · {p.subject}] {p.name}"
    msg["From"] = user
    msg["To"] = to_addr
    msg["Reply-To"] = p.email
    msg.set_content(f"Ad: {p.name}\nE-posta: {p.email}\nKonu: {p.subject}\n\n{p.message}")

    ctx = ssl.create_default_context()
    with smtplib.SMTP(hostname, int(port_s or "587"), timeout=15) as s:
        s.starttls(context=ctx)
        s.login(user, pwd)
        s.send_message(msg)
    return True


@router.post("/contact", tags=["chat"])
async def submit_contact(payload: ContactRequest) -> dict:
    """Öneri/görüş formu — PUBLIC. Mesajı ekibe e-posta ile iletir (SMTP yoksa loglar)."""
    try:
        delivered = _send_email(payload)
    except Exception as exc:  # SMTP/ağ hatası → kullanıcıya nazik hata
        _logger.error("[contact] e-posta gönderilemedi: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Mesaj şu an iletilemedi, lütfen daha sonra tekrar deneyin.",
        )
    if delivered:
        _logger.info("[contact] iletildi: %s <%s> konu=%s", payload.name, payload.email, payload.subject)
    else:
        _logger.warning(
            "[contact] SMTP yok — mesaj loglandı: %s <%s> | %s",
            payload.name, payload.email, payload.message[:200],
        )
    return {"status": "ok", "delivered": delivered}
