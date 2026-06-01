"""
Chat uç-noktaları — mod matrisi + streaming paritesi (HTTP seviyesi, AĞSIZ).

Kapsam (api/router_chat.py'deki 4 uç):
  /api/chat              — tam SecurePipelineV2 (non-stream)
  /api/chat/stream       — AYNI pipeline, SSE ile kelime-kelime
  /api/chat/fast         — Hızlı RAG (non-stream), intent routing YOK
  /api/chat/stream/fast  — Hızlı RAG, gerçek token-token SSE

REGRESYON ODAĞI: Eskiden /api/chat/stream kendi mini-pipeline'ını koşup Layer 2/3'ü
atlıyordu → `selam` gibi smalltalk girdileri RAG'a gidip uzun güvenlik cevabı dönüyordu.
Artık stream de tam pipeline'ı koşar → `selam` ANINDA smalltalk yanıtı alır (RAG yok).

LLM'ler fake (ağsız, deterministik): safety prompt'u `<USER_INPUT>` içerir → SAFE döner;
diğer prompt'lar (üretim) sabit metin döner. RAG kapalı (use_rag=false) → Qdrant'a gidilmez.
Auth: conftest `client` fixture'ı get_current_user'ı test-sysadmin'e override eder.
"""
from __future__ import annotations

import json

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.api]

# fake LLM çıktıları
_SAFE_JSON = '{"category": "safe_defensive", "confidence": 0.95, "reason": "hardening"}'
_INFO_ANSWER = "SSH için PermitRootLogin no ayarlanır, anahtar tabanlı auth kullanılır. CIS 5.2."
_SCRIPT_ANSWER = "```bash\nset -euo pipefail\nsudo ufw enable\n```"


def _fake_small(prompt, **_kw):
    # Safety sınıflandırma prompt'u <USER_INPUT> içerir → güvenli verdict döndür.
    if "USER_INPUT" in prompt:
        return _SAFE_JSON
    return _INFO_ANSWER


def _fake_large(prompt, **_kw):
    return _SCRIPT_ANSWER


@pytest.fixture(autouse=True)
def _patch_llms(monkeypatch):
    """Router'ın LLM fabrikasını fake'lere bağla (ağsız)."""
    monkeypatch.setattr(
        "api.router_chat._get_llm_clients", lambda: (_fake_small, _fake_large)
    )


def _parse_sse(text: str):
    """SSE gövdesini [(event, data_dict), ...] listesine ayır."""
    events = []
    for block in text.split("\n\n"):
        ev = None
        data_raw = None
        for line in block.splitlines():
            if line.startswith("event:"):
                ev = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_raw = line[len("data:"):].strip()
        if ev:
            events.append((ev, json.loads(data_raw) if data_raw else None))
    return events


def _sse_tokens(events) -> str:
    """SSE 'message' event'lerindeki token'ları birleştir → tam cevap metni."""
    return "".join(d.get("token", "") for ev, d in events if ev == "message" and d)


def _meta(events) -> dict:
    for ev, d in events:
        if ev == "metadata":
            return d or {}
    return {}


_SMALLTALK = {"question": "selam", "os": "ubuntu_24_04", "role": "sysadmin", "use_rag": False}
_SECURITY = {
    "question": "SSH nasıl sıkılaştırılır",
    "os": "ubuntu_24_04",
    "role": "sysadmin",
    "use_rag": False,
}


# ════════════════════════════════════════════════════════════════════════
# 1) /api/chat — smalltalk tam pipeline'da 3A'ya gider (RAG yok)
# ════════════════════════════════════════════════════════════════════════
class TestChatSmalltalk:
    def test_selam_routes_to_pattern_responder(self, client):
        r = client.post("/api/chat", json=_SMALLTALK)
        assert r.status_code == 200
        body = r.json()
        assert body["intent"] == "smalltalk"
        assert body["layer_path"].endswith("3A")
        assert body["rag_sources"] == []
        # Smalltalk yanıtı — üretim fake'i (INFO/SCRIPT) DEĞİL, kısa selam
        assert _INFO_ANSWER not in body["answer"]
        assert _SCRIPT_ANSWER not in body["answer"]
        assert len(body["answer"]) < 400
        # OPTİMİZASYON: smalltalk'ta safety LLM atlanır → maliyet $0 (eski 0.0001 gitti)
        assert body.get("estimated_cost") == 0


# ════════════════════════════════════════════════════════════════════════
# 2) /api/chat/stream — REGRESYON: smalltalk akışta da 3A (RAG cevabı DEĞİL)
# ════════════════════════════════════════════════════════════════════════
class TestChatStreamParity:
    def test_stream_selam_is_smalltalk_not_rag(self, client):
        r = client.post("/api/chat/stream", json=_SMALLTALK)
        assert r.status_code == 200
        events = _parse_sse(r.text)
        meta = _meta(events)
        assert meta.get("intent") == "smalltalk"
        assert str(meta.get("layer_path", "")).endswith("3A")
        assert meta.get("rag_used") is False
        # Akan metin selam yanıtı — uzun güvenlik/RAG cevabı DEĞİL
        answer = _sse_tokens(events)
        assert answer.strip()
        assert _INFO_ANSWER not in answer
        # 'sources' event'i smalltalk'ta yayınlanmaz
        assert all(ev != "sources" for ev, _ in events)

    def test_stream_security_question_uses_pipeline(self, client):
        r = client.post("/api/chat/stream", json=_SECURITY)
        assert r.status_code == 200
        meta = _meta(_parse_sse(r.text))
        # Güvenlik sorusu smalltalk DEĞİL → info/action yoluna gider
        assert meta.get("intent") in {"info_request", "action_request"}


# ════════════════════════════════════════════════════════════════════════
# 3) "Hızlı RAG" uçları DEVRE DIŞI (PR #30) — Retrieval Explorer (/rag/search) +
#    akıllı sohbet (/api/chat[/stream]) yeterli. Route'lar kayıt edilmiyor.
# ════════════════════════════════════════════════════════════════════════
class TestFastPathsDisabled:
    @pytest.mark.parametrize("path", ["/api/chat/fast", "/api/chat/stream/fast"])
    def test_fast_endpoints_unregistered(self, client, path):
        # @router.post yorumlandı → route kayıtsız → 404 (kod korundu, re-enable kolay).
        r = client.post(path, json=_SECURITY)
        assert r.status_code == 404, f"{path} devre dışı olmalı (404), döndü: {r.status_code}"
