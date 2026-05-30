"""
Unit tests for domain.rule_engine.RuleEngine

Covers:
- Rule loading from YAML
- Conflict detection (config_file + kernel_module overlap)
- Dependency ordering (topological sort by CIS section number)
- Execution plan generation
- Rule lookup and filtered listing

No network / external services required — uses a tmp YAML fixture.
"""

from __future__ import annotations

import textwrap

import pytest

from domain.rule_engine.rule_engine import RuleEngine, RuleConflict, ExecutionPlan


@pytest.fixture
def rules_yaml(tmp_path):
    """Write a small, deterministic rules file and return its path."""
    content = textwrap.dedent(
        """
        rules:
          - id: "1.1.10"
            title: "Ensure /var/tmp is separate"
            level: 2
            category: "filesystem"
            config_files: ["/etc/fstab"]
            auto_remediate: false
          - id: "1.1.2"
            title: "Ensure /tmp is configured"
            level: 1
            category: "filesystem"
            config_files: ["/etc/fstab"]
            auto_remediate: true
          - id: "5.2.1"
            title: "Ensure SSH permissions"
            level: 1
            category: "ssh"
            config_files: ["/etc/ssh/sshd_config"]
            auto_remediate: true
          - id: "3.4.1"
            title: "Disable dccp"
            level: 1
            category: "network"
            kernel_module: "dccp"
            auto_remediate: true
          - id: "3.4.2"
            title: "Restrict dccp again"
            level: 2
            category: "network"
            kernel_module: "dccp"
            auto_remediate: false
        """
    ).strip()
    path = tmp_path / "rules.yaml"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def engine(rules_yaml):
    return RuleEngine(rules_yaml)


class TestLoading:
    def test_lazy_load_and_get_rule(self, engine):
        rule = engine.get_rule("5.2.1")
        assert rule is not None
        assert rule["title"] == "Ensure SSH permissions"

    def test_unknown_rule_returns_none(self, engine):
        assert engine.get_rule("9.9.9") is None


class TestConflictDetection:
    def test_config_file_overlap_detected(self, engine):
        conflicts = engine.detect_conflicts(["1.1.10", "1.1.2", "5.2.1"])
        cf = [c for c in conflicts if c.conflict_type == "config_file"]
        # 1.1.10 and 1.1.2 both touch /etc/fstab -> exactly one conflict
        assert len(cf) == 1
        pair = {cf[0].rule_a, cf[0].rule_b}
        assert pair == {"1.1.10", "1.1.2"}
        assert cf[0].resource == "/etc/fstab"

    def test_kernel_module_overlap_detected(self, engine):
        conflicts = engine.detect_conflicts(["3.4.1", "3.4.2"])
        km = [c for c in conflicts if c.conflict_type == "kernel_module"]
        assert len(km) == 1
        assert km[0].resource == "dccp"

    def test_no_conflict_for_disjoint_rules(self, engine):
        conflicts = engine.detect_conflicts(["5.2.1", "3.4.1"])
        assert conflicts == []

    def test_unknown_ids_ignored(self, engine):
        # Should not raise even with unknown ids mixed in
        conflicts = engine.detect_conflicts(["5.2.1", "does.not.exist"])
        assert conflicts == []


class TestOrdering:
    def test_resolve_order_is_numeric_not_lexicographic(self, engine):
        # Lexicographic would put "1.1.10" before "1.1.2"; numeric must not.
        ordered = engine.resolve_order(["5.2.1", "1.1.10", "1.1.2", "3.4.1"])
        assert ordered == ["1.1.2", "1.1.10", "3.4.1", "5.2.1"]

    def test_resolve_order_drops_unknown(self, engine):
        ordered = engine.resolve_order(["5.2.1", "nope"])
        assert ordered == ["5.2.1"]


class TestExecutionPlan:
    def test_plan_has_order_conflicts_and_warnings(self, engine):
        plan = engine.get_execution_plan(["1.1.10", "1.1.2"])
        assert isinstance(plan, ExecutionPlan)
        assert plan.ordered_rules == ["1.1.2", "1.1.10"]
        assert len(plan.conflicts) == 1
        assert len(plan.warnings) == 1
        assert "/etc/fstab" in plan.warnings[0]


class TestListRules:
    def test_filter_by_level(self, engine):
        lvl1 = engine.list_rules(level=1)
        ids = {r["id"] for r in lvl1}
        assert ids == {"1.1.2", "5.2.1", "3.4.1"}

    def test_filter_by_category(self, engine):
        net = engine.list_rules(category="network")
        assert {r["id"] for r in net} == {"3.4.1", "3.4.2"}

    def test_filter_by_auto_remediate(self, engine):
        auto = engine.list_rules(auto_remediate=True)
        assert {r["id"] for r in auto} == {"1.1.2", "5.2.1", "3.4.1"}
