"""Partner API-key (M2M) birim testleri — offline, deterministik (ağ/LLM gerektirmez)."""
import hashlib

from api.api_keys import resolve_api_key
from api.auth_models import Role


def _h(k: str) -> str:
    return hashlib.sha256(k.encode()).hexdigest()


def test_gecerli_anahtar_cozulur(monkeypatch):
    monkeypatch.setenv("PARTNER_API_KEYS", f"kardesekip:{_h('gizli-123')}:security")
    u = resolve_api_key("gizli-123")
    assert u is not None
    assert u.username == "partner:kardesekip"
    assert u.role == Role.SECURITY


def test_gecersiz_anahtar_none(monkeypatch):
    monkeypatch.setenv("PARTNER_API_KEYS", f"kardesekip:{_h('gizli-123')}:security")
    assert resolve_api_key("yanlis-anahtar") is None


def test_bos_env_none(monkeypatch):
    monkeypatch.setenv("PARTNER_API_KEYS", "")
    assert resolve_api_key("herhangi") is None


def test_none_token(monkeypatch):
    monkeypatch.setenv("PARTNER_API_KEYS", f"k:{_h('x')}:security")
    assert resolve_api_key(None) is None


def test_birden_cok_anahtar(monkeypatch):
    monkeypatch.setenv(
        "PARTNER_API_KEYS",
        f"a:{_h('ka')}:developer,b:{_h('kb')}:security",
    )
    assert resolve_api_key("ka").username == "partner:a"
    assert resolve_api_key("ka").role == Role.DEVELOPER
    assert resolve_api_key("kb").role == Role.SECURITY


def test_bozuk_girdi_atlanir(monkeypatch):
    monkeypatch.setenv("PARTNER_API_KEYS", f"bozuk-girdi,a:{_h('ka')}:developer")
    assert resolve_api_key("ka") is not None  # bozuk atlanır, geçerli olan çalışır


def test_gecersiz_rol_atlanir(monkeypatch):
    monkeypatch.setenv("PARTNER_API_KEYS", f"a:{_h('ka')}:olmayan_rol")
    assert resolve_api_key("ka") is None  # geçersiz rol → anahtar yüklenmez


def test_anahtar_hashli_dogrulama(monkeypatch):
    # Aynı düz anahtarın SHA-256'sı eşleşmeli; düz metin saklanmaz.
    plain = "uzun-gizli-anahtar"
    monkeypatch.setenv("PARTNER_API_KEYS", f"x:{_h(plain)}:end_user")
    assert resolve_api_key(plain).role == Role.END_USER
