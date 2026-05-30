"""
Tests for api.auth_blacklist (JWT jti blacklist).

In this test env the `redis` package is not importable → the backend falls back
to the in-memory implementation, which is exactly what we exercise here:
block/is_blocked, expiry, empty/None jti guards, and the in-memory GC.
"""

from __future__ import annotations

import time

from api.auth_blacklist import _InMemoryBlacklist, block_token, is_blocked, reset_for_tests


class TestInMemoryBlacklist:
    def test_block_then_blocked(self):
        bl = _InMemoryBlacklist()
        bl.block("jti-1", 60)
        assert bl.is_blocked("jti-1") is True

    def test_unknown_not_blocked(self):
        assert _InMemoryBlacklist().is_blocked("nope") is False

    def test_expired_not_blocked(self):
        bl = _InMemoryBlacklist()
        bl.block("jti-x", 60)
        bl._d["jti-x"] = time.time() - 1   # geçmişe çek → süresi dolmuş
        assert bl.is_blocked("jti-x") is False
        assert "jti-x" not in bl._d        # tembel temizlik

    def test_gc_drops_expired(self):
        bl = _InMemoryBlacklist()
        for i in range(300):
            bl._d[f"old-{i}"] = time.time() - 10   # hepsi expired
        bl.block("fresh", 60)                        # GC tetiklenir (>256)
        assert bl.is_blocked("fresh") is True
        assert len(bl._d) < 300


class TestPublicAPI:
    def setup_method(self):
        reset_for_tests()

    def teardown_method(self):
        reset_for_tests()

    def test_block_token_and_is_blocked(self):
        block_token("abc", time.time() + 60)
        assert is_blocked("abc") is True

    def test_empty_jti_guards(self):
        assert is_blocked("") is False
        assert is_blocked(None) is False
        block_token("", time.time() + 60)   # no-op, raise etmemeli
        assert is_blocked("x") is False

    def test_already_expired_block(self):
        block_token("old", time.time() - 5)  # ttl negatif → min 1sn; pratikte ~hemen geçer
        # En azından raise etmemeli ve bilinmeyen jti False dönmeli
        assert is_blocked("different") is False
