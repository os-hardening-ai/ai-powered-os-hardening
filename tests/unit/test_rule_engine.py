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
          - id: "5.2.10"
            title: "SSH MaxAuthTries 4"
            config_files: ["/etc/ssh/sshd_config"]
            sshd_directive: "MaxAuthTries"
            expected_value: "4"
          - id: "5.2.11"
            title: "SSH MaxAuthTries 3 (stricter — gerçek çelişki)"
            config_files: ["/etc/ssh/sshd_config"]
            sshd_directive: "MaxAuthTries"
            expected_value: "3"
          - id: "5.2.12"
            title: "SSH PermitRootLogin no (farklı direktif — çakışma değil)"
            config_files: ["/etc/ssh/sshd_config"]
            sshd_directive: "PermitRootLogin"
            expected_value: "no"
          - id: "1.1.1.1"
            title: "cramfs disabled"
            config_files: ["/etc/modprobe.d"]
            kernel_module: "cramfs"
          - id: "1.1.1.2"
            title: "freevxfs disabled"
            config_files: ["/etc/modprobe.d"]
            kernel_module: "freevxfs"
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
    def test_same_directive_different_value_is_real_conflict(self, engine):
        # AYNI sshd_directive (MaxAuthTries) FARKLI değer (4 vs 3) → gerçek çakışma
        conflicts = engine.detect_conflicts(["5.2.10", "5.2.11"])
        cf = [c for c in conflicts if c.conflict_type == "config_file"]
        assert len(cf) == 1
        assert {cf[0].rule_a, cf[0].rule_b} == {"5.2.10", "5.2.11"}
        assert cf[0].resource == "/etc/ssh/sshd_config"

    def test_same_file_different_directive_is_NOT_conflict(self, engine):
        # Aynı dosya (sshd_config) FARKLI direktif (MaxAuthTries vs PermitRootLogin) →
        # birlikte yaşar → çakışma DEĞİL (sıra notu olur)
        conflicts = engine.detect_conflicts(["5.2.10", "5.2.12"])
        assert conflicts == []

    def test_same_file_no_directive_is_NOT_conflict(self, engine):
        # 1.1.10 ve 1.1.2 ikisi de /etc/fstab'a yazar ama farklı girdiler (ayrı bölümler)
        # → çakışma DEĞİL (eski davranış bunu yanlışlıkla çakışma sayıyordu)
        conflicts = engine.detect_conflicts(["1.1.10", "1.1.2", "5.2.1"])
        assert conflicts == []

    def test_different_kernel_modules_sharing_dir_NOT_conflict(self, engine):
        # cramfs ve freevxfs ikisi de /etc/modprobe.d paylaşır ama FARKLI modüller →
        # bağımsız (ayrı dosyalar) → çakışma DEĞİL (asıl gürültü kaynağı buydu)
        conflicts = engine.detect_conflicts(["1.1.1.1", "1.1.1.2"])
        assert conflicts == []

    def test_same_kernel_module_is_real_conflict(self, engine):
        conflicts = engine.detect_conflicts(["3.4.1", "3.4.2"])
        km = [c for c in conflicts if c.conflict_type == "kernel_module"]
        assert len(km) == 1
        assert km[0].resource == "dccp"

    def test_no_conflict_for_disjoint_rules(self, engine):
        conflicts = engine.detect_conflicts(["5.2.1", "3.4.1"])
        assert conflicts == []

    def test_unknown_ids_ignored(self, engine):
        conflicts = engine.detect_conflicts(["5.2.1", "does.not.exist"])
        assert conflicts == []


class TestOrderNotes:
    def test_same_file_different_settings_is_order_note(self, engine):
        # /etc/fstab'a yazan 2 kural → 1 toplu sıra notu (çift-çift değil)
        notes = engine.detect_order_notes(["1.1.10", "1.1.2"])
        assert len(notes) == 1
        assert "/etc/fstab" in notes[0]
        assert "1.1.2" in notes[0] and "1.1.10" in notes[0]
        assert "çakışma değil" in notes[0].lower()

    def test_kernel_module_rules_produce_no_order_note(self, engine):
        # modprobe.d bağımsız kuralları → sıra notu YOK
        notes = engine.detect_order_notes(["1.1.1.1", "1.1.1.2"])
        assert notes == []

    def test_single_rule_no_order_note(self, engine):
        assert engine.detect_order_notes(["1.1.10"]) == []


class TestOrdering:
    def test_resolve_order_is_numeric_not_lexicographic(self, engine):
        # Lexicographic would put "1.1.10" before "1.1.2"; numeric must not.
        ordered = engine.resolve_order(["5.2.1", "1.1.10", "1.1.2", "3.4.1"])
        assert ordered == ["1.1.2", "1.1.10", "3.4.1", "5.2.1"]

    def test_resolve_order_drops_unknown(self, engine):
        ordered = engine.resolve_order(["5.2.1", "nope"])
        assert ordered == ["5.2.1"]


class TestExecutionPlan:
    def test_plan_same_file_is_order_note_not_conflict(self, engine):
        plan = engine.get_execution_plan(["1.1.10", "1.1.2"])
        assert isinstance(plan, ExecutionPlan)
        assert plan.ordered_rules == ["1.1.2", "1.1.10"]
        assert len(plan.conflicts) == 0  # çakışma değil
        assert len(plan.warnings) == 1
        assert plan.warnings[0].startswith("Sıra notu:")
        assert "/etc/fstab" in plan.warnings[0]

    def test_plan_real_conflict_is_flagged(self, engine):
        plan = engine.get_execution_plan(["5.2.10", "5.2.11"])
        assert len(plan.conflicts) == 1
        conflict_warnings = [w for w in plan.warnings if w.startswith("ÇAKIŞMA:")]
        assert len(conflict_warnings) == 1
        assert "MaxAuthTries" in conflict_warnings[0]


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
