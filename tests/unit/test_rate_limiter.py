"""
Tests for the rate limiter — in-memory + Redis-backed (graceful fallback).

Previously: in-memory only, per-process, and the client IP came from the
spoofable X-Forwarded-For header. Now: Redis-backed when available (distributed,
restart-persistent), XFF trusted only behind a configured proxy, standard JSON
429. Redis is faked — no server needed.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.security import (
    RateLimitConfig,
    RateLimitMiddleware,
    _InMemoryRateLimiter,
    _RedisRateLimiter,
)


class TestInMemoryLimiter:
    def test_allows_then_blocks_at_minute_limit(self):
        cfg = RateLimitConfig(requests_per_minute=3, requests_per_hour=100)
        lim = _InMemoryRateLimiter(cfg)
        now = 1000.0
        assert all(lim.allow("ip1", now) for _ in range(3))  # 3 allowed
        assert lim.allow("ip1", now) is False                # 4th blocked

    def test_separate_clients_independent(self):
        cfg = RateLimitConfig(requests_per_minute=1, requests_per_hour=100)
        lim = _InMemoryRateLimiter(cfg)
        assert lim.allow("a", 1000.0) is True
        assert lim.allow("b", 1000.0) is True  # different client, own bucket
        assert lim.allow("a", 1000.0) is False

    def test_window_slides(self):
        cfg = RateLimitConfig(requests_per_minute=1, requests_per_hour=100)
        lim = _InMemoryRateLimiter(cfg)
        assert lim.allow("a", 1000.0) is True
        assert lim.allow("a", 1000.0) is False
        assert lim.allow("a", 1000.0 + 61) is True  # next minute window


class _FakePipeline:
    def __init__(self, store, fail=False):
        self._store = store
        self._ops = []
        self._fail = fail

    def incr(self, key):
        self._ops.append(("incr", key))

    def expire(self, key, ttl):
        self._ops.append(("expire", key))

    def execute(self):
        if self._fail:
            raise RuntimeError("redis down")
        out = []
        for op, key in self._ops:
            if op == "incr":
                self._store[key] = self._store.get(key, 0) + 1
                out.append(self._store[key])
            else:
                out.append(True)
        return out


class _FakeRedis:
    def __init__(self, fail=False):
        self.store = {}
        self._fail = fail

    def pipeline(self):
        return _FakePipeline(self.store, fail=self._fail)


class TestRedisLimiter:
    def test_allows_under_limit_blocks_over(self):
        cfg = RateLimitConfig(requests_per_minute=2, requests_per_hour=100)
        lim = _RedisRateLimiter(_FakeRedis(), cfg)
        now = 1000.0
        assert lim.allow("ip", now) is True
        assert lim.allow("ip", now) is True
        assert lim.allow("ip", now) is False  # 3rd over per-minute limit

    def test_hour_limit_enforced(self):
        cfg = RateLimitConfig(requests_per_minute=100, requests_per_hour=2)
        lim = _RedisRateLimiter(_FakeRedis(), cfg)
        now = 1000.0
        assert lim.allow("ip", now) is True
        assert lim.allow("ip", now) is True
        assert lim.allow("ip", now) is False  # 3rd over per-hour limit

    def test_fails_open_on_redis_error(self):
        cfg = RateLimitConfig(requests_per_minute=1, requests_per_hour=1)
        lim = _RedisRateLimiter(_FakeRedis(fail=True), cfg)
        # Redis errors must not block traffic
        assert lim.allow("ip", 1000.0) is True
        assert lim.allow("ip", 1000.0) is True


class TestMiddlewareIntegration:
    @pytest.fixture(autouse=True)
    def _force_in_memory(self, monkeypatch):
        # Avoid the real Redis ping (2s timeout) during middleware construction.
        import api.security as sec
        monkeypatch.setattr(
            sec, "_build_rate_limiter", lambda cfg: _InMemoryRateLimiter(cfg)
        )

    def test_returns_429_json_when_exceeded(self):
        cfg = RateLimitConfig(requests_per_minute=2, requests_per_hour=100)
        app = FastAPI()

        @app.get("/ping")
        def ping():
            return {"ok": True}

        app.add_middleware(RateLimitMiddleware, config=cfg)
        client = TestClient(app)
        assert client.get("/ping").status_code == 200
        assert client.get("/ping").status_code == 200
        r3 = client.get("/ping")
        assert r3.status_code == 429
        assert r3.json()["error"]["code"] == "RATE_LIMITED"
        assert r3.headers.get("Retry-After") == "60"

    def test_ip_ignores_xff_without_trust_proxy(self, monkeypatch):
        monkeypatch.delenv("TRUST_PROXY", raising=False)
        mw = RateLimitMiddleware(FastAPI(), config=RateLimitConfig())

        class _Req:
            headers = {"x-forwarded-for": "1.2.3.4"}
            class client:
                host = "10.0.0.1"

        assert mw._get_client_ip(_Req()) == "10.0.0.1"  # real peer, not XFF

    def test_ip_uses_xff_with_trust_proxy(self, monkeypatch):
        monkeypatch.setenv("TRUST_PROXY", "1")
        mw = RateLimitMiddleware(FastAPI(), config=RateLimitConfig())

        class _Req:
            headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
            class client:
                host = "10.0.0.1"

        assert mw._get_client_ip(_Req()) == "1.2.3.4"  # leftmost XFF when trusted
