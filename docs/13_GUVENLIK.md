# Güvenlik (Security)

Bu belge sistemin güvenlik mimarisini ve önlemlerini açıklar.

## Katmanlar

1. **Input Validation** — `api/security.py`, prompt injection ve dangerous pattern tespiti
2. **Safety Classifier** — LLM tabanlı güvenlik sınıflandırması (Layer 1), **fail-closed**
3. **Output Validation** — üretilen script'lerde tehlikeli komut tespiti
4. **Authentication** — API-key (header) tabanlı erişim kontrolü
5. **Rate Limiting** — IP başına istek sınırlama (Redis-backed, graceful fallback)
6. **Security Headers** — XSS, clickjacking, MIME-sniffing koruması

## Safety Classifier — Fail-Closed

Layer 1 güvenlik sınıflandırıcısı **fail-closed** çalışır: LLM çağrısı hata
verirse, kategori parse edilemezse veya geçersiz bir etiket dönerse sonuç
`unverified` olur ve istek **reddedilir** (`is_safe=False`). Böylece bir Groq
kesintisi güvenlik kapısını sessizce devre dışı bırakamaz.

Ayrıca kullanıcı girdisi sınıflandırma prompt'una `<USER_INPUT>` bloğu içinde,
"yalnızca veri olarak ele al" direktifiyle enjekte edilir ve delimiter-escape
denemeleri nötralize edilir (prompt injection savunması).

## Authentication — API Key

`api/auth.py` → `require_api_key` dependency'si. `API_KEY` ortam değişkeni set
ise tüm uçlar (health hariç) `X-API-Key` header'ı ister; karşılaştırma
constant-time'dır. `API_KEY` set değilse **geliştirme modunda** açık çalışır ve
tek seferlik uyarı loglanır. Health uçları liveness/readiness probe'ları için
public kalır.

## Rate Limiting

`RateLimitMiddleware`: dakika/saat bazlı limit.
- **Redis-backed** (atomik INCR+EXPIRE) — `REDIS_URL`/config erişilebilirse;
  dağıtık ve restart'a dayanıklı. Redis hiccup'ta **fail-open** (altyapı sorunu
  tüm API'yi düşürmesin).
- Erişilemezse **in-memory** fallback (process-local).
- İstemci IP'si varsayılan olarak gerçek peer adresinden alınır; `X-Forwarded-For`
  yalnızca `TRUST_PROXY=1` (bilinen LB arkasında) ise güvenilir (IP spoofing'e karşı).
- Limit aşımında standart `{"error": {...}}` şeması + `Retry-After` başlığı.

## LLM Sağlayıcı Güvenilirliği

- **Timeout + retry:** Groq/OpenAI SDK çağrıları `timeout` ve `max_retries` ile;
  429/5xx'te exponential backoff + `Retry-After` başlığına uyum.
- **Fallback zinciri:** birincil sağlayıcı düşerse sırayla diğerlerine geçilir
  (Groq → Novita → OpenAI → Ollama); hepsi düşerse anlamlı hata yükseltilir
  (sessiz boş cevap dönmez).

## CORS / Trusted Host

- CORS origin'leri `config.json`'dan okunur; wildcard (`*`) origin'de
  `allow_credentials` otomatik kapatılır (güvensiz kombinasyon engellenir).
- `TrustedHostMiddleware` `ALLOWED_HOSTS` env ile kısıtlanabilir.
- Her iki wildcard durumunda startup'ta uyarı loglanır.
- **Not:** Varsayılan dağıtım açık bırakılmıştır; production'da `ALLOWED_HOSTS` ve
  spesifik CORS origin'leri ayarlanmalıdır.

## Hata Yönetimi — Sızıntı Yok

Tüm router catch-all'ları `raise_internal_error` kullanır: gerçek exception
**yalnızca sunucu loguna** yazılır (request_id ile korele), client'a sadece
jenerik mesaj + request_id döner. Stack trace / iç detay / secret sızmaz.

## Bilinen Kısıtlar / Yapılacaklar

- API key tek-anahtar modelidir; çok-kullanıcılı/rol-bazlı (RBAC) erişim için
  JWT'ye yükseltilebilir.
- CORS/TrustedHost varsayılanı açık — production öncesi kısıtlanmalı.
