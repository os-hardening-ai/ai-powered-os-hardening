"""
Different OS Types Examples
---------------------------
Shows how to generate scripts for different operating systems

Usage:
    python examples/different_os_types.py
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

from llm.core.models import get_llm_clients
from llm.core.pipeline_v2 import SecurePipelineV2
from llm.core.context import RequestContext


def example_ubuntu():
    """Example: Ubuntu 22.04"""
    print("\n" + "="*70)
    print("[EXAMPLE 1] Ubuntu 22.04 SSH Hardening")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(
        llm_ultra_fast=llm_small,
        llm_small=llm_small,
        llm_large=llm_large,
        debug=False
    )

    ctx = RequestContext(
        user_question="SSH güvenlik ayarları için script oluştur",
        os="ubuntu_22_04",
        role="admin",
        security_level="high"
    )

    print(f"OS Type: {ctx.os}")
    print(f"Request: {ctx.user_question}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[SCRIPT]")
    print(result.answer[:300] + "...\n")


def example_debian():
    """Example: Debian 11"""
    print("\n" + "="*70)
    print("[EXAMPLE 2] Debian 11 Firewall Configuration")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(
        llm_ultra_fast=llm_small,
        llm_small=llm_small,
        llm_large=llm_large,
        debug=False
    )

    ctx = RequestContext(
        user_question="Firewall kuralları oluştur",
        os="debian_11",
        role="admin",
        security_level="medium"
    )

    print(f"OS Type: {ctx.os}")
    print(f"Request: {ctx.user_question}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[SCRIPT]")
    print(result.answer[:300] + "...\n")


def example_centos():
    """Example: CentOS 7"""
    print("\n" + "="*70)
    print("[EXAMPLE 3] CentOS 7 SELinux Configuration")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(
        llm_ultra_fast=llm_small,
        llm_small=llm_small,
        llm_large=llm_large,
        debug=False
    )

    ctx = RequestContext(
        user_question="SELinux güvenlik ayarları scripti yaz",
        os="centos_7",
        role="admin",
        security_level="high"
    )

    print(f"OS Type: {ctx.os}")
    print(f"Request: {ctx.user_question}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[SCRIPT]")
    print(result.answer[:300] + "...\n")


def example_windows_server():
    """Example: Windows Server 2022"""
    print("\n" + "="*70)
    print("[EXAMPLE 4] Windows Server 2022 Security Hardening")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(
        llm_ultra_fast=llm_small,
        llm_small=llm_small,
        llm_large=llm_large,
        debug=False
    )

    ctx = RequestContext(
        user_question="Windows Defender ve firewall ayarları için PowerShell scripti oluştur",
        os="windows_server_2022",
        role="admin",
        security_level="high"
    )

    print(f"OS Type: {ctx.os}")
    print(f"Request: {ctx.user_question}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[SCRIPT]")
    print(result.answer[:300] + "...\n")


def example_windows_10():
    """Example: Windows 10"""
    print("\n" + "="*70)
    print("[EXAMPLE 5] Windows 10 RDP Security")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(
        llm_ultra_fast=llm_small,
        llm_small=llm_small,
        llm_large=llm_large,
        debug=False
    )

    ctx = RequestContext(
        user_question="RDP güvenlik ayarları scripti",
        os="windows_10",
        role="admin",
        security_level="critical"
    )

    print(f"OS Type: {ctx.os}")
    print(f"Request: {ctx.user_question}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[SCRIPT]")
    print(result.answer[:300] + "...\n")


def example_rhel():
    """Example: RHEL 8"""
    print("\n" + "="*70)
    print("[EXAMPLE 6] RHEL 8 Audit Configuration")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(
        llm_ultra_fast=llm_small,
        llm_small=llm_small,
        llm_large=llm_large,
        debug=False
    )

    ctx = RequestContext(
        user_question="Audit daemon yapılandırması için script",
        os="rhel_8",
        role="admin",
        security_level="high"
    )

    print(f"OS Type: {ctx.os}")
    print(f"Request: {ctx.user_question}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[SCRIPT]")
    print(result.answer[:300] + "...\n")


def main():
    """Run all OS-specific examples"""
    print("\n" + "="*70)
    print("DIFFERENT OS TYPES EXAMPLES")
    print("="*70)
    print("\nDemonstrates script generation for various operating systems\n")

    examples = [
        ("Ubuntu 22.04", example_ubuntu),
        ("Debian 11", example_debian),
        ("CentOS 7", example_centos),
        ("Windows Server 2022", example_windows_server),
        ("Windows 10", example_windows_10),
        ("RHEL 8", example_rhel)
    ]

    print("Supported operating systems:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")

    print("\nRunning examples for each OS...\n")

    for name, example_func in examples:
        try:
            example_func()
        except Exception as e:
            print(f"[ERROR] {name} failed: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*70)
    print("[COMPLETE] All OS examples finished")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
