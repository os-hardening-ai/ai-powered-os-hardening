"""
Unit tests for llm.agents.task_planner.TaskPlanner (İP-6 Görev Planlayıcı).

Real RuleEngine (tmp YAML fixture) + ArtifactGenerator are exercised; the LLM
selection step is faked. Covers deterministic fallback, LLM-driven selection,
ordering, conflict surfacing and security-level → CIS-level mapping.
"""

from __future__ import annotations

import json
import textwrap

import pytest

from domain.rule_engine.rule_engine import RuleEngine
from llm.agents.task_planner import TaskPlanner, HardeningPlan, PlanItem


RULES_YAML = textwrap.dedent("""
rules:
  - id: "1.1.1"
    title: "Disable SSH root login"
    level: 1
    category: "ssh"
    zt_principle: "least_privilege"
    nist_ref: "AC-6"
    config_files: ["/etc/ssh/sshd_config"]
    remediation_script_content: "sed -i 's/^PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config"
  - id: "1.1.3"
    title: "Set SSH MaxAuthTries"
    level: 1
    category: "ssh"
    zt_principle: "continuous_verification"
    nist_ref: "AC-7"
    config_files: ["/etc/ssh/sshd_config"]
    remediation_script_content: "echo 'MaxAuthTries 4' >> /etc/ssh/sshd_config"
  - id: "1.2.1"
    title: "Password minimum length 14"
    level: 1
    category: "password"
    zt_principle: "strong_identity"
    nist_ref: "IA-5"
    config_files: ["/etc/login.defs"]
    remediation_script_content: "echo 'PASS_MIN_LEN 14' >> /etc/login.defs"
  - id: "2.3.1"
    title: "Advanced audit policy"
    level: 2
    category: "audit"
    zt_principle: "visibility_and_analytics"
    nist_ref: "AU-2"
    remediation_script_content: "auditctl -e 1"
""").strip()


@pytest.fixture
def engine(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text(RULES_YAML, encoding="utf-8")
    return RuleEngine(p)


class TestDeterministicPlan:
    def test_plan_without_llm_uses_all_candidates(self, engine):
        planner = TaskPlanner(rule_engine=engine, llm_fn=None)
        plan = planner.plan("SSH sıkılaştır", os_target="ubuntu_24_04", security_level="balanced")
        assert isinstance(plan, HardeningPlan)
        # balanced -> level 1 only (3 rules), level 2 excluded
        ids = [i.rule_id for i in plan.items]
        assert "2.3.1" not in ids
        assert set(ids) == {"1.1.1", "1.1.3", "1.2.1"}

    def test_strict_includes_level2(self, engine):
        planner = TaskPlanner(rule_engine=engine, llm_fn=None)
        plan = planner.plan("tam sıkılaştırma", security_level="strict")
        ids = [i.rule_id for i in plan.items]
        assert "2.3.1" in ids  # level 2 included under strict

    def test_items_ordered_by_section(self, engine):
        planner = TaskPlanner(rule_engine=engine, llm_fn=None)
        plan = planner.plan("hepsi", security_level="strict")
        orders = [i.order for i in plan.items]
        assert orders == sorted(orders)
        ids = [i.rule_id for i in plan.items]
        assert ids == sorted(ids, key=lambda r: tuple(int(x) for x in r.split(".")))

    def test_metadata_enriched(self, engine):
        planner = TaskPlanner(rule_engine=engine, llm_fn=None)
        plan = planner.plan("ssh", security_level="balanced")
        ssh = next(i for i in plan.items if i.rule_id == "1.1.1")
        assert ssh.zt_principle == "least_privilege"
        assert ssh.nist_ref == "AC-6"


class TestConflict:
    def test_conflict_detected_for_same_config_file(self, engine):
        planner = TaskPlanner(rule_engine=engine, llm_fn=None)
        plan = planner.plan("ssh", security_level="balanced")
        # 1.1.1 and 1.1.3 both write /etc/ssh/sshd_config
        assert any(
            {c.rule_a, c.rule_b} == {"1.1.1", "1.1.3"} for c in plan.conflicts
        )
        assert plan.warnings


class TestLLMSelection:
    def test_llm_selects_subset_with_priority(self, engine):
        selection = json.dumps([
            {"rule_id": "1.1.1", "priority": 1, "risk": "high", "rationale": "root login en kritik"},
            {"rule_id": "1.2.1", "priority": 2, "risk": "medium", "rationale": "parola politikası"},
        ])
        planner = TaskPlanner(rule_engine=engine, llm_fn=lambda _p: selection)
        plan = planner.plan("ssh ve parola", security_level="balanced")
        ids = {i.rule_id for i in plan.items}
        assert ids == {"1.1.1", "1.2.1"}  # only LLM-selected rules
        item = next(i for i in plan.items if i.rule_id == "1.1.1")
        assert item.priority == 1
        assert item.risk == "high"
        assert "root login" in item.rationale

    def test_llm_garbage_falls_back_to_all(self, engine):
        planner = TaskPlanner(rule_engine=engine, llm_fn=lambda _p: "not json at all")
        plan = planner.plan("ssh", security_level="balanced")
        assert len(plan.items) == 3  # fallback: all level-1 candidates

    def test_llm_unknown_ids_ignored(self, engine):
        selection = json.dumps([{"rule_id": "9.9.9", "priority": 1}])  # not in engine
        planner = TaskPlanner(rule_engine=engine, llm_fn=lambda _p: selection)
        plan = planner.plan("ssh", security_level="balanced")
        # unknown id dropped -> selection empty -> fallback to all
        assert len(plan.items) == 3


class TestRelevanceRanking:
    """İP-6 latency+doğruluk: adaylar LLM'e gönderilmeden önce hedefe göre sıralanır."""

    def test_ranking_surfaces_goal_relevant_rules_first(self, engine):
        planner = TaskPlanner(rule_engine=engine, llm_fn=None)
        candidates = planner._candidate_rules("strict")  # 4 rule
        ranked = planner._rank_candidates("audit denetim", candidates)
        # 'audit' kategorili 2.3.1 en üste çıkmalı (kategori+başlık+tag eşleşmesi)
        assert ranked[0]["id"] == "2.3.1"

    def test_turkish_goal_matches_english_rule_via_synonyms(self, engine):
        planner = TaskPlanner(rule_engine=engine, llm_fn=None)
        candidates = planner._candidate_rules("balanced")
        # "parola" (TR) → "password" (EN) sinonimiyle 1.2.1 öne çekilmeli
        ranked = planner._rank_candidates("parola sıkılaştır", candidates)
        assert ranked[0]["id"] == "1.2.1"

    def test_ranking_preserves_all_candidates(self, engine):
        planner = TaskPlanner(rule_engine=engine, llm_fn=None)
        candidates = planner._candidate_rules("strict")
        ranked = planner._rank_candidates("alakasız hedef xyz", candidates)
        # eşleşme olmasa bile hiçbir aday düşmez (recall korunur)
        assert {r["id"] for r in ranked} == {r["id"] for r in candidates}

    def test_llm_pool_capped_relevant_subset(self, engine):
        """LLM'e giden aday sayısı _LLM_CANDIDATES ile sınırlı ve alaka-öncelikli."""
        captured = {}

        def fake_llm(prompt: str) -> str:
            captured["prompt"] = prompt
            return "[]"  # boş → fallback, ama prompt'u yakaladık

        planner = TaskPlanner(rule_engine=engine, llm_fn=fake_llm)
        planner.plan("ssh", security_level="balanced")
        # SSH kuralları (1.1.1, 1.1.3) prompt'ta görünmeli
        assert "1.1.1" in captured["prompt"]
        assert "1.1.3" in captured["prompt"]


class TestSerialization:
    def test_to_dict(self, engine):
        plan = TaskPlanner(rule_engine=engine, llm_fn=None).plan("ssh", security_level="balanced")
        d = plan.to_dict()
        assert d["goal"] == "ssh"
        assert isinstance(d["items"], list) and d["items"]
        assert "summary" in d
