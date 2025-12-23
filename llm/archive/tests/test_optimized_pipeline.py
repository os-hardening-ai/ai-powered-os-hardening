# test_optimized_pipeline.py
"""
Test script for optimized pipeline with complexity-based routing
"""

from context import RequestContext
from models import get_llm_clients
from pipeline_optimized import OptimizedPipeline

# LLM clients
llm_small, llm_large = get_llm_clients()

# Pipeline
pipeline = OptimizedPipeline(
    llm_small=llm_small,
    llm_large=llm_large,
    priority="balanced",
)

# Test cases
test_cases = [
    {
        "name": "Simple Question",
        "question": "SELinux nedir?",
        "expected_path": "simple",
    },
    {
        "name": "Medium Question",
        "question": "SSH yapılandırmasını nasıl güvenli hale getiririm?",
        "expected_path": "medium",
    },
    {
        "name": "Complex Question",
        "question": "Ubuntu 22.04 için full hardening script yaz",
        "expected_path": "complex",
    },
]

print("\n" + "="*70)
print("OPTIMIZED PIPELINE - COMPLEXITY ROUTING TEST")
print("="*70 + "\n")

for i, test in enumerate(test_cases, 1):
    print(f"\n{'-'*70}")
    print(f"TEST {i}: {test['name']}")
    print(f"Question: {test['question']}")
    print(f"Expected Path: {test['expected_path'].upper()}")
    print(f"{'-'*70}\n")

    # Create context
    ctx = RequestContext(
        user_question=test['question'],
        os="ubuntu_22_04",
        role="sysadmin",
        security_level="strict",
    )

    # Run pipeline
    result = pipeline.run(ctx)

    # Show result
    print("\nFINAL ANSWER:")
    # Emoji'leri temizle (Windows encoding sorunu için)
    clean_answer = result.final_answer.encode('ascii', 'ignore').decode('ascii')
    print(clean_answer[:500])  # İlk 500 karakter
    if len(clean_answer) > 500:
        print(f"\n... (total {len(clean_answer)} chars)")

    print("\n")

# Show stats
print("\n" + "="*70)
print("PIPELINE STATISTICS")
print("="*70)
print(f"Total LLM calls: {pipeline.stats['total_calls']}")
print(f"Fast path (smalltalk): {pipeline.stats['fast_path_count']}")
print(f"Simple path: {pipeline.stats['simple_path_count']}")
print(f"Medium path: {pipeline.stats['medium_path_count']}")
print(f"Complex path: {pipeline.stats['complex_path_count']}")
print(f"Total estimated cost: ${pipeline.stats['total_cost_estimate']:.4f}")
print("="*70 + "\n")
