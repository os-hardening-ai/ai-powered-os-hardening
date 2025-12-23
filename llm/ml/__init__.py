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
    from .intent_detector import MLIntentDetector, train_intent_model
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("[WARNING] ML models not available")

__all__ = [
    "MLIntentDetector",
    "train_intent_model",
    "ML_AVAILABLE",
]
