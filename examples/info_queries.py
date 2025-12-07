"""
Information Query Examples
--------------------------
Shows how to ask informational questions about security concepts

Usage:
    python examples/info_queries.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from llm.models import get_llm_clients
from llm.pipeline_v2 import SecurePipelineV2
from llm.context import RequestContext


def example_what_is_ssh():
    """Example: What is SSH?"""
    print("\n" + "="*70)
    print("[EXAMPLE 1] What is SSH?")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(llm_small=llm_small, llm_large=llm_large, use_rag=True)

    ctx = RequestContext(
        user_input="SSH nedir ve nasıl çalışır?",
        os_type="ubuntu_22_04",
        role="user"
    )

    print(f"Input: {ctx.user_input}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print("[RESULT]")
    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[ANSWER]")
    print("-"*70)
    print(result.answer)
    print("-"*70 + "\n")


def example_zero_trust():
    """Example: Zero Trust Architecture"""
    print("\n" + "="*70)
    print("[EXAMPLE 2] Zero Trust Architecture")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(llm_small=llm_small, llm_large=llm_large, use_rag=True)

    ctx = RequestContext(
        user_input="Zero Trust Architecture nedir? Temel prensipleri nelerdir?",
        os_type="ubuntu_22_04",
        role="user"
    )

    print(f"Input: {ctx.user_input}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print("[RESULT]")
    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[ANSWER]")
    print("-"*70)
    print(result.answer)
    print("-"*70)

    if hasattr(result, 'rag_sources') and result.rag_sources:
        print("\n[SOURCES]")
        for i, source in enumerate(result.rag_sources[:3], 1):
            print(f"  {i}. {source.get('source', 'Unknown')} (Score: {source.get('score', 0):.2f})")
    print()


def example_cis_benchmarks():
    """Example: CIS Benchmarks"""
    print("\n" + "="*70)
    print("[EXAMPLE 3] CIS Benchmarks")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(llm_small=llm_small, llm_large=llm_large, use_rag=True)

    ctx = RequestContext(
        user_input="CIS Benchmarks nedir? Ubuntu için hangi kuralları içerir?",
        os_type="ubuntu_22_04",
        role="user"
    )

    print(f"Input: {ctx.user_input}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print("[RESULT]")
    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[ANSWER]")
    print("-"*70)
    print(result.answer)
    print("-"*70 + "\n")


def example_firewall_concepts():
    """Example: Firewall concepts"""
    print("\n" + "="*70)
    print("[EXAMPLE 4] Firewall Concepts")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(llm_small=llm_small, llm_large=llm_large, use_rag=True)

    ctx = RequestContext(
        user_input="Firewall stateful ve stateless arasındaki fark nedir?",
        os_type="ubuntu_22_04",
        role="user"
    )

    print(f"Input: {ctx.user_input}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print("[RESULT]")
    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[ANSWER]")
    print("-"*70)
    print(result.answer)
    print("-"*70 + "\n")


def example_nist_standards():
    """Example: NIST standards"""
    print("\n" + "="*70)
    print("[EXAMPLE 5] NIST Standards")
    print("="*70)

    llm_small, llm_large = get_llm_clients()
    pipeline = SecurePipelineV2(llm_small=llm_small, llm_large=llm_large, use_rag=True)

    ctx = RequestContext(
        user_input="NIST 800-207 standardı neyi kapsar?",
        os_type="ubuntu_22_04",
        role="user"
    )

    print(f"Input: {ctx.user_input}")
    print("\n[PROCESSING]...\n")

    result = pipeline.run(ctx)

    print("[RESULT]")
    print(f"Layer Path: {result.layer_path}")
    print(f"Cost: ${result.estimated_cost:.4f}")
    print("\n[ANSWER]")
    print("-"*70)
    print(result.answer)
    print("-"*70 + "\n")


def main():
    """Run all information query examples"""
    print("\n" + "="*70)
    print("INFORMATION QUERY EXAMPLES")
    print("="*70)
    print("\nDemonstrates asking informational questions about security\n")

    examples = [
        ("SSH Basics", example_what_is_ssh),
        ("Zero Trust", example_zero_trust),
        ("CIS Benchmarks", example_cis_benchmarks),
        ("Firewall Concepts", example_firewall_concepts),
        ("NIST Standards", example_nist_standards)
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
