"""
SMTP e-posta gönderimi (smtplib + STARTTLS/SSL).

Env değişkenleri:
  SMTP_HOST   örn. smtp.gmail.com
  SMTP_PORT   587 (STARTTLS) veya 465 (SSL)
  SMTP_USER   gönderen hesap / SMTP kullanıcı adı
  SMTP_PASS   parola (Gmail için App Password)
  SMTP_FROM   görünen gönderen (yoksa SMTP_USER)

Tasarım: Bu modül yalnız "gönderim yeteneği"ni sağlar. Forgot-password'a bağlı DEĞİL
(kullanıcılarda email alanı yok). `scripts/send_test_email.py` ile test edilir.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

from log_manager import get_logger

_logger = get_logger("email_sender")

_REQUIRED = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS")


def smtp_configured() -> bool:
    """SMTP env değişkenlerinin hepsi ayarlı mı?"""
    return all(os.environ.get(k) for k in _REQUIRED)


def send_email(to: str, subject: str, body: str) -> None:
    """Düz-metin e-posta gönderir. Hata olursa exception fırlatır (çağıran yakalar)."""
    if not smtp_configured():
        raise RuntimeError(
            "SMTP ayarlı değil — gerekli env: " + ", ".join(_REQUIRED)
        )

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]
    sender = os.environ.get("SMTP_FROM", user)

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
            server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls(context=context)
            server.login(user, password)
            server.send_message(msg)

    _logger.info("e-posta gönderildi to=%s subject=%r", to, subject)


def send_reset_email(to: str, token: str) -> None:
    """Parola sıfırlama token'ını e-postayla gönderir (forgot-password akışı)."""
    body = (
        "Parola sıfırlama talebiniz alındı.\n\n"
        f"Sıfırlama token'ınız:\n{token}\n\n"
        "Uygulamadaki 'Parolamı unuttum' ekranında bu token'ı ve yeni parolanızı girin.\n"
        "Token 15 dakika geçerlidir. Bu talebi siz yapmadıysanız bu e-postayı yok sayın.\n"
    )
    send_email(to, "OS Hardening — Parola sıfırlama", body)
