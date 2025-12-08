# test_local_responder.py
"""
Test local responder integration in pipeline
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
        "name": "Local Response - Greeting",
        "question": "merhaba",
        "expected_path": "local",
    },
    {
        "name": "Local Response - Thanks",
        "question": "teşekkür ederim",
        "expected_path": "local",
    },
    {
        "name": "Local Response - Farewell",
        "question": "görüşürüz",
        "expected_path": "local",
    },
    {
        "name": "Local Response - Help",
        "question": "sana bir sorum var",
        "expected_path": "local",
    },
    {
        "name": "Simple Question - Needs LLM",
        "question": "SELinux nedir?",
        "expected_path": "simple",
    },
]

print("\n" + "="*70)
print("LOCAL RESPONDER PIPELINE TEST")
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
    )

    # Run pipeline
    result = pipeline.run(ctx)

    # Show result
    print("\nRESPONSE:")
    clean_answer = result.final_answer.encode('ascii', 'ignore').decode('ascii')
    print(clean_answer[:300])
    if len(clean_answer) > 300:
        print(f"\n... (total {len(clean_answer)} chars)")

    print("\n")

# Show stats
print("\n" + "="*70)
print("PIPELINE STATISTICS")
print("="*70)
print(f"Local responses (no LLM): {pipeline.stats['local_response_count']}")
print(f"Simple path (small LLM): {pipeline.stats['simple_path_count']}")
print(f"Medium path: {pipeline.stats['medium_path_count']}")
print(f"Complex path: {pipeline.stats['complex_path_count']}")
print(f"Total LLM calls: {pipeline.stats['total_calls']}")
print(f"Total estimated cost: ${pipeline.stats['total_cost_estimate']:.4f}")
print("="*70 + "\n")

# Cost savings calculation
local_count = pipeline.stats['local_response_count']
if local_count > 0:
    saved_cost = local_count * 0.0001  # Minimum LLM cost avoided
    print(f"Cost saved by local responses: ${saved_cost:.4f}")
    print(f"(Avoided {local_count} LLM calls)")
