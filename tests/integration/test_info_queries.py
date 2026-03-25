"""
Information Query Integration Tests
------------------------------------
Bilgi sorgularının pipeline üzerinden çalışmasını test eder.
Güvenlik kavramları hakkında soru sorma örneklerini içerir.

Çalıştırma:
    python tests/integration/test_info_queries.py
"""

import sys
import os

if sys.platform == 'win32':
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


def example_what_is_ssh():
    print("\n" + "="*70)
    print("[EXAMPLE 1] What is SSH?")
    print("="*70)

    pipeline = _make_pipeline()
    ctx = RequestContext(
        user_question="SSH nedir ve nasıl çalışır?",
        os="ubuntu_22_04",
        role="user",
    )

    print(f"Input: {ctx.user_question}")
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
    print("\n" + "="*70)
    print("[EXAMPLE 2] Zero Trust Architecture")
    print("="*70)

    pipeline = _make_pipeline()
    ctx = RequestContext(
        user_question="Zero Trust Architecture nedir? Temel prensipleri nelerdir?",
        os="ubuntu_22_04",
        role="user",
    )

    print(f"Input: {ctx.user_question}")
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
    print("\n" + "="*70)
    print("[EXAMPLE 3] CIS Benchmarks")
    print("="*70)

    pipeline = _make_pipeline()
    ctx = RequestContext(
        user_question="CIS Benchmarks nedir? Ubuntu için hangi kuralları içerir?",
        os="ubuntu_22_04",
        role="user",
    )

    print(f"Input: {ctx.user_question}")
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
    print("\n" + "="*70)
    print("[EXAMPLE 4] Firewall Concepts")
    print("="*70)

    pipeline = _make_pipeline()
    ctx = RequestContext(
        user_question="Firewall stateful ve stateless arasındaki fark nedir?",
        os="ubuntu_22_04",
        role="user",
    )

    print(f"Input: {ctx.user_question}")
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
    print("\n" + "="*70)
    print("[EXAMPLE 5] NIST Standards")
    print("="*70)

    pipeline = _make_pipeline()
    ctx = RequestContext(
        user_question="NIST 800-207 standardı neyi kapsar?",
        os="ubuntu_22_04",
        role="user",
    )

    print(f"Input: {ctx.user_question}")
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
    print("\n" + "="*70)
    print("INFORMATION QUERY INTEGRATION TESTS")
    print("="*70)
    print("\nGüvenlik kavramları hakkında bilgi sorguları\n")

    examples = [
        ("SSH Basics", example_what_is_ssh),
        ("Zero Trust", example_zero_trust),
        ("CIS Benchmarks", example_cis_benchmarks),
        ("Firewall Concepts", example_firewall_concepts),
        ("NIST Standards", example_nist_standards),
    ]

    for name, fn in examples:
        try:
            fn()
        except Exception as e:
            print(f"[ERROR] {name} failed: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*70)
    print("[COMPLETE] All examples finished")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
