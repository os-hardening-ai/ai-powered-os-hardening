"""
Unit tests for evaluation.provider_benchmark (no network — fake clients).

The benchmark's value is empirical (real API latency), but its pure logic — skip-on-no-key,
reachability detection, aggregation, sorting, markdown — is deterministic and tested here.
"""

from __future__ import annotations

import evaluation.provider_benchmark as pb
from evaluation.provider_benchmark import ProviderResult, to_markdown, _sort_key, bench_provider


class _FakeClient:
    def __init__(self, content="ok answer", exc=None, model_name="fake-model"):
        self.model_name = model_name
        self._content = content
        self._exc = exc

    def __call__(self, prompt):
        if self._exc:
            raise self._exc
        return self._content


class TestPercentile:
    def test_delegates(self):
        from api.metrics import MetricsCollector
        data = [0.1, 0.2, 0.3, 0.4]
        assert pb._percentile(data, 0.95) == round(MetricsCollector._percentile(sorted(data), 0.95), 3)

    def test_empty_is_zero(self):
        assert pb._percentile([], 0.5) == 0.0


class TestBenchProvider:
    def test_no_key_skipped(self, monkeypatch):
        monkeypatch.setattr(pb, "preset_api_key", lambda p: "")
        r = bench_provider("cerebras", 3, "prompt")
        assert r.has_key is False and r.reachable is False
        assert "key yok" in r.error.lower()
        assert r.n == 0

    def test_reachable_aggregates(self, monkeypatch):
        monkeypatch.setattr(pb, "preset_api_key", lambda p: "k")
        monkeypatch.setattr(pb, "build_from_preset", lambda p, **kw: _FakeClient("hardening steps"))
        r = bench_provider("cerebras", 4, "prompt")
        assert r.has_key and r.reachable
        assert r.ok == 4 and r.n == 4
        assert r.passed_h3 is True            # fake = instant ⇒ p95 < 5s
        assert r.sample.startswith("hardening")

    def test_warmup_error_marks_unreachable(self, monkeypatch):
        monkeypatch.setattr(pb, "preset_api_key", lambda p: "k")
        monkeypatch.setattr(pb, "build_from_preset",
                            lambda p, **kw: _FakeClient(exc=RuntimeError("401 unauthorized")))
        r = bench_provider("cerebras", 3, "prompt")
        assert r.has_key and r.reachable is False
        assert "401" in r.error or "unauthorized" in r.error.lower()

    def test_setup_error_handled(self, monkeypatch):
        monkeypatch.setattr(pb, "preset_api_key", lambda p: "k")
        def _boom(p, **kw):
            raise ValueError("bad base_url")
        monkeypatch.setattr(pb, "build_from_preset", _boom)
        r = bench_provider("cerebras", 3, "prompt")
        assert r.reachable is False and "kurulum" in r.error.lower()


class TestMatrix:
    def test_parse_matrix(self):
        pairs = pb._parse_matrix("cerebras:gpt-oss-120b; groq:llama-3.3-70b ;bad-no-colon")
        assert pairs == [("cerebras", "gpt-oss-120b"), ("groq", "llama-3.3-70b")]

    def test_default_matrix_well_formed(self):
        assert len(pb.DEFAULT_MATRIX) >= 4
        for prov, model in pb.DEFAULT_MATRIX:
            assert prov in pb.PROVIDER_PRESETS and isinstance(model, str) and model

    def test_bench_pair_passes_explicit_model(self, monkeypatch):
        captured = {}

        def _bfp(provider, **kw):
            captured["model"] = kw.get("model")
            return _FakeClient("answer", model_name=kw.get("model") or "default")

        monkeypatch.setattr(pb, "preset_api_key", lambda p: "k")
        monkeypatch.setattr(pb, "build_from_preset", _bfp)
        r = bench_provider  # ensure wrapper still importable
        res = pb.bench_pair("cerebras", "gpt-oss-120b", 2, "prompt")
        assert captured["model"] == "gpt-oss-120b"
        assert res.model == "gpt-oss-120b" and res.reachable

    def test_bench_provider_wrapper_uses_preset(self, monkeypatch):
        captured = {}

        def _bfp(provider, **kw):
            captured["model"] = kw.get("model")
            return _FakeClient("answer", model_name="preset-model")

        monkeypatch.setattr(pb, "preset_api_key", lambda p: "k")
        monkeypatch.setattr(pb, "build_from_preset", _bfp)
        bench_provider("cerebras", 2, "prompt")
        assert captured["model"] is None      # wrapper → preset/env default


class TestSortAndMarkdown:
    def _results(self):
        return [
            ProviderResult("slow", "m", True, True, 5, 5, 8.0, 12.0, 9.0, passed_h3=False),
            ProviderResult("fast", "m", True, True, 5, 5, 1.0, 2.0, 1.2, passed_h3=True),
            ProviderResult("down", "m", True, False, 0, 0, error="timeout"),
            ProviderResult("nokey", "m", False, False, error="API key yok (atlandı)"),
        ]

    def test_sort_reachable_by_p95_then_unreachable_then_nokey(self):
        ordered = sorted(self._results(), key=_sort_key)
        names = [r.provider for r in ordered]
        assert names == ["fast", "slow", "down", "nokey"]

    def test_markdown_renders_all(self):
        md = to_markdown(self._results())
        for name in ("fast", "slow", "down", "nokey"):
            assert name in md
        assert "H3" in md
        assert "En hızlı" in md          # fast passed_h3 ⇒ recommendation line

    def test_markdown_warns_when_none_pass(self):
        md = to_markdown([ProviderResult("a", "m", True, True, 5, 5, 9.0, 12.0, 10.0, passed_h3=False)])
        assert "Hiçbir sağlayıcı H3" in md
