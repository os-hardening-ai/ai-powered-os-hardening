# Güvenlik Dokümantasyonu

## Güvenlik Özellikleri

### 1. Rate Limiting

**Token Bucket Algorithm**
- 100 request/dakika per IP
- 5 dakika ban süresi
- Otomatik IP tracking

**Implementation**: `api/security.py` - `RateLimiter`

### 2. Input Validation

**Pydantic Validation**
- Max 5000 karakter
- Boş input reddetme
- Field-level validation

**SQL/XSS Injection Protection** (strict mode)
- SQL pattern detection
- Script injection detection

**Implementation**: `api/security.py` - `InputValidator`

### 3. Security Headers

Tüm response'larda:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000`
- `Content-Security-Policy: default-src 'self'`

**Implementation**: `api/security.py` - `SecurityHeadersMiddleware`

### 4. Output Sanitization

LLM output'tan temizlenen:
- `[INST]...[/INST]` patterns
- `<|im_start|>...<|im_end|>` patterns
- System instructions

**Implementation**: `api/security.py` - `sanitize_output()`

### 5. Prompt Injection Protection (Opsiyonel)

**Tespit edilen saldırılar**:
- Instruction override
- Jailbreak attempts
- System prompt extraction

**Not**: LLM provider'lar (Groq, OpenAI) zaten koruma sağlar. Burası ek savunma katmanı.

## Production Deployment

```env
# Production .env
ALLOWED_HOSTS=yourdomain.com
CORS_ORIGINS=https://yourdomain.com
RATE_LIMIT_REQUESTS=50  # Daha sıkı
```

## Vulnerability Scanning

```bash
pip install pip-audit
pip-audit
```

## Best Practices

1. **HTTPS kullanın** (production'da zorunlu)
2. **API keys'i güvende tutun** (.env dosyası .gitignore'da)
3. **Rate limits ayarlayın** (production için daha sıkı)
4. **Logs monitör edin** (/metrics/errors endpoint)
5. **Dependencies güncel tutun** (pip-audit ile kontrol)
