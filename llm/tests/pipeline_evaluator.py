"""
Pipeline Evaluator
------------------
Runs test dataset against pipeline and collects metrics.

Usage:
    python -m llm.eval.pipeline_evaluator

    # Or with specific tags
    python -m llm.eval.pipeline_evaluator --tags smalltalk,info

    # Or with debug mode
    python -m llm.eval.pipeline_evaluator --debug
"""

from __future__ import annotations
import sys
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import json

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from llm.testing.tests.test_dataset import TEST_DATASET, get_test_cases_by_tag
from llm.pipelines.secure_v2 import SecurePipelineV2
from llm.core.context import RequestContext
from llm.clients import get_llm_clients


@dataclass
class TestResult:
    """Single test case result"""
    test_id: str
    input: str
    passed: bool
    expected_intent: str
    actual_intent: str
    expected_layer_path: str
    actual_layer_path: str
    expected_safety: str
    actual_safety: str
    latency_ms: float
    cost: float
    error: Optional[str] = None


@dataclass
class EvaluationMetrics:
    """Aggregated evaluation metrics"""
    total_tests: int
    passed_tests: int
    failed_tests: int
    accuracy: float
    avg_latency_ms: float
    total_cost: float
    intent_accuracy: float
    layer_path_accuracy: float
    safety_accuracy: float
    errors: int


class PipelineEvaluator:
    """
    Pipeline Evaluator

    Runs test dataset and collects metrics.
    """

    def __init__(self, pipeline: SecurityPipeline, debug: bool = False):
        self.pipeline = pipeline
        self.debug = debug
        self.results: List[TestResult] = []

    def run_test_case(self, test_case: Dict[str, Any]) -> TestResult:
        """Run a single test case"""
        test_id = test_case["id"]
        input_text = test_case["input"]

        if self.debug:
            print(f"\n[{test_id}] Running: {input_text[:50]}...")

        start_time = datetime.now()

        try:
            # Create context
            ctx = RequestContext(
                user_question=input_text,
                os=test_case.get("os"),
                role=test_case.get("role"),
                security_level=test_case.get("security_level", "balanced"),
                zt_maturity=test_case.get("zt_maturity", "medium"),
            )

            # Run pipeline
            result = self.pipeline.run(ctx)

            # Calculate latency
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000

            # Extract results
            actual_intent = result.intent.type if result.intent else "unknown"
            actual_layer_path = result.layer_path or "unknown"
            actual_safety = result.safety.category if result.safety else "unknown"

            # Check if passed
            intent_match = actual_intent == test_case.get("expected_intent")
            layer_match = actual_layer_path.startswith(test_case.get("expected_layer_path", ""))
            safety_match = actual_safety == test_case.get("expected_safety")

            # Overall pass: intent + layer path must match
            passed = intent_match and layer_match

            if self.debug:
                status = "[PASS]" if passed else "[FAIL]"
                print(f"  {status}")
                if not passed:
                    print(f"    Expected intent: {test_case.get('expected_intent')}, Got: {actual_intent}")
                    print(f"    Expected layer: {test_case.get('expected_layer_path')}, Got: {actual_layer_path}")

            return TestResult(
                test_id=test_id,
                input=input_text,
                passed=passed,
                expected_intent=test_case.get("expected_intent", ""),
                actual_intent=actual_intent,
                expected_layer_path=test_case.get("expected_layer_path", ""),
                actual_layer_path=actual_layer_path,
                expected_safety=test_case.get("expected_safety", ""),
                actual_safety=actual_safety,
                latency_ms=latency_ms,
                cost=result.estimated_cost or 0.0,
                error=None
            )

        except Exception as e:
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000

            if self.debug:
                print(f"  [ERROR] {str(e)}")

            return TestResult(
                test_id=test_id,
                input=input_text,
                passed=False,
                expected_intent=test_case.get("expected_intent", ""),
                actual_intent="error",
                expected_layer_path=test_case.get("expected_layer_path", ""),
                actual_layer_path="error",
                expected_safety=test_case.get("expected_safety", ""),
                actual_safety="error",
                latency_ms=latency_ms,
                cost=0.0,
                error=str(e)
            )

    def run_evaluation(
        self,
        test_cases: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None
    ) -> EvaluationMetrics:
        """
        Run evaluation on test dataset

        Args:
            test_cases: Optional list of test cases (default: all)
            tags: Optional list of tags to filter by

        Returns:
            EvaluationMetrics
        """
        # Select test cases
        if test_cases is None:
            if tags:
                test_cases = []
                for tag in tags:
                    test_cases.extend(get_test_cases_by_tag(tag))
                # Remove duplicates
                seen = set()
                unique_cases = []
                for tc in test_cases:
                    if tc["id"] not in seen:
                        seen.add(tc["id"])
                        unique_cases.append(tc)
                test_cases = unique_cases
            else:
                test_cases = TEST_DATASET

        print(f"\n{'='*70}")
        print(f"PIPELINE EVALUATION")
        print(f"{'='*70}")
        print(f"Total test cases: {len(test_cases)}")
        if tags:
            print(f"Filtered by tags: {', '.join(tags)}")
        print(f"{'='*70}\n")

        # Run all test cases
        self.results = []
        for test_case in test_cases:
            result = self.run_test_case(test_case)
            self.results.append(result)

        # Calculate metrics
        metrics = self._calculate_metrics()

        # Print results
        self._print_results(metrics)

        return metrics

    def _calculate_metrics(self) -> EvaluationMetrics:
        """Calculate aggregated metrics"""
        total = len(self.results)
        if total == 0:
            return EvaluationMetrics(
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                accuracy=0.0,
                avg_latency_ms=0.0,
                total_cost=0.0,
                intent_accuracy=0.0,
                layer_path_accuracy=0.0,
                safety_accuracy=0.0,
                errors=0
            )

        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed

        intent_correct = sum(1 for r in self.results if r.expected_intent == r.actual_intent)
        layer_correct = sum(1 for r in self.results if r.actual_layer_path.startswith(r.expected_layer_path))
        safety_correct = sum(1 for r in self.results if r.expected_safety == r.actual_safety)

        errors = sum(1 for r in self.results if r.error is not None)

        avg_latency = sum(r.latency_ms for r in self.results) / total
        total_cost = sum(r.cost for r in self.results)

        return EvaluationMetrics(
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            accuracy=passed / total,
            avg_latency_ms=avg_latency,
            total_cost=total_cost,
            intent_accuracy=intent_correct / total,
            layer_path_accuracy=layer_correct / total,
            safety_accuracy=safety_correct / total,
            errors=errors
        )

    def _print_results(self, metrics: EvaluationMetrics):
        """Print evaluation results"""
        print(f"\n{'='*70}")
        print(f"RESULTS")
        print(f"{'='*70}\n")

        print(f"Overall:")
        print(f"  Total Tests:    {metrics.total_tests}")
        print(f"  Passed:         {metrics.passed_tests} ({metrics.accuracy*100:.1f}%)")
        print(f"  Failed:         {metrics.failed_tests}")
        print(f"  Errors:         {metrics.errors}")

        print(f"\nAccuracy by Component:")
        print(f"  Intent Detection:    {metrics.intent_accuracy*100:.1f}%")
        print(f"  Layer Routing:       {metrics.layer_path_accuracy*100:.1f}%")
        print(f"  Safety Classification: {metrics.safety_accuracy*100:.1f}%")

        print(f"\nPerformance:")
        print(f"  Avg Latency:    {metrics.avg_latency_ms:.0f}ms")
        print(f"  Total Cost:     ${metrics.total_cost:.4f}")
        print(f"  Avg Cost/Query: ${metrics.total_cost/metrics.total_tests:.6f}")

        # Failed tests summary
        failed_results = [r for r in self.results if not r.passed]
        if failed_results:
            print(f"\nFailed Tests ({len(failed_results)}):")
            for r in failed_results[:10]:  # Show first 10
                print(f"  [{r.test_id}] {r.input[:50]}...")
                print(f"    Expected: intent={r.expected_intent}, layer={r.expected_layer_path}")
                print(f"    Got:      intent={r.actual_intent}, layer={r.actual_layer_path}")
                if r.error:
                    print(f"    Error: {r.error}")

        print(f"\n{'='*70}\n")

    def save_results(self, filepath: str):
        """Save results to JSON file"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "metrics": asdict(self._calculate_metrics()),
            "results": [asdict(r) for r in self.results]
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Results saved to: {filepath}")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Pipeline Evaluator")
    parser.add_argument("--tags", type=str, help="Comma-separated tags to filter (e.g., 'smalltalk,info')")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--save", type=str, help="Save results to file (e.g., 'results.json')")

    args = parser.parse_args()

    # Parse tags
    tags = args.tags.split(",") if args.tags else None

    print("Initializing pipeline...")

    # Get LLM clients
    try:
        llm_small, llm_large = get_llm_clients()
    except Exception as e:
        print(f"ERROR: Failed to initialize LLM clients: {e}")
        print("\nMake sure you have set up .env file with API keys:")
        print("  - GROQ_API_KEY (required)")
        print("  - OPENAI_API_KEY (optional)")
        sys.exit(1)

    # Create pipeline
    pipeline = SecurityPipeline(
        llm_small=llm_small,
        llm_large=llm_large,
        use_rag=True,
        debug=args.debug
    )

    # Create evaluator
    evaluator = PipelineEvaluator(pipeline=pipeline, debug=args.debug)

    # Run evaluation
    metrics = evaluator.run_evaluation(tags=tags)

    # Save results if requested
    if args.save:
        evaluator.save_results(args.save)

    # Exit with appropriate code
    if metrics.accuracy < 0.9:
        print("\nWARNING: Accuracy below 90%!")
        sys.exit(1)
    else:
        print(f"\nSUCCESS: Accuracy {metrics.accuracy*100:.1f}%")
        sys.exit(0)


if __name__ == "__main__":
    main()
