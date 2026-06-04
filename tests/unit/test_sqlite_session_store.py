"""
SqliteSessionStore birim testleri — KULLANICI BAZLI izolasyon + kalıcılık + cleanup.

Asıl bug: history kullanıcıya bağlı değildi → herkes birbirinin geçmişini görüyordu.
Bu testler izolasyonu (owner A, owner B'nin geçmişini GÖREMEZ) ve kalıcılığı kilitler.
"""
from __future__ import annotations

import pytest

from api import db as auth_db
from llm.core.sqlite_session_store import SqliteSessionStore


@pytest.fixture()
def store(tmp_path):
    # Her test izole bir SQLite dosyasına bağlanır (paylaşılan singleton'ı resetler).
    auth_db.reset_for_tests(str(tmp_path / "t.db"))
    s = SqliteSessionStore(max_history=10)
    assert s.available
    yield s


def test_history_isolated_per_owner(store):
    # İki kullanıcı AYNI session_id'yi kullansa bile geçmişleri AYRI olmalı (asıl fix).
    store.add_turn("sess1", "user", "ali'nin sorusu", owner="ali")
    store.add_turn("sess1", "assistant", "ali'ye cevap", owner="ali")
    store.add_turn("sess1", "user", "veli'nin sorusu", owner="veli")

    ali = store.get_history("sess1", owner="ali")
    veli = store.get_history("sess1", owner="veli")

    assert [t.content for t in ali] == ["ali'nin sorusu", "ali'ye cevap"]
    assert [t.content for t in veli] == ["veli'nin sorusu"]
    # Sızıntı yok: ali, veli'nin içeriğini GÖRMEZ
    assert all("veli" not in t.content for t in ali)


def test_get_history_returns_chronological_last_n():
    # Bağlam penceresi: son max_history*2 mesaj (1 tur=user+asistan=2 mesaj), KRONOLOJİK sıra.
    auth_db.reset_for_tests(":memory:")
    s = SqliteSessionStore(max_history=2)          # → en fazla 4 mesaj döner
    for i in range(6):
        s.add_turn("s", "user", f"q{i}", owner="u")
    hist = s.get_history("s", owner="u")
    assert [t.content for t in hist] == ["q2", "q3", "q4", "q5"]  # son 4, sırayla


def test_list_sessions_only_owners(store):
    store.add_turn("s1", "user", "merhaba", owner="ali")
    store.add_turn("s2", "user", "ikinci sohbet", owner="ali")
    store.add_turn("s9", "user", "başkası", owner="veli")

    sess = store.list_sessions("ali")
    ids = {x["session_id"] for x in sess}
    assert ids == {"s1", "s2"}            # ali sadece kendi 2 oturumunu görür
    assert all("session_id" in x and "last_message" in x for x in sess)


def test_get_turns_owner_scoped(store):
    store.add_turn("s1", "user", "soru", owner="ali")
    store.add_turn("s1", "assistant", "cevap", owner="ali")
    # Sahibi tüm turları görür
    assert len(store.get_turns("ali", "s1")) == 2
    # BAŞKA kullanıcı aynı session_id'yi sorgularsa BOŞ döner (erişemez)
    assert store.get_turns("veli", "s1") == []


def test_delete_session_owner_scoped(store):
    store.add_turn("s1", "user", "x", owner="ali")
    store.add_turn("s1", "user", "y", owner="ali")
    # veli, ali'nin oturumunu silemez (owner filtresi → 0 silinir)
    assert store.delete_session("veli", "s1") == 0
    assert len(store.get_turns("ali", "s1")) == 2
    # ali kendi oturumunu siler
    assert store.delete_session("ali", "s1") == 2
    assert store.get_turns("ali", "s1") == []


def test_persistence_across_store_instances(tmp_path):
    # Kalıcılık: yeni store örneği aynı DB'den eski geçmişi okur (Redis TTL'i gibi uçmaz).
    path = str(tmp_path / "persist.db")
    auth_db.reset_for_tests(path)
    s1 = SqliteSessionStore()
    s1.add_turn("s", "user", "kalıcı mesaj", owner="ali")

    auth_db.reset_for_tests(path)  # bağlantıyı kapatıp yeniden aç (restart simülasyonu)
    s2 = SqliteSessionStore()
    hist = s2.get_turns("ali", "s")
    assert len(hist) == 1 and hist[0]["content"] == "kalıcı mesaj"


def test_cleanup_removes_old_turns(store):
    import sqlite3
    from datetime import datetime, timezone, timedelta
    # 40 gün önce bir tur enjekte et (created_at'i elle eski tarihe set)
    old_ts = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    conn = auth_db.get_conn()
    conn.execute(
        "INSERT INTO chat_history (owner, session_id, role, content, created_at) VALUES (?,?,?,?,?)",
        ("ali", "old", "user", "eski", old_ts),
    )
    conn.commit()
    store.add_turn("new", "user", "yeni", owner="ali")  # bugün

    removed = store.cleanup(retention_days=30)
    assert removed == 1                                   # sadece 40 günlük silindi
    assert store.get_turns("ali", "old") == []
    assert len(store.get_turns("ali", "new")) == 1        # yeni duruyor


def test_cleanup_disabled_when_zero(store):
    store.add_turn("s", "user", "x", owner="ali")
    assert store.cleanup(retention_days=0) == 0           # 0 = süresiz, hiçbir şey silinmez
    assert len(store.get_turns("ali", "s")) == 1


def test_empty_and_missing(store):
    assert store.get_history("", owner="ali") == []        # boş session_id
    assert store.get_history("yok", owner="ali") == []     # var olmayan
    assert store.list_sessions("kimse") == []
