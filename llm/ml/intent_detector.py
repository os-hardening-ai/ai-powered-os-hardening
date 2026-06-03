# ml_intent_detector.py
"""
ML-Based Intent Detection using Logistic Regression + SVM

Features:
1. TF-IDF vectorization for text features
2. Logistic Regression as primary classifier
3. SVM as secondary classifier for ensemble
4. Model persistence with joblib
5. Hybrid approach: ML primary, pattern fallback

Dataset: 1161+ labeled examples
- greeting (200)
- farewell (150)
- thanks (100)
- help (100)
- info_request (325)
- action_request (231)
- out_of_scope (132)
"""

from __future__ import annotations
from typing import Literal, Optional, Tuple
from dataclasses import dataclass
import re
import os
import joblib
import pandas as pd
import numpy as np
from pathlib import Path

# Scikit-learn imports
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.ensemble import VotingClassifier


# Intent types
IntentType = Literal[
    "greeting",
    "farewell",
    "thanks",
    "help",
    "info_request",
    "action_request",
    "out_of_scope"
]


@dataclass
class MLIntent:
    """ML-based intent detection result"""
    type: IntentType
    confidence: float  # 0.0 - 1.0 (probability from model)
    method: str = "ml"  # ml / pattern / hybrid
    probabilities: dict = None  # All class probabilities

    def __post_init__(self):
        if self.probabilities is None:
            self.probabilities = {}


class MLIntentDetector:
    """
    Machine Learning based intent detector

    Uses:
    - TF-IDF for feature extraction
    - Logistic Regression (primary, fast, probabilistic)
    - LinearSVM (secondary, more robust)
    - Voting ensemble for final prediction

    Performance:
    - Training: ~1161 examples
    - Expected accuracy: 92-96%
    - Latency: ~5-10ms per prediction
    - Cost: $0 (no API calls)
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        vectorizer_path: Optional[str] = None,
        debug: bool = False
    ):
        """
        Initialize ML intent detector

        Args:
            model_path: Path to saved model file
            vectorizer_path: Path to saved vectorizer file
            debug: Enable debug logging
        """
        self.debug = debug
        self.model = None
        self.vectorizer = None
        self.label_encoder = None
        self.is_trained = False

        # Default paths - models are in llm/ml/models/
        if model_path is None:
            model_path = Path(__file__).parent / "models" / "intent_model.joblib"
        if vectorizer_path is None:
            vectorizer_path = Path(__file__).parent / "models" / "intent_vectorizer.joblib"

        self.model_path = Path(model_path)
        self.vectorizer_path = Path(vectorizer_path)

        # Try to load existing models
        if self.model_path.exists() and self.vectorizer_path.exists():
            self.load_models()

    def preprocess_text(self, text: str) -> str:
        """
        Preprocess text for feature extraction

        Args:
            text: Raw input text

        Returns:
            Preprocessed text
        """
        # Lowercase
        text = text.lower().strip()

        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        return text

    def train(
        self,
        dataset_path: str,
        test_size: float = 0.2,
        random_state: int = 42
    ) -> dict:
        """
        Train ML models on intent dataset

        Args:
            dataset_path: Path to CSV file with 'text' and 'intent' columns
            test_size: Fraction of data for testing (default 0.2)
            random_state: Random seed for reproducibility

        Returns:
            Training metrics dict
        """
        print(f"[MLIntentDetector] Loading dataset from {dataset_path}...")

        # Load dataset
        df = pd.read_csv(dataset_path)

        if 'text' not in df.columns or 'intent' not in df.columns:
            raise ValueError("Dataset must have 'text' and 'intent' columns")

        # Statistics
        print(f"[MLIntentDetector] Total examples: {len(df)}")
        print(f"[MLIntentDetector] Intent distribution:")
        print(df['intent'].value_counts())

        # Preprocess
        df['text_clean'] = df['text'].apply(self.preprocess_text)

        # Split data
        X = df['text_clean'].values
        y = df['intent'].values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )

        print(f"\n[MLIntentDetector] Training set: {len(X_train)} examples")
        print(f"[MLIntentDetector] Test set: {len(X_test)} examples")

        # Create TF-IDF vectorizer
        print("\n[MLIntentDetector] Creating TF-IDF vectorizer...")
        self.vectorizer = TfidfVectorizer(
            max_features=5000,  # Limit vocabulary size
            ngram_range=(1, 3),  # Unigrams, bigrams, trigrams
            min_df=2,  # Ignore terms appearing in <2 documents
            max_df=0.8,  # Ignore terms appearing in >80% of documents
            sublinear_tf=True,  # Use sublinear TF scaling
            strip_accents='unicode',
            analyzer='word',
            token_pattern=r'\w{2,}',  # Words with 2+ characters
        )

        # Fit vectorizer on training data
        X_train_vec = self.vectorizer.fit_transform(X_train)
        X_test_vec = self.vectorizer.transform(X_test)

        print(f"[MLIntentDetector] Vocabulary size: {len(self.vectorizer.vocabulary_)}")
        print(f"[MLIntentDetector] Feature matrix shape: {X_train_vec.shape}")

        # Train Logistic Regression (primary classifier)
        print("\n[MLIntentDetector] Training Logistic Regression...")
        lr_model = LogisticRegression(
            max_iter=1000,
            C=1.0,  # Regularization strength
            solver='lbfgs',  # Fast solver
            # Note: multi_class='multinomial' is now default in sklearn 1.5+
            random_state=random_state,
            n_jobs=-1  # Use all CPU cores
        )
        lr_model.fit(X_train_vec, y_train)

        # Evaluate LR
        lr_train_score = lr_model.score(X_train_vec, y_train)
        lr_test_score = lr_model.score(X_test_vec, y_test)
        print(f"[MLIntentDetector] LR Train accuracy: {lr_train_score:.4f}")
        print(f"[MLIntentDetector] LR Test accuracy: {lr_test_score:.4f}")

        # Train SVM (secondary classifier)
        print("\n[MLIntentDetector] Training LinearSVC...")
        svm_model = LinearSVC(
            C=1.0,
            max_iter=1000,
            random_state=random_state,
            dual=False  # Faster for n_samples > n_features
        )
        svm_model.fit(X_train_vec, y_train)

        # Evaluate SVM
        svm_train_score = svm_model.score(X_train_vec, y_train)
        svm_test_score = svm_model.score(X_test_vec, y_test)
        print(f"[MLIntentDetector] SVM Train accuracy: {svm_train_score:.4f}")
        print(f"[MLIntentDetector] SVM Test accuracy: {svm_test_score:.4f}")

        # Create voting ensemble (soft voting uses probabilities)
        # Note: LinearSVC doesn't support predict_proba, so use LR as primary
        print("\n[MLIntentDetector] Creating ensemble model...")
        self.model = lr_model  # Use LR as primary (has predict_proba)

        # Predictions
        y_pred = self.model.predict(X_test_vec)

        # Detailed metrics
        print("\n[MLIntentDetector] Classification Report:")
        print(classification_report(y_test, y_pred))

        print("\n[MLIntentDetector] Confusion Matrix:")
        print(confusion_matrix(y_test, y_pred))

        # Cross-validation
        print("\n[MLIntentDetector] Cross-validation (5-fold)...")
        cv_scores = cross_val_score(
            self.model, X_train_vec, y_train, cv=5, scoring='accuracy'
        )
        print(f"[MLIntentDetector] CV scores: {cv_scores}")
        print(f"[MLIntentDetector] CV mean: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

        self.is_trained = True

        # Return metrics
        metrics = {
            "train_accuracy": lr_train_score,
            "test_accuracy": lr_test_score,
            "cv_mean": cv_scores.mean(),
            "cv_std": cv_scores.std(),
            "n_train": len(X_train),
            "n_test": len(X_test),
            "n_features": X_train_vec.shape[1]
        }

        return metrics

    def save_models(self):
        """Save trained models to disk"""
        if not self.is_trained:
            raise ValueError("Models not trained yet. Call train() first.")

        # Create models directory if not exists
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

        # Save model and vectorizer
        joblib.dump(self.model, self.model_path)
        joblib.dump(self.vectorizer, self.vectorizer_path)

        print(f"[MLIntentDetector] Models saved:")
        print(f"  - Model: {self.model_path}")
        print(f"  - Vectorizer: {self.vectorizer_path}")

    def load_models(self):
        """Load trained models from disk"""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        if not self.vectorizer_path.exists():
            raise FileNotFoundError(f"Vectorizer file not found: {self.vectorizer_path}")

        self.model = joblib.load(self.model_path)
        self.vectorizer = joblib.load(self.vectorizer_path)
        self.is_trained = True

        # SÜRÜM-UYUMSUZLUĞU SMOKE-TEST: model FARKLI bir scikit-learn sürümüyle pickle
        # edilmişse (.joblib eski), predict()/predict_proba() çalışma anında AttributeError
        # atabilir (ör. LogisticRegression.multi_class kaldırıldı). Bu durumda sessizce
        # bozuk tahmin döndürmek yerine YÜKLEMEDE net hata ver → çağıran fallback'e düşer
        # ve "modeli retrain et (scripts/retrain_intent.py)" mesajı loglanır.
        try:
            _v = self.vectorizer.transform([self.preprocess_text("ssh nedir")])
            self.model.predict(_v)
            self.model.predict_proba(_v)
        except Exception as exc:
            self.is_trained = False
            self.model = None
            self.vectorizer = None
            raise RuntimeError(
                f"Intent modeli yüklenebildi ama tahmin edemiyor "
                f"({type(exc).__name__}: {exc}). Büyük olasılıkla scikit-learn sürüm "
                f"uyumsuzluğu — modeli yeniden eğit: python scripts/retrain_intent.py"
            ) from exc

        if self.debug:
            print(f"[MLIntentDetector] Models loaded successfully")

    def predict(self, text: str) -> MLIntent:
        """
        Predict intent for input text

        Args:
            text: User input text

        Returns:
            MLIntent with prediction and confidence
        """
        if not self.is_trained:
            raise ValueError("Models not trained. Call train() or load_models() first.")

        # Preprocess
        text_clean = self.preprocess_text(text)

        # Vectorize
        text_vec = self.vectorizer.transform([text_clean])

        # Predict
        intent_type = self.model.predict(text_vec)[0]

        # Get probabilities
        proba = self.model.predict_proba(text_vec)[0]
        classes = self.model.classes_

        # Create probability dict
        prob_dict = {cls: float(prob) for cls, prob in zip(classes, proba)}

        # Confidence is max probability
        confidence = float(proba.max())

        if self.debug:
            print(f"[MLIntentDetector] Text: '{text}'")
            print(f"[MLIntentDetector] Predicted: {intent_type} (confidence: {confidence:.4f})")
            print(f"[MLIntentDetector] Probabilities: {prob_dict}")

        return MLIntent(
            type=intent_type,  # type: ignore
            confidence=confidence,
            method="ml",
            probabilities=prob_dict
        )

    def predict_batch(self, texts: list[str]) -> list[MLIntent]:
        """
        Predict intents for multiple texts (batch processing)

        Args:
            texts: List of input texts

        Returns:
            List of MLIntent predictions
        """
        if not self.is_trained:
            raise ValueError("Models not trained. Call train() or load_models() first.")

        # Preprocess all
        texts_clean = [self.preprocess_text(t) for t in texts]

        # Vectorize all
        texts_vec = self.vectorizer.transform(texts_clean)

        # Predict all
        intent_types = self.model.predict(texts_vec)
        probas = self.model.predict_proba(texts_vec)
        classes = self.model.classes_

        # Create MLIntent objects
        results = []
        for intent_type, proba in zip(intent_types, probas):
            prob_dict = {cls: float(p) for cls, p in zip(classes, proba)}
            confidence = float(proba.max())

            results.append(MLIntent(
                type=intent_type,  # type: ignore
                confidence=confidence,
                method="ml",
                probabilities=prob_dict
            ))

        return results
