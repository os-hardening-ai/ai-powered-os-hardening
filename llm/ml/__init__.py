"""
Machine Learning Module
========================

ML models for intent detection and evaluation.

## Components:

- **Intent Detector** (`intent_detector.py`):
  - Logistic Regression classifier
  - TF-IDF vectorization
  - 1,230 training examples
  - 97% accuracy

- **Evaluation** (`evaluation/`):
  - Dataset management
  - Model evaluation tools
"""

try:
    from .intent_detector import MLIntentDetector
    ML_AVAILABLE = True
except ImportError as exc:
    ML_AVAILABLE = False
    print(f"[WARNING] ML models not available: {exc}")

__all__ = [
    "MLIntentDetector",
    "ML_AVAILABLE",
]
