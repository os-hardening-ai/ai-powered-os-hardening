"""
E2E — uçtan uca kullanıcı yolculuğu (GERÇEK JWT auth + RBAC + 4 chat ucu).

conftest'teki `client` fixture'ı get_current_user'ı override eder (auth'u baypaslar);
burada onu KULLANMAYIZ — `create_app()` ile TAZE app kurar, GERÇEK auth akışını koşarız:
login → JWT → Bearer ile chat uçları → RBAC (Pano/metrics gate) → logout/blacklist.

Tamamı AĞSIZ: LLM'ler fake (safety prompt'u <USER_INPUT> → SAFE), RAG kapalı (use_rag=false),
auth dev-mode + izole SQLite. Frontend role-gate'inin (Pano yalnız sysadmin/security) backend
karşılığı burada `/metrics` 401/403/200 ile doğrulanır.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.e2e, pytest.mark.api]

_SAFE_JSON = '{"category": "safe_defensive", "confidence": 0.95, "reason": "hardening"}'
_INFO = "SSH için PermitRootLogin no, anahtar tabanlı auth. CIS 5.2."
_SCRIPT = "```bash\nsudo ufw enable\n```"


def _fake_small(prompt, **_kw):
    return _SAFE_JSON if "USER_INPUT" in prompt else _INFO


def _fake_large(prompt, **_kw):
    return _SCRIPT


def _parse_sse(text: str):
    events = []
    for block in text.split("\n\n"):
        ev = data = None
        for line in block.splitlines():
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
        if ev:
            events.append((ev, json.loads(data) if data else None))
    return events


def _sse_meta(text: str) -> dict:
    for ev, d in _parse_sse(text):
        if ev == "metadata":
            return d or {}
    return {}


@pytest.fixture
def e2e(tmp_path, monkeypatch):
    """Taze app + izole auth DB + fake LLM (gerçek JWT, override YOK)."""
    monkeypatch.delenv("JWT_SECRET", raising=False)  # dev mode (sabit dev-secret)
    from api import db, auth_blacklist
    from api.auth_store import user_store
    from api.auth_models import Role

    # ÖNEMLİ: create_app() → bootstrap_auth() → init_db() VARSAYILAN path'e (data/auth.db)
    # döner ve temp bağlantımızı kapatır. _resolve_db_path'i temp'e sabitleyerek bootstrap'ın
    # da AYNI izole DB'yi kullanmasını sağlarız (gerçek data/auth.db kirlenmez).
    db_file = str(tmp_path / "e2e_auth.db")
    monkeypatch.setattr("api.db._resolve_db_path", lambda: db_file)
    db.reset_for_tests(db_file)
    auth_blacklist.reset_for_tests()
    user_store.create("e2e_admin", "adminpass1", Role.SYSADMIN)
    user_store.create("e2e_user", "userpass1", Role.END_USER)

    monkeypatch.setattr(
        "api.router_chat._get_llm_clients", lambda: (_fake_small, _fake_large)
    )

    # Mevcut main.app'i kullan (create_app'i TEKRAR çağırmak Prometheus collector'ı
    # yeniden register edip "Duplicated timeseries" verir). conftest'in get_current_user
    # override'ını GEÇİCİ temizle → GERÇEK JWT auth koşsun; sonunda geri yükle.
    from main import app
    saved_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved_overrides)
        db.reset_for_tests("data/auth.db")
        auth_blacklist.reset_for_tests()


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


_SMALLTALK = {"question": "selam", "os": "ubuntu_24_04", "role": "sysadmin", "use_rag": False}
_SECURITY = {"question": "SSH nasıl sıkılaştırılır", "os": "ubuntu_24_04",
             "role": "sysadmin", "use_rag": False}


class TestFullJourney:
    def test_login_returns_jwt_and_role(self, e2e):
        r = e2e.post("/auth/login", json={"username": "e2e_admin", "password": "adminpass1"})
        assert r.status_code == 200
        body = r.json()
        assert body["access_token"] and body["role"] == "sysadmin"

    def test_chat_requires_auth(self, e2e):
        # Token olmadan korumalı uç → 401
        r = e2e.post("/api/chat", json=_SMALLTALK)
        assert r.status_code == 401

    def test_all_four_chat_endpoints_with_real_jwt(self, e2e):
        token = _login(e2e, "e2e_admin", "adminpass1")
        h = _auth(token)

        # 1) /api/chat — smalltalk tam pipeline → 3A
        r1 = e2e.post("/api/chat", json=_SMALLTALK, headers=h)
        assert r1.status_code == 200
        assert r1.json()["intent"] == "smalltalk"
        assert r1.json()["layer_path"].endswith("3A")

        # 2) /api/chat/stream — smalltalk akışta da 3A (REGRESYON)
        r2 = e2e.post("/api/chat/stream", json=_SMALLTALK, headers=h)
        assert r2.status_code == 200
        assert _sse_meta(r2.text).get("intent") == "smalltalk"

        # 3) /api/chat/fast — Hızlı RAG (non-stream)
        r3 = e2e.post("/api/chat/fast", json=_SECURITY, headers=h)
        assert r3.status_code == 200
        assert r3.json()["layer_path"] == "1→RAG→GEN(fast)"

        # 4) /api/chat/stream/fast — Hızlı RAG gerçek-token
        r4 = e2e.post("/api/chat/stream/fast", json=_SECURITY, headers=h)
        assert r4.status_code == 200
        assert _sse_meta(r4.text).get("streaming") == "real-token"

    def test_rbac_metrics_gate_mirrors_pano(self, e2e):
        """Frontend Pano role-gate'inin backend karşılığı: /metrics yalnız sysadmin/security."""
        admin = _login(e2e, "e2e_admin", "adminpass1")
        user = _login(e2e, "e2e_user", "userpass1")

        assert e2e.get("/metrics").status_code == 401                      # token yok
        assert e2e.get("/metrics", headers=_auth(user)).status_code == 403  # end_user yetkisiz
        assert e2e.get("/metrics", headers=_auth(admin)).status_code == 200  # sysadmin OK

    def test_logout_revokes_token(self, e2e):
        token = _login(e2e, "e2e_admin", "adminpass1")
        h = _auth(token)
        assert e2e.get("/auth/me", headers=h).status_code == 200
        assert e2e.post("/auth/logout", headers=h).status_code == 200
        # Blacklist sonrası aynı token reddedilir
        assert e2e.get("/auth/me", headers=h).status_code == 401
