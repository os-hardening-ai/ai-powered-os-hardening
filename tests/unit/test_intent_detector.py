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


# Modül düzeyi sahte sınıflar (joblib pickle edemez ama load_models'ı monkeypatch'lediğimiz
# için pickle gerekmez — load doğrudan bu örnekleri döndürür).
class _BrokenModel:
    """Yüklenir ama predict edemez — sklearn sürüm-uyumsuzluğunu simüle eder."""
    classes_ = ["info_request"]
    def predict(self, X):
        raise AttributeError("'LogisticRegression' object has no attribute 'multi_class'")
    def predict_proba(self, X):
        raise AttributeError("'LogisticRegression' object has no attribute 'multi_class'")


class _OkVectorizer:
    def transform(self, texts):
        return texts  # _BrokenModel.predict zaten patlar


class TestVersionMismatchGuard:
    """load_models() sürüm-uyumsuzluğunda (model yüklenir ama predict edemez) sessizce
    bozuk tahmin döndürmek yerine NET hata vermeli → 'retrain et' yönlendirmesi.

    (Kök neden: .joblib sklearn 1.8 ile pickle'lanıp ortamda 1.5 olunca
    LogisticRegression.multi_class AttributeError → eskiden info_request@0.5'e düşüyordu.)
    """

    def test_predict_failure_raises_with_retrain_hint(self, tmp_path, monkeypatch):
        # __init__ dosya varsa load_models()'ı kendisi çağırır → RuntimeError init'te atılır.
        # Sahte yol DOSYASI YOK (exists False) → init load yapmaz; load_models elle çağrılır.
        from llm.ml import intent_detector as mod
        from llm.ml.intent_detector import MLIntentDetector
        seq = [_BrokenModel(), _OkVectorizer()]
        monkeypatch.setattr(mod.joblib, "load", lambda _p: seq.pop(0))
        # exists() True döndür ama init'i atla: önce var-olmayan yolla kur, sonra patch'le
        det = MLIntentDetector(model_path=str(tmp_path / "nope.joblib"),
                               vectorizer_path=str(tmp_path / "nope2.joblib"))
        assert det.is_trained is False         # init yükleyemedi (dosya yok)
        monkeypatch.setattr(mod.Path, "exists", lambda self: True)
        with pytest.raises(RuntimeError, match="retrain_intent"):
            det.load_models()
        assert det.is_trained is False         # sessiz "yüklendi" demesin

    def test_hybrid_detector_falls_back_when_model_broken(self):
        """ML kapalıyken HybridIntentDetector pattern-only çalışır, ÇÖKMEZ (fallback sözleşmesi)."""
        det = HybridIntentDetector(use_ml=False)
        assert det.detect("merhaba").type == "smalltalk"
