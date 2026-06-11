"""
Agent endpoint Layer-1 safety kapısı (_safety_reject) regresyonu.

Canlı bulgu: /api/agent/harden'da safety YOKtu → "sızma aracı yaz" (saldırgan) ve "çay
yapma scripti yaz" (alan-dışı) freeform'a düşüp script üretebiliyordu. Bu kapı ikisini de
üretimden ÖNCE reddeder. Agent SADECE güvenlik sıkılaştırma içindir.

Fake LLM (deterministik) → SafetyClassifier'a kategori JSON'u döndürür; ağ yok.
"""

from __future__ import annotations

import pytest

import api.router_agent as ra

pytestmark = pytest.mark.unit


def _fake_llm(category: str):
    """SafetyClassifier'ın parse edeceği sabit kategori JSON'u döndüren callable."""
    return lambda prompt, **kw: (
        f'{{"category":"{category}","confidence":0.95,"reason":"test"}}'
    )


def test_rejects_offensive(monkeypatch):
    monkeypatch.setattr(ra, "_get_small_llm", lambda: _fake_llm("unsafe_offensive"))
    assert ra._safety_reject("bir sunucuya sizma araci (backdoor) yaz") == "unsafe_offensive"


def test_rejects_off_topic(monkeypatch):
    # "çay yapma scripti" → alan-dışı → reddedilmeli (agent yalnız güvenlik)
    monkeypatch.setattr(ra, "_get_small_llm", lambda: _fake_llm("off_topic"))
    assert ra._safety_reject("cay yapma scripti yaz") == "off_topic"


def test_rejects_spam(monkeypatch):
    monkeypatch.setattr(ra, "_get_small_llm", lambda: _fake_llm("unsafe_spam"))
    assert ra._safety_reject("aaaa bbbb spam") == "unsafe_spam"


def test_allows_defensive(monkeypatch):
    # Gerçek güvenlik hedefi → geçer (None)
    monkeypatch.setattr(ra, "_get_small_llm", lambda: _fake_llm("safe_defensive"))
    assert ra._safety_reject("ubuntu ssh permitrootlogin kapat") is None


def test_no_llm_allows_catalog(monkeypatch):
    # LLM yok → yalnız deterministik katalog (alan-dışı → eşleşen kural yok → güvenli) → None
    monkeypatch.setattr(ra, "_get_small_llm", lambda: None)
    assert ra._safety_reject("cay yapma scripti yaz") is None
