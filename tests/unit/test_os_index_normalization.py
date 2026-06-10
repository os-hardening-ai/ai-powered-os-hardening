"""OS index normalizasyonu (router_chat._normalize_os_for_index).

Bug: kullanıcı 'Ubuntu 22.04 LTS' seçince RAG os_version filtresi indekste karşılık
bulamıyor (indeks: ubuntu_24_04 / windows_11 / windows_server_2025) → soft-fallback
filtreyi düşürüyor → YANLIŞ OS (Windows) içeriği sızıyordu. Normalizasyon, seçimi en
yakın indeksli aynı-aile sürüme eşler (cross-OS sızıntısını önler).
"""
from __future__ import annotations

import pytest

from api.router_chat import _normalize_os_for_index

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("inp,exp", [
    # indekslenmemiş → en yakın indeksli aynı-aile
    ("ubuntu_22_04", "ubuntu_24_04"),
    ("ubuntu_20_04", "ubuntu_24_04"),
    ("debian_12", "ubuntu_24_04"),
    ("linux", "ubuntu_24_04"),
    ("windows_server_2022", "windows_server_2025"),
    ("windows_server_2019", "windows_server_2025"),
    ("windows_10", "windows_11"),
    # indeksli → AYNEN (değişmez)
    ("ubuntu_24_04", "ubuntu_24_04"),
    ("windows_11", "windows_11"),
    ("windows_server_2025", "windows_server_2025"),
    # tanınmayan / boş → aynen (RAG kendi fallback'ini yapar)
    ("macos", "macos"),
    (None, None),
    ("", ""),
])
def test_normalize_os_for_index(inp, exp):
    assert _normalize_os_for_index(inp) == exp


def test_cross_os_never_leaks():
    # Linux seçimleri ASLA Windows'a, Windows seçimleri ASLA Linux'a düşmez
    for linux in ("ubuntu_22_04", "ubuntu_20_04", "debian_11", "linux"):
        assert "windows" not in _normalize_os_for_index(linux)
    for win in ("windows_10", "windows_server_2022"):
        assert _normalize_os_for_index(win).startswith("windows")
