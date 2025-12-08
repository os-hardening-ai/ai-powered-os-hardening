# Testing Guide

Complete guide for testing the AI-Powered OS Hardening system.

## Test Organization

All test files are organized in the `tests/` folder:

```
tests/
├── unit/               # Unit tests for individual components
│   └── test_groq_models.py
├── integration/        # Integration tests
│   ├── test_rag_llm_integration.py
│   └── test_single_turn_chat.py
├── test_dataset.py     # 50 test cases for evaluation
├── pipeline_evaluator.py   # Automated pipeline evaluation
└── run_all_tests.py    # Universal test runner
```

## Quick Start

### Run All Tests
```bash
# Run all tests in the test suite
python tests/run_all_tests.py
```

### Run Specific Test Types
```bash
# Unit tests only
python tests/run_all_tests.py --unit

# Integration tests only
python tests/run_all_tests.py --integration

# Pipeline evaluation only
python tests/run_all_tests.py --pipeline
```

## Test Types

### 1. Single-Turn Chat Test
**Purpose**: Verify that users can ask a single question and receive an answer without multiple interactions.

**Location**: `tests/integration/test_single_turn_chat.py`

**Run**:
```bash
python tests/integration/test_single_turn_chat.py
```

**Tests**:
- Smalltalk interaction
- Info request
- Action request (script generation)
- Out-of-scope query handling
- Unsafe query rejection

**Expected Results**:
- All 5 tests should pass
- Each test completes in <5 seconds
- Responses match expected layer paths

### 2. Pipeline Evaluation
**Purpose**: Automated evaluation of the entire 4-layer security pipeline with 50 test cases.

**Location**: `tests/pipeline_evaluator.py`

**Run**:
```bash
# Evaluate all 50 test cases
python tests/pipeline_evaluator.py

# Evaluate specific tags
python tests/pipeline_evaluator.py --tags smalltalk,info

# Save results to file
python tests/pipeline_evaluator.py --save results.json

# Verbose output
python tests/pipeline_evaluator.py --verbose
```

**Metrics Tracked**:
- **Accuracy**: Percentage of tests passed
- **Intent Accuracy**: Correct intent detection rate
- **Routing Accuracy**: Correct layer path selection
- **Safety Accuracy**: Correct safety classification
- **Average Latency**: Mean response time in milliseconds
- **Total Cost**: Estimated API cost for all tests

**Test Dataset Coverage** (50 test cases):
- Smalltalk: 8 cases
- Info requests: 19 cases
- Action requests: 11 cases
- Out-of-scope: 7 cases
- Unsafe queries: 5 cases

**Expected Performance**:
- Overall accuracy: >95%
- Intent accuracy: >97%
- Routing accuracy: >95%
- Safety accuracy: >99%
- Average latency: <2000ms
- Total cost: <$0.20

### 3. RAG-LLM Integration Test
**Purpose**: Verify RAG (Retrieval-Augmented Generation) integration with LLM.

**Location**: `tests/integration/test_rag_llm_integration.py`

**Run**:
```bash
python tests/integration/test_rag_llm_integration.py
```

**Tests**:
- Vector database connectivity
- Document retrieval quality
- RAG-enhanced response generation
- Source citation accuracy

### 4. Groq Models Test
**Purpose**: Test Groq LLM API connectivity and model switching.

**Location**: `tests/unit/test_groq_models.py`

**Run**:
```bash
python tests/unit/test_groq_models.py
```

**Tests**:
- API connectivity
- Model availability (llama-3.3-70b, llama-3.1-8b)
- Response quality
- Error handling

## Test Dataset

**Location**: `tests/test_dataset.py`

**Total Cases**: 50 test cases

**Categories**:

### By Intent
- `smalltalk`: 8 cases - Greetings, thanks, farewells
- `info_request`: 19 cases - Questions about security concepts
- `action_request`: 11 cases - Script generation requests
- `out_of_scope`: 7 cases - Non-security topics (weather, food, sports)
- `unsafe`: 5 cases - Malicious or unethical requests

### By OS Type
- Ubuntu 22.04: 5 cases
- Windows 10/Server 2022: 4 cases
- Debian 11: 1 case
- CentOS/RHEL: 2 cases
- Generic: 38 cases

### By Complexity
- Simple: 30 cases
- Medium: 15 cases
- Complex: 5 cases

### Special Categories
- Edge cases: 4 cases (empty input, whitespace, special chars)
- Multilingual: 3 cases (English queries)
- Performance tests: 2 cases (minimal and very long inputs)
- Regression tests: 2 cases (previous bug fixes)

## Running Tests in CI/CD

### GitHub Actions Example
```yaml
name: Test Suite
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run all tests
        run: python tests/run_all_tests.py
```

## Test Configuration

### Environment Variables
```bash
# Required for Groq API
export GROQ_API_KEY="your-api-key"

# Optional: Test verbosity
export TEST_VERBOSE=1

# Optional: Skip slow tests
export SKIP_SLOW_TESTS=1
```

### Test Data
Test data is self-contained in `tests/test_dataset.py`. No external test data files required.

## Interpreting Results

### Success Criteria
```
[PASS] All 5 single-turn tests passed
[PASS] Pipeline evaluation: 95%+ accuracy
[PASS] RAG integration: Sources retrieved correctly
[PASS] Groq models: Both models responding
```

### Common Failures

**Intent Misclassification**:
- Symptom: Test expects `info_request`, gets `action_request`
- Cause: Ambiguous query or keyword overlap
- Fix: Improve intent detection keywords or use LLM-based detection

**Layer Path Mismatch**:
- Symptom: Expected `1→2→3B`, got `1→2→3C`
- Cause: Intent triggers wrong routing
- Fix: Adjust routing logic in `pipeline_v2.py`

**High Latency**:
- Symptom: Average latency >3000ms
- Cause: RAG retrieval or LLM response slow
- Fix: Check network, optimize RAG queries, use smaller model

**High Cost**:
- Symptom: Total cost >$0.50 for 50 tests
- Cause: Using large model for all queries
- Fix: Ensure small model (llama-3.1-8b) used for Layer 1 & 2

## Adding New Tests

### Add to Test Dataset
Edit `tests/test_dataset.py`:

```python
{
    "id": "your_test_id",
    "input": "Your test query",
    "expected_intent": "info_request",  # or action_request, smalltalk, out_of_scope
    "expected_layer_path": "1→2→3B",
    "expected_safety": "safe_educational",
    "os": "ubuntu_22_04",  # optional
    "description": "What this test verifies",
    "tags": ["info", "ubuntu", "custom_tag"]
}
```

### Add Integration Test
Create new file in `tests/integration/`:

```python
"""
Your test description
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from llm.pipeline_v2 import SecurityPipeline, RequestContext
from llm.models import get_llm_clients

def test_your_feature():
    llm_small, llm_large = get_llm_clients()
    pipeline = SecurityPipeline(llm_small=llm_small, llm_large=llm_large)

    ctx = RequestContext(user_input="Your test query", os_type="ubuntu_22_04")
    result = pipeline.run(ctx)

    assert result.success, "Test should pass"
    print("[PASS] Your test passed")

if __name__ == "__main__":
    test_your_feature()
```

## Continuous Monitoring

### Performance Benchmarks
Run weekly to track performance trends:

```bash
# Run and save results with timestamp
python tests/pipeline_evaluator.py --save "results_$(date +%Y%m%d).json"
```

### Compare Results
```bash
# Compare two evaluation runs
python tests/compare_results.py results_20250101.json results_20250201.json
```

## Troubleshooting

### Tests Won't Run
```bash
# Check Python version (requires 3.10+)
python --version

# Verify dependencies
pip install -r requirements.txt

# Check GROQ_API_KEY
echo $GROQ_API_KEY
```

### API Rate Limiting
If you hit rate limits during testing:
- Add delays between tests: `time.sleep(1)`
- Run smaller test subsets: `--tags smalltalk`
- Use mock responses for unit tests

### Test Timeouts
If tests timeout:
- Increase timeout in test files
- Check network connectivity
- Verify Groq API status

## Best Practices

1. **Run tests before commits**: Always run `python tests/run_all_tests.py` before pushing
2. **Add regression tests**: When fixing bugs, add test cases to prevent recurrence
3. **Tag tests appropriately**: Use descriptive tags for easy filtering
4. **Monitor costs**: Track API costs during development
5. **Version test results**: Save evaluation results for comparison over time

## Resources

- [Test Dataset](../tests/test_dataset.py) - 50 test cases
- [Pipeline Evaluator](../tests/pipeline_evaluator.py) - Evaluation engine
- [Run All Tests](../tests/run_all_tests.py) - Universal test runner
- [Examples](../examples/) - Example usage scripts
