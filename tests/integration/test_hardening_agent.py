"""
Integration tests for llm.agents.hardening_agent.HardeningAgent (İP-7).

Drives the full multi-step tool chain with REAL RuleEngine + TaskPlanner +
ArtifactGenerator + OutputValidator (LLM faked/None). Verifies the step trace,
artifact generation, the self-verify gate and the observe→reason→re-act refine
loop that drops rules carrying dangerous commands.
"""

from __future__ import annotations

import textwrap

import pytest

from domain.rule_engine.rule_engine import RuleEngine
from llm.agents.hardening_agent import HardeningAgent, AgentResult

pytestmark = pytest.mark.integration


SAFE_RULES = """
  - id: "1.1.1"
    title: "Disable SSH root login"
    level: 1
    category: "ssh"
    zt_principle: "least_privilege"
    config_files: ["/etc/ssh/sshd_config"]
    remediation_script_content: "sed -i 's/^PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config"
  - id: "1.2.1"
    title: "Password minimum length"
    level: 1
    category: "password"
    remediation_script_content: "echo 'PASS_MIN_LEN 14' >> /etc/login.defs"
"""

DANGEROUS_RULE = """
  - id: "8.8.8"
    title: "Bad cleanup rule"
    level: 1
    category: "misc"
    remediation_script_content: "rm -rf / --no-preserve-root"
"""


def make_engine(tmp_path, body):
    p = tmp_path / "rules.yaml"
    p.write_text("rules:\n" + textwrap.dedent(body).strip("\n") + "\n", encoding="utf-8")
    return RuleEngine(p)


class TestHappyPath:
    def test_generates_verified_script(self, tmp_path):
        engine = make_engine(tmp_path, SAFE_RULES)
        agent = HardeningAgent(rule_engine=engine)  # llm_fn=None -> deterministic
        res = agent.run("SSH ve parola sıkılaştır", os_target="ubuntu_24_04",
                        security_level="balanced", fmt="bash")
        assert isinstance(res, AgentResult)
        assert res.success
        assert res.artifact is not None and res.artifact.rule_count == 2
        assert "PermitRootLogin no" in res.artifact.content
        # step trace covers the whole tool chain
        names = [s.name for s in res.steps]
        assert names[0] == "plan"
        assert "collect" in names and "generate" in names and "verify" in names
        assert names[-1] == "summarize"

    def test_ansible_format(self, tmp_path):
        engine = make_engine(tmp_path, SAFE_RULES)
        agent = HardeningAgent(rule_engine=engine)
        res = agent.run("hepsi", security_level="balanced", fmt="ansible")
        assert res.artifact.format == "ansible"
        assert "hosts: all" in res.artifact.content


class TestRefineLoop:
    def test_dangerous_rule_dropped_on_refine(self, tmp_path):
        engine = make_engine(tmp_path, SAFE_RULES + DANGEROUS_RULE)
        agent = HardeningAgent(rule_engine=engine, max_refine=1)
        res = agent.run("sıkılaştır", security_level="balanced", fmt="bash")

        # refine step must have fired
        assert any(s.name == "refine" for s in res.steps)
        # dangerous command must NOT survive in the final artifact
        assert "rm -rf /" not in res.artifact.content
        assert "8.8.8" not in res.artifact.content
        # safe rules remain and final output verifies clean
        assert "PermitRootLogin no" in res.artifact.content
        assert res.success

    def test_two_verify_steps_when_refined(self, tmp_path):
        engine = make_engine(tmp_path, SAFE_RULES + DANGEROUS_RULE)
        agent = HardeningAgent(rule_engine=engine, max_refine=1)
        res = agent.run("sıkılaştır", security_level="balanced")
        verify_steps = [s for s in res.steps if s.name == "verify"]
        assert len(verify_steps) == 2  # initial (fail) + post-refine (pass)
        assert verify_steps[0].ok is False
        assert verify_steps[1].ok is True


class TestSummarySync:
    """D bug regresyonu: refine'da kural çıkınca özet GERÇEK final sayıyı yansıtmalı."""

    def test_summary_reflects_post_refine_count_not_plan(self, tmp_path):
        # 2 güvenli + 1 tehlikeli plan → refine tehlikeliyi çıkarır → artifact 2 kural.
        # Özet "2 kural" demeli (plan.items=3 DEĞİL) + çıkarıldı notu içermeli.
        engine = make_engine(tmp_path, SAFE_RULES + DANGEROUS_RULE)
        agent = HardeningAgent(rule_engine=engine, max_refine=1)
        res = agent.run("sıkılaştır", security_level="balanced")
        assert res.artifact.rule_count == 2
        assert len(res.plan.items) == 3            # plan başta 3 kural seçti
        assert "2 kural" in res.summary            # özet ÜRETİLEN sayıyı yansıtır
        assert "3 kural" not in res.summary        # plan sayısını DEĞİL
        assert "çıkarıldı" in res.summary          # şeffaflık notu

    def test_summary_llm_prompt_gets_final_count(self, tmp_path):
        # LLM özet kullanılırken prompt'a GERÇEK final sayı geçer (refine sonrası).
        captured = {}
        def _spy(prompt):
            captured["prompt"] = prompt
            return "özet"
        engine = make_engine(tmp_path, SAFE_RULES + DANGEROUS_RULE)
        agent = HardeningAgent(rule_engine=engine, llm_fn=_spy, max_refine=1)
        agent.run("sıkılaştır", security_level="balanced")
        assert "Üretilen kural sayısı: 2" in captured["prompt"]


class TestEdgeCases:
    def test_all_rules_dangerous_no_artifact(self, tmp_path):
        # Tek kural ve o da tehlikeli → refine hepsini çıkarır → selected_ids boşalır.
        # Çökme olmamalı; success False (geçerli/güvenli script üretilemedi).
        engine = make_engine(tmp_path, DANGEROUS_RULE)
        agent = HardeningAgent(rule_engine=engine, max_refine=1)
        res = agent.run("temizlik", security_level="balanced")
        assert isinstance(res, AgentResult)
        assert res.success is False
        assert "rm -rf /" not in (res.artifact.content if res.artifact else "")

    def test_no_refine_when_max_refine_zero(self, tmp_path):
        # max_refine=0 → tehlikeli kural çıkmaz, refine adımı olmaz, doğrulama başarısız kalır.
        engine = make_engine(tmp_path, SAFE_RULES + DANGEROUS_RULE)
        agent = HardeningAgent(rule_engine=engine, max_refine=0)
        res = agent.run("sıkılaştır", security_level="balanced")
        assert not any(s.name == "refine" for s in res.steps)
        assert res.success is False  # tehlikeli komut doğrulamadan geçmez

    def test_no_applicable_rules(self, tmp_path):
        # only a level-2 rule; balanced asks for level-1 -> empty plan
        engine = make_engine(tmp_path, """
          - id: "2.3.1"
            title: "Audit only"
            level: 2
            category: "audit"
            remediation_script_content: "auditctl -e 1"
        """)
        agent = HardeningAgent(rule_engine=engine)
        res = agent.run("denetim", security_level="balanced")
        assert res.success is False
        assert res.plan is not None and res.plan.items == []

    def test_llm_summary_used_when_available(self, tmp_path):
        engine = make_engine(tmp_path, SAFE_RULES)
        agent = HardeningAgent(rule_engine=engine, llm_fn=lambda _p: "Yönetici özeti: 2 kural uygulandı.")
        res = agent.run("ssh", security_level="balanced")
        assert "Yönetici özeti" in res.summary
