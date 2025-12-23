#!/usr/bin/env python3
"""
Test Groq Models - Her iki modelin de çalıştığını doğrula
"""

import sys
import os

# Add llm to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "llm"))

def test_groq_small_model():
    """Test small model (llama-3.1-8b-instant)"""
    print("\n" + "="*60)
    print("[TEST 1] Groq Small Model (llama-3.1-8b-instant)")
    print("="*60)

    try:
        from llm.core.models.groq_client import get_small_groq_llm

        # Get client
        llm = get_small_groq_llm()

        # Test prompt
        prompt = "What is 2+2? Answer in one word."
        print(f"\n[PROMPT] {prompt}")

        # Call model
        print("[CALLING] Model is being called...")
        response = llm(prompt)

        print(f"[OK] Response: {response}")
        print(f"[OK] Model calisyor!")
        return True

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_groq_large_model():
    """Test large model (llama-3.3-70b-versatile)"""
    print("\n" + "="*60)
    print("[TEST 2] Groq Large Model (llama-3.3-70b-versatile)")
    print("="*60)

    try:
        from llm.core.models.groq_client import get_large_groq_llm

        # Get client
        llm = get_large_groq_llm()

        # Test prompt
        prompt = "Explain what is SSH in one sentence."
        print(f"\n[PROMPT] {prompt}")

        # Call model
        print("[CALLING] Model is being called...")
        response = llm(prompt)

        print(f"[OK] Response: {response}")
        print(f"[OK] Model calisyor!")
        return True

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pipeline_integration():
    """Test pipeline'da model seçiminin doğru çalıştığını test et"""
    print("\n" + "="*60)
    print("[TEST 3] Pipeline Integration")
    print("="*60)

    try:
        from llm.core.models import get_llm_clients
        from llm.core.config import CONFIG

        print(f"\n[CONFIG] Active Provider: {CONFIG.llm_provider}")
        print(f"[CONFIG] Small Model: {CONFIG.groq_small_model}")
        print(f"[CONFIG] Large Model: {CONFIG.groq_large_model}")

        # Get clients
        print("\n[INIT] Getting LLM clients from pipeline...")
        llm_small, llm_large = get_llm_clients()

        # Test small
        print("\n[TEST] Testing small model via pipeline...")
        response_small = llm_small("Say 'hello' in one word")
        print(f"[OK] Small model response: {response_small}")

        # Test large
        print("\n[TEST] Testing large model via pipeline...")
        response_large = llm_large("What is Linux? Answer in 5 words.")
        print(f"[OK] Large model response: {response_large}")

        print(f"\n[OK] Pipeline entegrasyonu calisyor!")
        return True

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n=== GROQ MODEL TEST SUITE ===\n")

    results = []

    # Test 1: Small model
    results.append(("Small Model", test_groq_small_model()))

    # Test 2: Large model
    results.append(("Large Model", test_groq_large_model()))

    # Test 3: Pipeline integration
    results.append(("Pipeline Integration", test_pipeline_integration()))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    all_passed = True
    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False

    print("="*60)

    if all_passed:
        print("\n[SUCCESS] TUM TESTLER BASARILI!")
        print("\n[OK] Groq modelleri calisyor")
        print("[OK] Pipeline entegrasyonu tamam")
        print("[OK] Demo icin hazir!")
        return 0
    else:
        print("\n[FAIL] BAZI TESTLER BASARISIZ!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
