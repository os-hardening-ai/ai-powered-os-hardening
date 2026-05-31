#!/usr/bin/env python
"""
SMTP test — sunucu gerçekten e-posta gönderebiliyor mu?

Kullanım (container içinde, .env'de SMTP_* ayarlıyken):
  python scripts/send_test_email.py alici@ornek.com

SMTP_* env değişkenleri yoksa açıkça uyarır. Forgot-password'ı etkilemez;
yalnız SMTP yapılandırmasını doğrular.
"""

import sys

from api.email_sender import send_email, smtp_configured


def main() -> int:
    if len(sys.argv) < 2:
        print("Kullanım: python scripts/send_test_email.py <alici-email>")
        return 2

    to = sys.argv[1]
    if not smtp_configured():
        print("HATA: SMTP env'leri ayarlı değil. .env'e ekle:")
        print("  SMTP_HOST=smtp.gmail.com")
        print("  SMTP_PORT=587")
        print("  SMTP_USER=<gmail-adresin>")
        print("  SMTP_PASS=<gmail app password>")
        print("  SMTP_FROM=<gmail-adresin>")
        return 1

    try:
        send_email(
            to,
            "OS Hardening — SMTP test",
            "Bu bir test e-postasidir. SMTP yapilandirmasi calisiyor. [OK]",
        )
        print(f"[OK] Test e-postasi gonderildi: {to}")
        return 0
    except Exception as exc:  # noqa: BLE001 — test aracı; tüm hatayı göster
        print(f"[HATA] Gonderim basarisiz: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
