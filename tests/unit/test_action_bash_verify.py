"""
Unit tests for ActionPipeline (a) bash -n self-verify.

Üretilen script'in ASIL bash bloğunu (shebang'li) `bash -n` ile doğrular; bozuksa
LLM-onarım dener, yine bozuksa uyarı ekler. PowerShell / config-snippet'lere DOKUNMAZ
(yanlış pozitif önlenir). bash yoksa atlanır (false-fail vermez).
"""

from __future__ import annotations

import shutil

import pytest

from llm.pipelines.layers.action_pipeline import ActionPipeline

_HAS_BASH = shutil.which("bash") is not None


@pytest.fixture
def ap():
    # llm_large/llm_small basit echo — _bash_self_verify llm_small'ı yalnız onarım için çağırır.
    return ActionPipeline(llm_large=lambda p: "ok", llm_small=lambda p: "ok")


GOOD = "Adım 1:\n```bash\n#!/usr/bin/env bash\nset -euo pipefail\necho merhaba\n```"
BROKEN = '```bash\n#!/usr/bin/env bash\necho "unterminated string\n```'  # kapanmamış tırnak
SNIPPET = "Yapılandırma:\n```bash\nkernel.yama.ptrace_scope = 1\n```"     # shebang YOK → snippet


class TestExtractMainBash:
    def test_picks_shebang_block(self):
        out = ActionPipeline._extract_main_bash(GOOD)
        assert out is not None and out.lstrip().startswith("#!")

    def test_none_when_no_shebang(self):
        assert ActionPipeline._extract_main_bash(SNIPPET) is None
        assert ActionPipeline._extract_main_bash("düz metin, kod yok") is None


@pytest.mark.skipif(not _HAS_BASH, reason="bash yok — bash -n atlanır")
class TestBashSelfVerify:
    def test_valid_script_unchanged(self, ap):
        assert ap._bash_self_verify(GOOD, "ubuntu_22_04") == GOOD

    def test_broken_script_warned_or_repaired(self, ap):
        out = ap._bash_self_verify(BROKEN, "ubuntu_22_04")
        # onarım (echo 'ok' bozuk → onaramaz) → uyarı eklenir; her durumda DEĞİŞİR
        assert out != BROKEN
        assert "Sözdizimi uyarısı" in out

    def test_windows_target_skipped(self, ap):
        # PowerShell hedefi → bash -n çalışmaz (yanlış pozitif yok)
        assert ap._bash_self_verify(BROKEN, "windows_11") == BROKEN

    def test_snippet_without_shebang_skipped(self, ap):
        # config snippet (shebang yok) doğrulanmaz → dokunulmaz
        assert ap._bash_self_verify(SNIPPET, "ubuntu_22_04") == SNIPPET

    def test_llm_repair_accepted_when_fixed(self):
        # LLM geçerli script döndürürse → onarılmış kabul edilir (uyarı YOK)
        fixed = "```bash\n#!/usr/bin/env bash\nset -e\necho duzeltildi\n```"
        ap = ActionPipeline(llm_large=lambda p: "x", llm_small=lambda p: fixed)
        out = ap._bash_self_verify(BROKEN, "ubuntu_22_04")
        assert "duzeltildi" in out and "Sözdizimi uyarısı" not in out
