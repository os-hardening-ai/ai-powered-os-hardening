"""
Script Generation Example
-------------------------
Shows how to generate hardening scripts for different scenarios

Usage:
    python examples/script_generation.py
"""

import sys
import os

# Fix Windows console encoding for UTF-8 support
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.system('chcp 65001 > nul')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from llm.models import get_llm_clients
from llm.pipeline_v2 import SecurePipelineV2
from llm.context import RequestContext


def example_ssh_hardening():
    """Example: SSH hardening script"""
    print("\n" + "="*70)
    print("[EXAMPLE 1] SSH Hardening Script")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(
        llm_ultra_fast=llm_small,
        llm_small=llm_small,
        llm_large=llm_large,
        debug=False
    )

    ctx = RequestContext(
        user_question="Ubuntu 22.04 için SSH hardening scripti oluştur",
        os="ubuntu_22_04",
        role="admin",
        security_level="high"
    )

    print(f"Input: {ctx.user_question}")
    print(f"OS: {ctx.os}")
    print(f"Role: {ctx.role}")
    print(f"Security Level: {ctx.security_level}")
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
    """Example: Firewall configuration"""
    print("\n" + "="*70)
    print("[EXAMPLE 2] Firewall Rules")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(
        llm_ultra_fast=llm_small,
        llm_small=llm_small,
        llm_large=llm_large,
        debug=False
    )

    ctx = RequestContext(
        user_question="Windows Server 2022 için temel firewall kuralları oluştur",
        os="windows_server_2022",
        role="admin",
        security_level="medium"
    )

    print(f"Input: {ctx.user_question}")
    print(f"OS: {ctx.os}")
    print(f"Role: {ctx.role}")
    print(f"Security Level: {ctx.security_level}")
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
    """Example: RDP hardening"""
    print("\n" + "="*70)
    print("[EXAMPLE 3] RDP Hardening")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(
        llm_ultra_fast=llm_small,
        llm_small=llm_small,
        llm_large=llm_large,
        debug=False
    )

    ctx = RequestContext(
        user_question="Windows 10 için RDP güvenlik ayarları scripti yaz",
        os="windows_10",
        role="admin",
        security_level="high"
    )

    print(f"Input: {ctx.user_question}")
    print(f"OS: {ctx.os}")
    print(f"Role: {ctx.role}")
    print(f"Security Level: {ctx.security_level}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print("[RESULT]")
    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[GENERATED SCRIPT]")
    print("-"*70)
    print(result.answer)
    print("-"*70 + "\n")


def example_with_zt_enrichment():
    """Example: Script with Zero Trust enrichment"""
    print("\n" + "="*70)
    print("[EXAMPLE 4] Script with Zero Trust Enrichment")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(
        llm_ultra_fast=llm_small,
        llm_small=llm_small,
        llm_large=llm_large,
        debug=False
    )

    ctx = RequestContext(
        user_question="Debian 11 için kullanıcı erişim kontrolü scripti oluştur",
        os="debian_11",
        role="admin",
        security_level="critical"
    )

    print(f"Input: {ctx.user_question}")
    print(f"OS: {ctx.os}")
    print(f"Role: {ctx.role}")
    print(f"Security Level: {ctx.security_level}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print("[RESULT]")
    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")

    if hasattr(result, 'zt_enrichment') and result.zt_enrichment:
        print("\n[ZERO TRUST ENRICHMENT]")
        print(f"Principles: {', '.join(result.zt_enrichment.zt_principles)}")
        print(f"Standards: {', '.join(result.zt_enrichment.standards[:3])}...")
        print(f"Impact Level: {result.zt_enrichment.impact_level}")
        print(f"Rollback: {result.zt_enrichment.rollback_approach[:100]}...")

    print("\n[GENERATED SCRIPT]")
    print("-"*70)
    print(result.answer)
    print("-"*70 + "\n")


def main():
    """Run all script generation examples"""
    print("\n" + "="*70)
    print("SCRIPT GENERATION EXAMPLES")
    print("="*70)
    print("\nDemonstrates script generation for various scenarios\n")

    examples = [
        ("SSH Hardening", example_ssh_hardening),
        ("Firewall Rules", example_firewall_rules),
        ("RDP Hardening", example_rdp_hardening),
        ("Zero Trust Enrichment", example_with_zt_enrichment)
    ]

    print("Available examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")

    print("\nRunning all examples...\n")

    for name, example_func in examples:
        try:
            example_func()
        except Exception as e:
            print(f"[ERROR] {name} failed: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*70)
    print("[COMPLETE] All examples finished")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
