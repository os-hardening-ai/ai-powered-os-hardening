"""
Unit tests for the hybrid intent detector (ML + pattern).

Uses the REAL trained model (llm/ml/models/*.joblib) — this is a fast, local,
deterministic classifier (no network, no API key), so it is appropriate for the
unit tier. We assert the contract (valid intent type returned) and that obvious
inputs route sensibly, rather than pinning exact ML probabilities.
"""

from __future__ import annotations

import pytest

from llm.pipelines.layers.hybrid_intent_detector import HybridIntentDetector, HybridIntent


@pytest.fixture(scope="module")
def detector():
    return HybridIntentDetector(use_ml=True)


VALID_TYPES = {
    "smalltalk", "info_request", "action_request", "out_of_scope", "unknown",
}


class TestContract:
    @pytest.mark.parametrize("q", [
        "merhaba",
        "Firewall nedir?",
        "Ubuntu 24.04 için SSH hardening scripti yaz",
        "bugün hava nasıl?",
        "teşekkürler",
        "CIS Benchmark 5.2 PermitRootLogin nasıl ayarlanır",
    ])
    def test_returns_valid_intent(self, detector, q):
        intent = detector.detect(q)
        assert isinstance(intent, HybridIntent)
        assert intent.type in VALID_TYPES
        assert 0.0 <= intent.confidence <= 1.0

    def test_empty_question_handled(self, detector):
        intent = detector.detect("")
        assert isinstance(intent, HybridIntent)


class TestRoutingSanity:
    def test_greeting_is_smalltalk(self, detector):
        assert detector.detect("selam").type == "smalltalk"

    def test_script_request_is_action(self, detector):
        intent = detector.detect("Ubuntu sunucum için bir bash hardening scripti oluştur")
        # action_request expected; tolerate info_request if model is conservative
        assert intent.type in {"action_request", "info_request"}


class TestPatternFallback:
    def test_works_without_ml(self):
        det = HybridIntentDetector(use_ml=False)
        intent = det.detect("merhaba")
        assert intent.type in VALID_TYPES
