# 22 — Kimlik Doğrulama (JWT) ve RBAC

**Güncelleme:** 2026-06
**İlgili kod:** `api/auth.py`, `api/auth_models.py`, `api/auth_store.py`, `api/router_auth.py`, `api/db.py`, `api/audit.py`, `config/schemas.py` (AuthConfig)

Bu belge, önceki ara raporlarda "açık (P0)" olarak işaretlenen **Authentication/Authorization**
eksikliğinin kapatılmasını belgeler. Zero-Trust temalı bir proje için kimlik doğrulama, "kimliğe
dayalı erişim (identity-centric access)" ilkesinin somut karşılığıdır.

---

## 1. JWT Authentication

- **Algoritma:** HS256 (PyJWT). Token payload: `sub` (kullanıcı adı), `role`, `jti` (logout/iptal),
  `iat`, `exp`.
- **Üretim/doğrulama:** `create_access_token(user)` / `get_current_user(...)` (FastAPI dependency).
- **Secret:** `JWT_SECRET` env (prod). Boşsa dev-mode (sabit dev-secret + demo hesap seed'i) devreye
  girer ve uyarı verilir. Prod'da secret ≥ 32 karakter zorunlu (`AuthConfig.__post_init__` doğrular).
- **Süre:** `auth.access_token_expiry_minutes` (varsayılan 60).
- **İptal (logout):** `jti` blok-listesi (`is_blocked`) ile çıkış yapılmış token reddedilir.

## 2. RBAC — Roller

`api/auth_models.py` rolleri: `sysadmin`, `security`, `developer`, `end_user`.

- **`require_role(*roles)`** dependency fabrikası korumalı rotalarda kullanılır:
  ```python
  dependencies=[Depends(require_role(Role.SYSADMIN, Role.SECURITY))]
  ```
  Yetersiz rol → 403.

## 3. İki erişim modu

| Yardımcı | Davranış | Kullanım |
|----------|----------|----------|
| `get_current_user` | Token yoksa **401** | Korumalı rotalar (audit, chat geçmişi API'si) |
| `peek_username` | Token yoksa **None** (zorlamaz) | Best-effort kimlik — `/chat` açık kalsın ama varsa kullanıcıya scope'lansın (bkz. [20_CHAT_HISTORY](20_CHAT_HISTORY_VE_OTURUM.md)) |

Bu ayrım önemlidir: `/chat` ve `/chat/stream` **açık** (anonim/demo), ama token gönderilirse
geçmiş ilgili kullanıcıya izole edilir; `GET/DELETE /chat/history` ve `/audit/logs` **auth zorunlu**.

## 4. Kalıcılık (SQLite — `data/auth.db`)

`api/db.py` paylaşılan bağlantı (WAL, tek-yazıcı kilit). Tablolar:
- **`users`** — id, username (unique), password_hash, role, email, created_at
- **`audit_log`** — ts, username, role, action, endpoint, method, status, ip, request_id, detail
- **`chat_history`** — bkz. [20](20_CHAT_HISTORY_VE_OTURUM.md)

`bootstrap_auth()` uygulama açılışında DB'yi kurar ve (boşsa) demo hesapları seed'ler.

## 5. Audit log
Korumalı/kritik istekler `audit_log`'a yazılır; aynı `request_id` log/metrik/trace ile korelasyonlu
(bkz. monitoring 3-katman korelasyon). `/audit/logs` (sysadmin) ile sorgulanır.

## 6. Önceki rapordaki durumla karşılaştırma
- Ocak/Mart/Mayıs ara raporları: "Authentication/Authorization — **açık (P0)**".
- Bu dönem: **kapatıldı** — JWT + RBAC + audit + SQLite. Tez §5 "açık maddeler"den çıkarılır.

## 7. Güvenlik notları
- `JWT_SECRET`, `AUTH_ADMIN_PASSWORD` repoda tutulmaz (`.env`, `.gitignore`'da). `.env.example`
  yalnız placeholder içerir. Public-safe için tracked dosyalardan gerçek secret'lar temizlendi
  (bkz. [13_GUVENLIK](13_GUVENLIK.md)).
