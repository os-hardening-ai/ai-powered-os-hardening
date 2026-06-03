"""
FreeformScriptGenerator birim testleri — AĞSIZ (sahte LLM).

Katalog-dışı özel istekler için LLM script üretimi + güvenlik kapısı (DANGEROUS_COMMANDS)
+ tehlikeli→reddet politikası. LLM sahte; gerçek model çağrılmaz.
"""
from __future__ import annotations

from llm.agents.freeform_generator import (
    FreeformScriptGenerator,
    FreeformResult,
    _extract_code_block,
)


def fake_llm(resp: str):
    return lambda _p: resp


_SAFE_BASH = (
    "```bash\n#!/usr/bin/env bash\nset -euo pipefail\n"
    "groupadd -f dev\n"
    "grep -q '^AllowGroups' /etc/ssh/sshd_config || echo 'AllowGroups dev' >> /etc/ssh/sshd_config\n"
    "```"
)
_DANGEROUS_BASH = "```bash\n#!/usr/bin/env bash\nrm -rf /\n```"


class TestExtractCodeBlock:
    def test_fenced_block(self):
        assert "groupadd" in _extract_code_block(_SAFE_BASH, "bash")

    def test_no_fence_shebang(self):
        assert _extract_code_block("#!/usr/bin/env bash\ngroupadd dev", "bash").startswith("#!")

    def test_no_fence_command_heuristic(self):
        assert "groupadd" in _extract_code_block("groupadd dev\nusermod -aG dev ali", "bash")

    def test_empty_on_prose(self):
        assert _extract_code_block("Bu bir açıklama metni, kod yok.", "bash") == ""


class TestGenerate:
    def test_safe_script_ok(self):
        gen = FreeformScriptGenerator(llm_fn=fake_llm(_SAFE_BASH))
        r = gen.generate("SSH için dev grubu oluştur ve allow ver")
        assert isinstance(r, FreeformResult)
        assert r.ok is True
        assert "groupadd" in r.content and "AllowGroups dev" in r.content
        assert r.language == "bash"
        assert r.issues == []

    def test_dangerous_script_rejected(self):
        # GÜVENLİK: tehlikeli komut → reddet (güvenli alternatif üretme YOK)
        gen = FreeformScriptGenerator(llm_fn=fake_llm(_DANGEROUS_BASH))
        r = gen.generate("diski temizle")
        assert r.ok is False
        assert r.issues   # validator sorununu bildirdi

    def test_windows_target_powershell(self):
        ps = ("```powershell\n# dev grubu oluştur (idempotent)\n"
              "if (-not (Get-LocalGroup -Name 'dev' -ErrorAction SilentlyContinue)) "
              "{ New-LocalGroup -Name 'dev' -Description 'Developers' }\n```")
        gen = FreeformScriptGenerator(llm_fn=fake_llm(ps))
        r = gen.generate("dev grubu oluştur", os_target="windows_11")
        assert r.language == "powershell"
        assert r.ok is True

    def test_unparseable_llm_output(self):
        gen = FreeformScriptGenerator(llm_fn=fake_llm("Üzgünüm, bunu yapamam."))
        r = gen.generate("bir şey yap")
        assert r.ok is False
        assert "çıkarılamadı" in r.issues[0]

    def test_llm_exception_graceful(self):
        def boom(_p):
            raise RuntimeError("provider down")
        gen = FreeformScriptGenerator(llm_fn=boom)
        r = gen.generate("dev grubu oluştur")
        assert r.ok is False
        assert "LLM hatası" in r.issues[0]
