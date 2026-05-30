"""
Postman koleksiyonu üretici — auth-aware (JWT) + test assertion'lı.

Çalıştır:  python tests/postman/build_collection.py
Sonra:     newman run tests/postman/hardening_api.postman_collection.json --env-var baseUrl=http://localhost:8000

Akış: önce /auth/login token'ı 'token' değişkenine yazar; korumalı istekler
`Authorization: Bearer {{token}}` kullanır; logout en sonda token'ı iptal eder.
LLM/Qdrant gerektiren uçlar (chat/rag) canlı servis yoksa graceful 200/503 döner;
assertion'lar bu sözleşmeyi doğrular.
"""
import json
from pathlib import Path

BEARER = [{"key": "Authorization", "value": "Bearer {{token}}"},
          {"key": "Content-Type", "value": "application/json"}]
JSONH = [{"key": "Content-Type", "value": "application/json"}]


def url(path):
    raw = "{{baseUrl}}" + path
    parts = path.lstrip("/").split("?")
    p = parts[0].split("/")
    u = {"raw": raw, "host": ["{{baseUrl}}"], "path": p}
    if len(parts) > 1:
        u["query"] = [{"key": k, "value": v} for k, v in
                      (kv.split("=") for kv in parts[1].split("&"))]
    return u


def item(name, method, path, *, headers=None, body=None, tests=None):
    req = {"method": method, "header": headers or [], "url": url(path)}
    if body is not None:
        req["body"] = {"mode": "raw", "raw": json.dumps(body)}
    ev = []
    if tests:
        ev.append({"listen": "test", "script": {"type": "text/javascript", "exec": tests}})
    return {"name": name, "request": req, "event": ev}


def st(code):
    return [f"pm.test('status {code}', () => pm.response.to.have.status({code}));"]


items = [
    # 1) Login — token'ı kaydet
    item("Auth: POST /auth/login (admin)", "POST", "/auth/login", headers=JSONH,
         body={"username": "admin", "password": "changeme123"},
         tests=[
             "pm.test('status 200', () => pm.response.to.have.status(200));",
             "const j = pm.response.json();",
             "pm.test('access_token var', () => pm.expect(j.access_token).to.be.a('string').and.not.empty);",
             "pm.test('role sysadmin', () => pm.expect(j.role).to.eql('sysadmin'));",
             "pm.collectionVariables.set('token', j.access_token);",
         ]),
    item("Auth: GET /auth/me", "GET", "/auth/me", headers=BEARER,
         tests=["pm.test('status 200', () => pm.response.to.have.status(200));",
                "pm.test('username admin', () => pm.expect(pm.response.json().username).to.eql('admin'));"]),
    # Health (public)
    item("Health: GET /health", "GET", "/health",
         tests=["pm.test('status 200', () => pm.response.to.have.status(200));",
                "pm.test('status alanı var', () => pm.expect(pm.response.json()).to.have.property('status'));"]),
    # Domain — rule engine (LLM gerektirmez)
    item("Domain: GET /api/rules?limit=5", "GET", "/api/rules?limit=5&os=ubuntu_24_04", headers=BEARER,
         tests=st(200)),
    item("Domain: POST /api/rules/plan", "POST", "/api/rules/plan", headers=BEARER,
         body={"rule_ids": ["1.1.1.1", "1.1.1.2", "1.1.1.3"], "os": "ubuntu_24_04"}, tests=st(200)),
    item("Domain: POST /api/rules/conflicts", "POST", "/api/rules/conflicts", headers=BEARER,
         body={"rule_ids": ["1.1.1.1", "1.1.1.2"], "os": "ubuntu_24_04"}, tests=st(200)),
    item("Domain: POST /api/artifacts/generate (bash)", "POST", "/api/artifacts/generate", headers=BEARER,
         body={"rule_ids": ["1.1.1.1"], "format": "bash", "os": "ubuntu_24_04"},
         tests=["pm.test('status 200', () => pm.response.to.have.status(200));",
                "pm.test('content var', () => pm.expect(pm.response.json()).to.have.property('content'));"]),
    # Agentic (LLM yoksa deterministik fallback → 200)
    item("Agent İP-6: POST /api/agent/plan", "POST", "/api/agent/plan", headers=BEARER,
         body={"goal": "SSH ve parola sıkılaştır", "os_target": "ubuntu_24_04", "security_level": "balanced"},
         tests=["pm.test('status 200', () => pm.response.to.have.status(200));",
                "pm.test('items dizisi', () => pm.expect(pm.response.json().items).to.be.an('array'));"]),
    item("Agent İP-7: POST /api/agent/harden (bash)", "POST", "/api/agent/harden", headers=BEARER,
         body={"goal": "SSH sıkılaştır", "os_target": "ubuntu_24_04", "security_level": "balanced", "format": "bash"},
         tests=st(200)),
    # OpenAI-compat models (LLM çağrısı yok)
    item("OpenAI-compat: GET /v1/models", "GET", "/v1/models", headers=BEARER, tests=st(200)),
    # Audit (sysadmin)
    item("Monitoring: GET /api/audit", "GET", "/api/audit?limit=10", headers=BEARER,
         tests=["pm.test('status 200', () => pm.response.to.have.status(200));",
                "pm.test('events dizisi', () => pm.expect(pm.response.json().events).to.be.an('array'));"]),
    # Chat — LLM yoksa graceful (200, degraded answer)
    item("Chat: POST /api/chat (use_rag=false)", "POST", "/api/chat", headers=BEARER,
         body={"question": "SSH nedir?", "use_rag": False},
         tests=["pm.test('status 200 (LLM yoksa graceful)', () => pm.response.to.have.status(200));",
                "pm.test('answer alanı var', () => pm.expect(pm.response.json()).to.have.property('answer'));"]),
    # RAG — Qdrant gerektirir; canlı yoksa 503 (graceful). Prod'da 200.
    item("RAG: POST /rag/search (Qdrant-bağımlı)", "POST", "/rag/search", headers=BEARER,
         body={"query": "ssh hardening", "top_k": 3},
         tests=["pm.test('200 (Qdrant açık) veya 503 (Qdrant yok) — graceful', () => pm.expect([200,503]).to.include(pm.response.code));"]),
    # ── Negatif / güvenlik sözleşmesi ──
    item("RBAC: GET /api/rules (token YOK → 401)", "GET", "/api/rules", tests=st(401)),
    item("Validation: POST /api/agent/plan (boş goal → 422)", "POST", "/api/agent/plan", headers=BEARER,
         body={"goal": ""}, tests=st(422)),
    # Logout (token'ı iptal et) — token kullanan TÜM isteklerden SONRA
    item("Auth: POST /auth/logout", "POST", "/auth/logout", headers=BEARER, tests=st(200)),
    item("Auth: GET /auth/me (logout sonrası → 401)", "GET", "/auth/me", headers=BEARER, tests=st(401)),
]

collection = {
    "info": {
        "name": "AI-Powered OS Hardening API (JWT auth-aware)",
        "description": "JWT auth + RBAC + rule engine + agentic + graceful LLM/RAG sözleşme testleri.",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "item": items,
    "variable": [
        {"key": "baseUrl", "value": "http://localhost:8000"},
        {"key": "token", "value": ""},
    ],
}

out = Path(__file__).parent / "hardening_api.postman_collection.json"
out.write_text(json.dumps(collection, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Yazıldı: {out} ({len(items)} istek)")
