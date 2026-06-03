"""
Integration tests for llm.agents.hardening_agent.HardeningAgent (İP-7).

Drives the full multi-step tool chain with REAL RuleEngine + TaskPlanner +
ArtifactGenerator + OutputValidator (LLM faked/None). Verifies the step trace,
artifact generation, the self-verify gate and the observe→reason→re-act refine
loop that drops rules carrying dangerous commands.
"""

from __future__ import annotations

import shutil
import textwrap

import pytest

from domain.rule_engine.rule_engine import RuleEngine
from llm.agents.hardening_agent import HardeningAgent, AgentResult

pytestmark = pytest.mark.integration

_HAS_BASH = shutil.which("bash") is not None


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

# Tehlikeli DEĞİL ama sözdizimi BOZUK (dengesiz çift tırnak) → `bash -n` patlar,
# fakat OutputValidator tehlikeli-komut taramasından GEÇER (echo zararsız).
BROKEN_BASH_RULE = """
  - id: "7.7.7"
    title: "Broken quote rule"
    level: 1
    category: "misc"
    remediation_script_content: 'echo "unterminated string >> /etc/some.conf'
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


class TestSyntaxSelfVerify:
    """Step 6: üretilen script `bash -n`/`yaml.load` ile FİİLEN doğrulanır; bozuksa
    (a) bozuk kural izole edilip çıkarılır (deterministik), (b) son çare LLM-repair."""

    @pytest.mark.skipif(not _HAS_BASH, reason="bash yok — `bash -n` doğrulaması atlanır")
    def test_syntax_step_present_and_ok_on_happy_path(self, tmp_path):
        engine = make_engine(tmp_path, SAFE_RULES)
        agent = HardeningAgent(rule_engine=engine)  # llm None
        res = agent.run("ssh", fmt="bash")
        syntax_steps = [s for s in res.steps if s.name == "syntax"]
        assert len(syntax_steps) == 1 and syntax_steps[0].ok  # tek geçiş, geçerli
        assert res.success

    @pytest.mark.skipif(not _HAS_BASH, reason="bash yok")
    def test_broken_rule_isolated_and_dropped(self, tmp_path):
        # SAFE + sözdizimi bozuk kural → izolasyon bozuğu bulur, çıkarır, yeniden üretir.
        engine = make_engine(tmp_path, SAFE_RULES + BROKEN_BASH_RULE)
        agent = HardeningAgent(rule_engine=engine, max_syntax_fix=1)  # llm None
        res = agent.run("sıkılaştır", fmt="bash")
        # deterministik syntax-isolate refine adımı ateşlendi
        assert any(s.name == "refine" and s.tool == "syntax-isolate" for s in res.steps)
        # bozuk kural final çıktıdan SİLİNDİ, güvenli kurallar kaldı
        assert "7.7.7" not in res.artifact.content
        assert "unterminated" not in res.artifact.content
        assert "PermitRootLogin no" in res.artifact.content
        # son syntax kontrolü temiz → success
        syntax_steps = [s for s in res.steps if s.name == "syntax"]
        assert len(syntax_steps) == 2 and syntax_steps[-1].ok
        assert res.success

    def test_ansible_syntax_checked_via_yaml(self, tmp_path):
        # bash gerektirmez — ansible yaml.safe_load ile doğrulanır (safe_dump → geçerli).
        engine = make_engine(tmp_path, SAFE_RULES)
        agent = HardeningAgent(rule_engine=engine)
        res = agent.run("hepsi", fmt="ansible")
        syntax_steps = [s for s in res.steps if s.name == "syntax"]
        assert len(syntax_steps) == 1 and syntax_steps[0].ok
        assert res.success

    @pytest.mark.skipif(not _HAS_BASH, reason="bash yok")
    def test_llm_repair_last_resort_accepted(self, tmp_path, monkeypatch):
        # İzolasyon suçluyu bulamazsa (iskelet düzeyi hata) → LLM-repair son çaresi.
        engine = make_engine(tmp_path, BROKEN_BASH_RULE)
        # Onarılmış script: geçerli + güvenli + min uzunluğu (50 char) aşar.
        fixed = ("#!/usr/bin/env bash\nset -euo pipefail\n"
                 "echo 'AllowGroups sudo' >> /etc/ssh/sshd_config\necho tamamlandi\n")
        agent = HardeningAgent(
            rule_engine=engine, max_syntax_fix=1,
            llm_fn=lambda _p: "```bash\n" + fixed + "```",  # fenced → strip edilmeli
        )
        # izolasyonu bilerek devre dışı bırak → LLM-repair dalına zorla
        monkeypatch.setattr(agent, "_isolate_broken_rule_ids", lambda *a, **k: set())
        res = agent.run("temizlik", fmt="bash")
        assert any(s.tool == "LLM-repair" and s.ok for s in res.steps)
        assert "AllowGroups sudo" in res.artifact.content  # fence ayıklandı + onarıldı
        assert res.success

    @pytest.mark.skipif(not _HAS_BASH, reason="bash yok")
    def test_llm_repair_rejected_when_still_invalid(self, tmp_path, monkeypatch):
        # LLM onarımı HÂLÂ bozuksa reddedilir → bozuk script sessizce sunulmaz, success False.
        engine = make_engine(tmp_path, BROKEN_BASH_RULE)
        # 50+ char (uzunluk geçer) AMA dengesiz tırnak → SÖZDİZİMİ nedeniyle reddedilmeli.
        agent = HardeningAgent(
            rule_engine=engine, max_syntax_fix=1,
            llm_fn=lambda _p: ('#!/usr/bin/env bash\n'
                               'echo "still an unterminated string that is plenty long enough'),
        )
        monkeypatch.setattr(agent, "_isolate_broken_rule_ids", lambda *a, **k: set())
        res = agent.run("temizlik", fmt="bash")
        assert any(s.tool == "LLM-repair" and not s.ok for s in res.steps)
        assert not res.success
        assert any("Sözdizimi" in i for i in res.issues)


class TestSyntaxHelpers:
    def test_strip_code_fence(self, tmp_path):
        engine = make_engine(tmp_path, SAFE_RULES)
        agent = HardeningAgent(rule_engine=engine)
        assert agent._strip_code_fence("```bash\necho hi\n```") == "echo hi"
        assert agent._strip_code_fence("```\necho hi\n```") == "echo hi"
        assert agent._strip_code_fence("echo hi") == "echo hi"  # çitsiz → değişmez

    def test_syntax_check_skips_unverifiable_formats(self, tmp_path):
        engine = make_engine(tmp_path, SAFE_RULES)
        agent = HardeningAgent(rule_engine=engine)
        ok, err = agent._syntax_check("Set-Item X 14", "powershell")
        assert ok and err == ""        # pwsh doğrulayıcı yok → engelleme

    def test_syntax_check_detects_bad_yaml(self, tmp_path):
        engine = make_engine(tmp_path, SAFE_RULES)
        agent = HardeningAgent(rule_engine=engine)
        ok, err = agent._syntax_check("key: [unclosed", "ansible")
        assert not ok and err          # geçersiz YAML yakalanır


class TestCatalogMissFreeform:
    """Katalog-dışı özel istek (dev grubu oluştur) → serbest-form dal (mode=freeform).

    Düzeltilen bug: "SSH için dev grubu oluştur ve allow ver" eskiden 23 generic CIS
    kuralı döküyordu; artık LLM ile hedefe-özel script üretilir.
    """

    # groupadd + AllowGroups dev üreten sahte LLM (gerçek model yerine)
    def _devgroup_llm(self):
        script = (
            "```bash\n#!/usr/bin/env bash\nset -euo pipefail\n"
            "groupadd -f dev\n"
            "grep -q 'AllowGroups' /etc/ssh/sshd_config || echo 'AllowGroups dev' >> /etc/ssh/sshd_config\n"
            "sshd -t && systemctl reload sshd\n```"
        )
        return lambda _p: script

    def test_devgroup_request_uses_freeform(self, tmp_path):
        engine = make_engine(tmp_path, SAFE_RULES)
        agent = HardeningAgent(rule_engine=engine, llm_fn=self._devgroup_llm())
        res = agent.run("SSH için dev grubu oluştur ve bu gruba SSH izni ver",
                        os_target="ubuntu_24_04", security_level="balanced", fmt="bash")
        assert res.mode == "freeform"
        assert res.success
        # Kullanıcının GERÇEK isteği karşılanıyor:
        assert "groupadd" in res.artifact.content and "dev" in res.artifact.content
        assert "AllowGroups dev" in res.artifact.content
        # Eski hatalı davranış YOK: 20+ generic CIS kuralı dökülmedi
        assert res.artifact.rule_count == 0   # katalog kuralı değil
        assert any(s.name == "freeform_generate" for s in res.steps)

    def test_normal_hardening_stays_catalog(self, tmp_path):
        # REGRESYON: normal CIS hedefi hâlâ katalog akışı (mode=catalog), bozulmadı.
        engine = make_engine(tmp_path, SAFE_RULES)
        agent = HardeningAgent(rule_engine=engine)
        res = agent.run("SSH ve parola sıkılaştır", security_level="balanced")
        assert res.mode == "catalog"
        assert res.artifact is not None and res.artifact.rule_count >= 1

    def test_dangerous_freeform_rejected(self, tmp_path):
        # GÜVENLİK: serbest-form tehlikeli komut üretirse REDDEDİLİR (success=False).
        engine = make_engine(tmp_path, SAFE_RULES)
        agent = HardeningAgent(rule_engine=engine,
                               llm_fn=lambda _p: "```bash\nrm -rf /\n```")
        res = agent.run("dev grubu oluştur", security_level="balanced")
        assert res.mode == "freeform"
        assert res.success is False
        assert res.issues   # güvenlik sorunu bildirildi

    def test_freeform_without_llm_fails_gracefully(self, tmp_path):
        engine = make_engine(tmp_path, SAFE_RULES)
        agent = HardeningAgent(rule_engine=engine, llm_fn=None)
        res = agent.run("dev grubu oluştur", security_level="balanced")
        assert res.mode == "freeform" and res.success is False
