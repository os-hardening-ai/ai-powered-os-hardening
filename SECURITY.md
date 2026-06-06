# Güvenlik Politikası

## Desteklenen Sürümler
| Sürüm | Destek |
|-------|--------|
| 1.0.x | ✅ |

## Güvenlik Açığı Bildirimi
Bir güvenlik açığı bulduysanız **herkese açık issue açmayın.** Lütfen sorumlu açıklama (responsible
disclosure) ilkesiyle şu adrese bildirin:

**hardeningai@gmail.com**

- İlk yanıt: **72 saat** içinde.
- Düzeltme yayınlanana kadar açığı gizli tutmanızı rica ederiz.
- Geçerli bildirimler (isteğe bağlı) sürüm notlarında teşekkürle anılır.

## Kapsam
Backend API (FastAPI), kimlik doğrulama/RBAC, RAG/LLM pipeline, dağıtım yapılandırması.
Üçüncü-taraf bağımlılık açıkları için **Dependabot** + CI güvenlik taraması (pip-audit / Trivy /
gitleaks) düzenli çalışır.

## Uygulanan Önlemler (özet)
- **Kimlik/Yetki:** JWT (HS256) + RBAC (sysadmin/security/developer/end_user), parola **bcrypt** hash,
  partner için hash'li **API-key** (M2M).
- **Ağ/İstek:** Redis tabanlı **rate-limit**, audit log, CORS allowlist, TrustedHost.
- **Başlıklar:** CSP, HSTS, X-Frame-Options (DENY), X-Content-Type-Options, Referrer-Policy,
  Permissions-Policy.
- **İçerik:** Girdi doğrulama + çıktı sanitizasyonu; **L1 güvenlik katmanı** (prompt-injection /
  jailbreak / kapsam-dışı filtresi).
- **Sırlar:** `.env` git-dışı; API anahtarları **düz metin saklanmaz** (SHA-256); otomatik **TLS** (Caddy).

## Bunu Bir Güvenlik Projesi Yapan Nokta
Bu sistem aynı zamanda OS sıkılaştırma rehberleri üreten bir araçtır; ürettiği her öneri
**CIS Benchmark + NIST 800-207 (Zero-Trust)** referanslarıyla gerekçelendirilir.
