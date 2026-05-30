"""
Unit tests for llm.core.redis_session_store.RedisSessionStore.

No real Redis: the unavailable path uses a bad URL, the operational path
injects an in-memory FakeRedis. Verifies graceful degradation and the
list-based history semantics.
"""

from __future__ import annotations

import json

from llm.core.redis_session_store import RedisSessionStore
from llm.core.session_store import Turn


class FakeRedis:
    def __init__(self, raise_on=None):
        self.data = {}
        self.raise_on = raise_on or set()

    def _maybe_raise(self, op):
        if op in self.raise_on:
            raise RuntimeError(f"redis {op} failed")

    def rpush(self, key, val):
        self._maybe_raise("rpush")
        self.data.setdefault(key, []).append(val)

    def expire(self, key, ttl):
        pass

    def ltrim(self, key, start, end):
        lst = self.data.get(key, [])
        self.data[key] = lst[start:] if end == -1 else lst[start:end + 1]

    def lrange(self, key, start, end):
        self._maybe_raise("lrange")
        lst = self.data.get(key, [])
        return lst[start:] if end == -1 else lst[start:end + 1]

    def delete(self, key):
        self.data.pop(key, None)


def make_store():
    # bad URL -> connection fails -> _client stays None (unavailable path covered)
    return RedisSessionStore(url="redis://127.0.0.1:1/0", ttl_seconds=60, max_history=3)


class TestUnavailable:
    def test_unavailable_is_graceful(self):
        s = make_store()
        assert s.available is False
        assert s.get_history("s1") == []
        s.add_turn("s1", "user", "x")   # no-op, no raise
        s.reset_session("s1")           # no-op
        assert s.get_history("s1") == []

    def test_empty_session_id_guarded(self):
        s = make_store()
        s._client = FakeRedis()
        assert s.get_history("") == []
        s.add_turn("", "user", "x")  # guarded no-op


class TestOperational:
    def test_add_and_get_roundtrip(self):
        s = make_store()
        s._client = FakeRedis()
        s.add_turn("s1", "user", "soru", intent="os_hardening")
        s.add_turn("s1", "assistant", "cevap")
        hist = s.get_history("s1")
        assert len(hist) == 2
        assert all(isinstance(t, Turn) for t in hist)
        assert hist[0].role == "user"
        assert hist[0].intent == "os_hardening"

    def test_reset_deletes(self):
        s = make_store()
        s._client = FakeRedis()
        s.add_turn("s1", "user", "x")
        s.reset_session("s1")
        assert s.get_history("s1") == []

    def test_get_history_error_is_swallowed(self):
        s = make_store()
        s._client = FakeRedis(raise_on={"lrange"})
        assert s.get_history("s1") == []

    def test_add_turn_error_is_swallowed(self):
        s = make_store()
        s._client = FakeRedis(raise_on={"rpush"})
        s.add_turn("s1", "user", "x")  # must not raise
