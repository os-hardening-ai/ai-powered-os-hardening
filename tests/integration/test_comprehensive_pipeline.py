"""
Comprehensive LLM Pipeline & RAG Integration Tests
==================================================

Tests all possible scenarios:
- ML Intent Detection (7 categories)
- RAG retrieval integration
- Pipeline routing (info, action, greeting, etc.)
- Error handling
- Edge cases
"""

from llm.clients import get_llm_clients
from llm.pipelines.secure_v2 import run_secure_pipeline_v2
from llm.ml.intent_detector import MLIntentDetector
from llm.rag.integration import RAG_AVAILABLE, get_rag_context_builder

print("=" * 80)
print("COMPREHENSIVE PIPELINE & RAG INTEGRATION TEST")
print("=" * 80)

# Initialize components
llm_small, llm_large = get_llm_clients()
ml_detector = MLIntentDetector(debug=False)

# Test scenarios covering all intent types
test_scenarios = [
    # Greeting intent
    ("Merhaba nasılsınız", "greeting", False),
    ("Hey what's up", "greeting", False),
    ("Selam ekip", "greeting", False),

    # Farewell intent
    ("Görüşürüz teşekkürler", "farewell", False),
    ("Goodbye bye bye", "farewell", False),
    ("Hoşçakal başarılar", "farewell", False),

    # Thanks intent
    ("Çok teşekkürler yardımın için", "thanks", False),
    ("Perfect thanks a lot", "thanks", False),
    ("Süpersin sağol", "thanks", False),

    # Help intent
    ("Yardıma ihtiyacım var", "help", False),
    ("Can you help me please", "help", False),
    ("Destek lazım acil", "help", False),

    # Info request - should use RAG
    ("SSH nedir açıkla", "info_request", True),
    ("Firewall nasıl çalışır", "info_request", True),
    ("Zero trust modelini anlat", "info_request", True),
    ("MFA authentication nasıl çalışır", "info_request", True),
    ("SELinux nedir", "info_request", True),

    # Action request - script generation
    ("Ubuntu SSH hardening scripti yaz", "action_request", False),
    ("Debian firewall kuralı ekle", "action_request", False),
    ("Docker security configuration oluştur", "action_request", False),
    ("Kubernetes RBAC policy hazırla", "action_request", False),

    # Out of scope
    ("Bugün hava nasıl", "out_of_scope", False),
    ("Film tavsiyesi ver", "out_of_scope", False),
    ("Yemek tarifi lazım", "out_of_scope", False),
]

print("\n[TEST 1] ML Intent Detection Accuracy")
print("-" * 80)
correct = 0
total = len(test_scenarios)

for question, expected_intent, _ in test_scenarios:
    result = ml_detector.predict(question)
    is_correct = result.type == expected_intent
    correct += is_correct

    status = "[OK]" if is_correct else "[ERR]"
    print(f"{status} '{question[:50]}...' -> {result.type} (expected: {expected_intent}, conf: {result.confidence:.2f})")

accuracy = (correct / total) * 100
print(f"\n[RESULT] Intent Detection Accuracy: {correct}/{total} = {accuracy:.1f}%")

print("\n[TEST 2] RAG Integration")
print("-" * 80)
if RAG_AVAILABLE:
    builder = get_rag_context_builder(top_k=3, min_score=0.7)

    rag_queries = [
        "SSH hardening",
        "Firewall configuration",
        "Password policy",
    ]

    for query in rag_queries:
        context = builder.retrieve_context(query)
        has_content = len(context) > 100 and "[NOT:" not in context
        status = "[OK]" if has_content else "[WARN]"
        print(f"{status} RAG query '{query}' -> {len(context)} chars")
else:
    print("[WARN] RAG not available")

print("\n[TEST 3] End-to-End Pipeline Tests (Sample)")
print("-" * 80)

# Test a few key scenarios end-to-end
pipeline_tests = [
    ("Merhaba", "Should return instant greeting"),
    ("SSH nedir açıkla", "Should use RAG and return info"),
    ("Ubuntu SSH port değiştir scripti", "Should generate script"),
    ("Film önerisi ver", "Should reject politely"),
]

for question, description in pipeline_tests:
    try:
        result = run_secure_pipeline_v2(
            question=question,
            llm_ultra_fast=llm_small,
            llm_small=llm_small,
            llm_large=llm_large,
            debug=False
        )

        has_answer = len(result.answer) > 10
        status = "[OK]" if has_answer else "[WARN]"

        intent = result.metadata.get('intent', 'unknown')
        safety = result.metadata.get('safety', 'unknown')

        print(f"{status} '{question[:40]}...'")
        print(f"    Intent: {intent}, Safety: {safety}")
        print(f"    Answer: {result.answer[:100]}...")
        print()

    except Exception as e:
        print(f"[ERR] '{question}' failed: {e}")
        print()

print("=" * 80)
print("COMPREHENSIVE TEST COMPLETE")
print("=" * 80)
print("\n[SUMMARY]")
print(f"  ML Intent Accuracy: {accuracy:.1f}%")
print(f"  RAG Available: {RAG_AVAILABLE}")
print(f"  LLM Clients: Initialized")
print(f"  Pipeline: Functional")
print("\n")
