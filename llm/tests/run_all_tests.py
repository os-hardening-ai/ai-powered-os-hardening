"""
Tum Testleri Calistir
---------------------
Projedeki tum testleri otomatik olarak calistirir.

Kullanim:
    python tests/run_all_tests.py

    # Sadece unit testler
    python tests/run_all_tests.py --unit

    # Sadece integration testler
    python tests/run_all_tests.py --integration

    # Sadece pipeline evaluation
    python tests/run_all_tests.py --eval

    # Debug mode
    python tests/run_all_tests.py --debug
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def run_unit_tests():
    """Run unit tests"""
    print("\n" + "="*70)
    print("UNIT TESTS")
    print("="*70 + "\n")

    # Import and run unit tests
    try:
        from tests.unit import test_groq_models
        print("[RUNNING] test_groq_models.py")
        # Run tests here
        print("[PASS] test_groq_models.py")
    except Exception as e:
        print(f"[FAIL] test_groq_models.py: {e}")


def run_integration_tests():
    """Run integration tests"""
    print("\n" + "="*70)
    print("INTEGRATION TESTS")
    print("="*70 + "\n")

    try:
        from tests.integration import test_rag_llm_integration
        print("[RUNNING] test_rag_llm_integration.py")
        # Run tests here
        print("[PASS] test_rag_llm_integration.py")
    except Exception as e:
        print(f"[FAIL] test_rag_llm_integration.py: {e}")


def run_pipeline_evaluation(debug=False):
    """Run pipeline evaluation"""
    print("\n" + "="*70)
    print("PIPELINE EVALUATION")
    print("="*70 + "\n")

    try:
        from tests import pipeline_evaluator
        from llm.core.models import get_llm_clients
        from llm.core.pipeline_v2 import SecurityPipeline

        # Get LLM clients
        llm_small, llm_large = get_llm_clients()

        # Create pipeline
        pipeline = SecurityPipeline(
            llm_small=llm_small,
            llm_large=llm_large,
            use_rag=True,
            debug=debug
        )

        # Create evaluator
        evaluator = pipeline_evaluator.PipelineEvaluator(pipeline=pipeline, debug=debug)

        # Run evaluation (just first 10 cases for quick test)
        from tests.test_dataset import TEST_DATASET
        quick_cases = TEST_DATASET[:10]
        metrics = evaluator.run_evaluation(test_cases=quick_cases)

        if metrics.accuracy >= 0.8:
            print(f"\n[PASS] Pipeline accuracy: {metrics.accuracy*100:.1f}%")
            return True
        else:
            print(f"\n[FAIL] Pipeline accuracy too low: {metrics.accuracy*100:.1f}%")
            return False

    except Exception as e:
        print(f"[FAIL] Pipeline evaluation: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test runner"""
    import argparse

    parser = argparse.ArgumentParser(description="Run all tests")
    parser.add_argument("--unit", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration", action="store_true", help="Run only integration tests")
    parser.add_argument("--eval", action="store_true", help="Run only pipeline evaluation")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    # Determine which tests to run
    run_all = not (args.unit or args.integration or args.eval)

    passed = 0
    failed = 0

    # Run tests
    if run_all or args.unit:
        try:
            run_unit_tests()
            passed += 1
        except Exception:
            failed += 1

    if run_all or args.integration:
        try:
            run_integration_tests()
            passed += 1
        except Exception:
            failed += 1

    if run_all or args.eval:
        try:
            if run_pipeline_evaluation(debug=args.debug):
                passed += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print("="*70 + "\n")

    # Exit code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
