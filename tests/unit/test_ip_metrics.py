"""
Unit tests for evaluation.ip_metrics pure scoring functions (no LLM, deterministic).

The live measurement needs Novita+Qdrant, but the scoring logic + report aggregation
are pure — that is the trusted part, so it is unit-tested here (mirrors test_h1_harness).
"""

from __future__ import annotations

import pytest

from evaluation.ip_metrics import (
    ordering_score,
    selection_precision,
    zt_principle_valid,
    has_standard_ref,
    steps_complete,
    IP6Sample, IP7Sample, IP8Sample, IP5Sample, IPReport,
)


class TestOrderingScore:
    def test_monotonic_from_one(self):
        assert ordering_score([1, 2, 3, 4]) == 1.0

    def test_not_sorted(self):
        assert ordering_score([1, 3, 2]) == 0.0

    def test_empty(self):
        assert ordering_score([]) == 0.0

    def test_must_start_at_one(self):
        assert ordering_score([2, 3, 4]) == 0.0


class TestSelectionPrecision:
    def test_all_in_expected_section(self):
        assert selection_precision(["5.1.1", "5.1.2", "5.3.1"], ["5"]) == 1.0

    def test_half(self):
        assert selection_precision(["5.1.1", "1.2.3"], ["5"]) == 0.5

    def test_multi_prefix(self):
        # 1.x, 3.x, 4.x hepsi beklenen
        assert selection_precision(["1.1", "3.2", "4.5"], ["1", "3", "4"]) == 1.0

    def test_empty_is_zero(self):
        assert selection_precision([], ["5"]) == 0.0


class TestZTPrinciple:
    def test_valid_principle(self):
        assert zt_principle_valid(["least_privilege"]) is True

    def test_hyphen_and_space_normalized(self):
        assert zt_principle_valid(["Micro-Segmentation"]) is True
        assert zt_principle_valid(["continuous verification"]) is True

    def test_invalid(self):
        assert zt_principle_valid(["totally_made_up"]) is False

    def test_empty(self):
        assert zt_principle_valid([]) is False


class TestStandardRef:
    @pytest.mark.parametrize("std", [
        "NIST_800-53:AC-2", "CIS_Ubuntu_22_04:5.2.5", "ISO_27001:A.9.2.3",
        "NIST_800-207:3.2",
    ])
    def test_valid_refs(self, std):
        assert has_standard_ref([std]) is True

    def test_no_ref(self):
        assert has_standard_ref(["just some text", "least_privilege"]) is False

    def test_empty(self):
        assert has_standard_ref([]) is False


class TestStepsComplete:
    def test_all_present(self):
        assert steps_complete(["plan", "collect", "generate", "verify", "summarize"]) is True

    def test_missing_verify(self):
        assert steps_complete(["plan", "collect", "generate"]) is False

    def test_custom_required(self):
        assert steps_complete(["a", "b"], required=["a"]) is True


class TestReportAggregation:
    def test_ip6_ordering_pass_rate(self):
        rep = IPReport(ip6=[
            IP6Sample("g1", ["5.1"], ordering_ok=1.0, selection_prec=1.0, n_items=3, n_conflicts=0),
            IP6Sample("g2", ["5.2"], ordering_ok=1.0, selection_prec=0.5, n_items=2, n_conflicts=1),
            IP6Sample("g3", ["1.1"], ordering_ok=0.0, selection_prec=0.0, n_items=1, n_conflicts=0),
        ])
        s = rep.summary()
        assert s["ip6"]["n"] == 3
        assert s["ip6"]["ordering_pass_rate"] == pytest.approx(2 / 3, abs=1e-3)
        assert s["ip6"]["avg_selection_precision"] == pytest.approx(0.5, abs=1e-3)

    def test_ip7_rates(self):
        rep = IPReport(ip7=[
            IP7Sample("g1", success=True, steps_ok=True, verify_present=True, all_steps_ok_flag=True, n_steps=6),
            IP7Sample("g2", success=False, steps_ok=True, verify_present=True, all_steps_ok_flag=False, n_steps=5),
        ])
        s = rep.summary()
        assert s["ip7"]["success_rate"] == pytest.approx(0.5)
        assert s["ip7"]["verify_gate_rate"] == pytest.approx(1.0)

    def test_ip8_combined(self):
        rep = IPReport(ip8=[
            IP8Sample("g1", principle_valid=True, standard_ref=True, principles=["least_privilege"], standards=["NIST:AC-2"]),
            IP8Sample("g2", principle_valid=True, standard_ref=False, principles=["least_privilege"], standards=["x"]),
        ])
        s = rep.summary()
        assert s["ip8"]["valid_principle_rate"] == pytest.approx(1.0)
        assert s["ip8"]["combined_rate"] == pytest.approx(0.5)

    def test_ip5_groundedness(self):
        rep = IPReport(ip5=[
            IP5Sample("g1", groundedness=1.0, is_grounded=True, n_chunks=5),
            IP5Sample("g2", groundedness=0.8, is_grounded=False, n_chunks=4),
        ])
        s = rep.summary()
        assert s["ip5"]["avg_groundedness"] == pytest.approx(0.9)
        assert s["ip5"]["grounded_rate"] == pytest.approx(0.5)

    def test_empty_report_safe(self):
        s = IPReport().summary()
        assert s["ip6"]["ordering_pass_rate"] == 0.0
        assert s["ip5"]["avg_groundedness"] == 0.0


class TestMarkdown:
    def test_renders(self):
        from evaluation.ip_metrics import to_markdown
        rep = IPReport(
            ip6=[IP6Sample("g", ["5.1"], 1.0, 1.0, 3, 0)],
            ip7=[IP7Sample("g", True, True, True, True, 6)],
            ip8=[IP8Sample("g", True, True, ["least_privilege"], ["NIST:AC-2"])],
            ip5=[IP5Sample("g", 0.95, True, 5)],
        )
        md = to_markdown(rep)
        assert "İP-5/6/7/8" in md
        assert "İP-6 Görev Planlayıcı" in md
