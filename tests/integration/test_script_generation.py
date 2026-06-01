"""
Script Generation Integration Tests
--------------------------------------
OS hardening script üretimini pipeline üzerinden test eder.
SSH, firewall, RDP ve Zero Trust enrichment örneklerini içerir.

Çalıştırma:
    python tests/integration/test_script_generation.py
"""

import sys
import os

# NOT: pytest altında sys.stdout/stderr DEĞİŞTİRİLMEZ — capture mekanizmasını bozar
# ("I/O operation on closed file" → tüm suite toplanmaz). Yalnız standalone script
# olarak çalışınca (pytest import edilmemişken) Windows konsol UTF-8 düzeltmesi uygulanır.
if sys.platform == 'win32' and "pytest" not in sys.modules:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.system('chcp 65001 > nul')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from llm.clients import get_llm_clients
from llm.pipelines.secure_v2 import SecurePipelineV2
from llm.core.context import RequestContext


def _make_pipeline():
    llm_small, llm_large = get_llm_clients()
    return SecurePipelineV2(
        llm_ultra_fast=llm_small,
        llm_small=llm_small,
        llm_large=llm_large,
        debug=False,
    )


def example_ssh_hardening():
    print("\n" + "="*70)
    print("[EXAMPLE 1] SSH Hardening Script")
    print("="*70)

    pipeline = _make_pipeline()
    ctx = RequestContext(
        user_question="Ubuntu 22.04 için SSH hardening bash scripti yaz",
        os="ubuntu_22_04",
        role="sysadmin",
        security_level="strict",
    )

    print(f"Input: {ctx.user_question}")
    print(f"OS: {ctx.os} | Role: {ctx.role} | Level: {ctx.security_level}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print("[RESULT]")
    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[GENERATED SCRIPT]")
    print("-"*70)
    print(result.answer)
    print("-"*70 + "\n")


def example_firewall_rules():
    print("\n" + "="*70)
    print("[EXAMPLE 2] Firewall Rules Script")
    print("="*70)

    pipeline = _make_pipeline()
    ctx = RequestContext(
        user_question="Ubuntu 22.04 için UFW firewall kuralları oluştur",
        os="ubuntu_22_04",
        role="sysadmin",
        security_level="balanced",
    )

    print(f"Input: {ctx.user_question}")
    print(f"OS: {ctx.os} | Role: {ctx.role} | Level: {ctx.security_level}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print("[RESULT]")
    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[GENERATED SCRIPT]")
    print("-"*70)
    print(result.answer)
    print("-"*70 + "\n")


def example_rdp_hardening():
    print("\n" + "="*70)
    print("[EXAMPLE 3] RDP Hardening Script")
    print("="*70)

    pipeline = _make_pipeline()
    ctx = RequestContext(
        user_question="Windows Server 2022 için RDP güvenlik PowerShell scripti yaz",
        os="windows_server_2022",
        role="sysadmin",
        security_level="strict",
    )

    print(f"Input: {ctx.user_question}")
    print(f"OS: {ctx.os} | Role: {ctx.role} | Level: {ctx.security_level}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print("[RESULT]")
    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[GENERATED SCRIPT]")
    print("-"*70)
    print(result.answer)
    print("-"*70 + "\n")


def example_zero_trust_enrichment():
    print("\n" + "="*70)
    print("[EXAMPLE 4] Zero Trust Enrichment")
    print("="*70)

    pipeline = _make_pipeline()
    ctx = RequestContext(
        user_question="Zero Trust mimarisine göre Linux sunucu sıkılaştırma planı oluştur",
        os="ubuntu_22_04",
        role="security_engineer",
        security_level="strict",
        zt_maturity="medium",
    )

    print(f"Input: {ctx.user_question}")
    print(f"OS: {ctx.os} | Role: {ctx.role} | ZT Maturity: {ctx.zt_maturity}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print("[RESULT]")
    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[ZT ENRICHMENT / ANSWER]")
    print("-"*70)
    print(result.answer)
    print("-"*70)

    # ZT enrichment verisi varsa göster
    if hasattr(result, 'zt_principles') and result.zt_principles:
        print("\n[ZT PRINCIPLES]")
        for p in result.zt_principles:
            print(f"  - {p}")

    if hasattr(result, 'standards') and result.standards:
        print("\n[STANDARDS]")
        for s in result.standards:
            print(f"  - {s}")
    print()


def main():
    print("\n" + "="*70)
    print("SCRIPT GENERATION INTEGRATION TESTS")
    print("="*70)
    print("\nOS hardening script üretim testleri\n")

    examples = [
        ("SSH Hardening", example_ssh_hardening),
        ("Firewall Rules", example_firewall_rules),
        ("RDP Hardening", example_rdp_hardening),
        ("Zero Trust Enrichment", example_zero_trust_enrichment),
    ]

    for name, fn in examples:
        try:
            fn()
        except Exception as e:
            print(f"[ERROR] {name} failed: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*70)
    print("[COMPLETE] All script generation tests finished")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
