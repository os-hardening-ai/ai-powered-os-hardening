"""
Unit tests for evaluation.survey_eval pure scoring functions (no LLM, deterministic).

The user study itself needs real participants, but the scoring logic (İP-12 satisfaction,
H2 decision-time reduction, H4 acceptance) is pure — that is the trusted part and is
unit-tested here (mirrors test_ip_metrics / test_load_test).
"""

from __future__ import annotations

from evaluation.survey_eval import (
    satisfaction_rate,
    acceptance_rate,
    decision_times,
    summarize,
    to_markdown,
    SAT_TARGET,
)


class TestSatisfactionRate:
    def test_all_satisfied(self):
        surveys = [{"usefulness": 5, "trust": 4, "clarity": 5, "would_use_again": 4,
                    "overall_satisfaction": 5}]
        assert satisfaction_rate(surveys) == 1.0

    def test_none_satisfied(self):
        surveys = [{"usefulness": 2, "trust": 3, "clarity": 1, "would_use_again": 2,
                    "overall_satisfaction": 3}]
        assert satisfaction_rate(surveys) == 0.0

    def test_mixed(self):
        # 2 of 4 answers ≥4
        surveys = [{"usefulness": 5, "trust": 2}, {"clarity": 4, "would_use_again": 1}]
        assert satisfaction_rate(surveys) == 0.5

    def test_threshold_boundary_inclusive(self):
        assert satisfaction_rate([{"usefulness": 4}], threshold=4) == 1.0
        assert satisfaction_rate([{"usefulness": 4}], threshold=5) == 0.0

    def test_empty(self):
        assert satisfaction_rate([]) == 0.0

    def test_ignores_non_numeric(self):
        assert satisfaction_rate([{"usefulness": "n/a", "trust": 5}]) == 1.0


class TestAcceptanceRate:
    def _p(self, *verdicts):
        return [{"tasks": [{"recommendations": [{"id": str(i), "verdict": v}
                                                 for i, v in enumerate(verdicts)]}]}]

    def test_all_accept(self):
        assert acceptance_rate(self._p("accept", "accept")) == 1.0

    def test_all_reject(self):
        assert acceptance_rate(self._p("reject", "reject")) == 0.0

    def test_modify_is_half(self):
        assert acceptance_rate(self._p("modify", "modify")) == 0.5

    def test_weighted_mix(self):
        # accept(1) + modify(0.5) + reject(0) = 1.5 / 3 = 0.5
        assert acceptance_rate(self._p("accept", "modify", "reject")) == 0.5

    def test_case_insensitive_and_unknown(self):
        # ACCEPT counts; unknown verdict → 0 credit
        assert acceptance_rate(self._p("ACCEPT", "weird")) == 0.5

    def test_empty(self):
        assert acceptance_rate([]) == 0.0


class TestDecisionTimes:
    def test_reduction_computed(self):
        parts = [{"tasks": [{"decision_time_baseline_s": 200, "decision_time_with_tool_s": 50}]}]
        dt = decision_times(parts)
        assert dt["mean_baseline_s"] == 200.0
        assert dt["mean_with_tool_s"] == 50.0
        assert dt["reduction_pct"] == 0.75

    def test_no_baseline_zero_reduction(self):
        parts = [{"tasks": [{"decision_time_with_tool_s": 50}]}]
        dt = decision_times(parts)
        assert dt["n_baseline"] == 0
        assert dt["reduction_pct"] == 0.0

    def test_averages_across_tasks(self):
        parts = [{"tasks": [
            {"decision_time_with_tool_s": 40, "decision_time_baseline_s": 100},
            {"decision_time_with_tool_s": 60, "decision_time_baseline_s": 200},
        ]}]
        dt = decision_times(parts)
        assert dt["mean_with_tool_s"] == 50.0
        assert dt["mean_baseline_s"] == 150.0


class TestSummarize:
    def _data(self, sat_vals, verdicts, base, tool, example=False):
        return {"participants": [{
            "id": "P1", "example": example,
            "tasks": [{"decision_time_baseline_s": base, "decision_time_with_tool_s": tool,
                       "recommendations": [{"id": str(i), "verdict": v} for i, v in enumerate(verdicts)]}],
            "survey": {f: v for f, v in zip(
                ("usefulness", "trust", "clarity", "would_use_again", "overall_satisfaction"), sat_vals)},
        }]}

    def test_passing_study(self):
        s = summarize(self._data([5, 5, 4, 4, 5], ["accept", "accept"], 200, 50))
        assert s["ip12_satisfaction"]["passed"] is True
        assert s["ip12_satisfaction"]["rate"] >= SAT_TARGET
        assert s["h2_supported"] is True
        assert s["h4_acceptance"]["rate"] == 1.0
        assert s["n_participants"] == 1
        assert s["small_sample"] is True          # n=1 < 5

    def test_failing_satisfaction(self):
        s = summarize(self._data([2, 2, 3, 1, 2], ["reject"], 100, 90))
        assert s["ip12_satisfaction"]["passed"] is False

    def test_example_rows_skipped(self):
        s = summarize(self._data([5, 5, 5, 5, 5], ["accept"], 200, 50, example=True))
        assert s["n_participants"] == 0           # example filtered out
        assert s["ip12_satisfaction"]["rate"] == 0.0


class TestMarkdown:
    def test_renders_all_three_items(self):
        s = summarize({"participants": [{
            "id": "P1",
            "tasks": [{"decision_time_baseline_s": 200, "decision_time_with_tool_s": 50,
                       "recommendations": [{"id": "r1", "verdict": "accept"}]}],
            "survey": {"usefulness": 5, "trust": 4, "clarity": 4, "would_use_again": 5,
                       "overall_satisfaction": 4},
        }]})
        md = to_markdown(s)
        assert "İP-12" in md and "H2" in md and "H4" in md
        assert "küçük örneklem" in md            # n=1 honesty flag
