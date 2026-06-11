"""
Intent: SAF BİLGİ-SORU override regresyonu.

Canlı bug: "ubuntu 20 ssh için konfigürasyon dosyası NEREDE?" → ML "konfigürasyon→script"
sanıp action verdi → 3C bir hardening script ÜRETTİ. Doğrusu: "nerede/nedir/hangi" gibi
saf bilgi-soru kelimesi + imperative YOK → bilgi (3B açıklama). imperative override'ının
simetriği; whack-a-mole değil (evrensel soru kelimeleri).
"""

from __future__ import annotations

import pytest

from llm.pipelines.layers.hybrid_intent_detector import HybridIntentDetector


class TestIsInfoQuestionHelper:
    """Deterministik (ML'siz) — _is_info_question sadece dilbilgisel soru kelimesi bakar."""

    @pytest.mark.parametrize("q", [
        "konfigürasyon dosyası nerede", "ssh nedir", "bu ne demek",
        "hangi portları açmalıyım", "ne işe yarar", "where is the config",
        "what is ssh", "which firewall",
    ])
    def test_detects_info_question(self, q):
        d = HybridIntentDetector(use_ml=False)
        assert d._is_info_question(q) is True

    @pytest.mark.parametrize("q", [
        "ufw firewall oluştur", "ssh sıkılaştır", "scripti yaz", "harden ssh now",
    ])
    def test_non_question_not_flagged(self, q):
        d = HybridIntentDetector(use_ml=False)
        assert d._is_info_question(q) is False


class TestEndToEndOverride:
    """ML 'action' dese bile saf bilgi-sorusu → info; imperative ise action KALIR."""

    @pytest.fixture(scope="class")
    def det(self):
        return HybridIntentDetector(use_ml=True)

    @pytest.mark.parametrize("q", [
        "ubuntu 20 ssh için konfigürasyon dosyası nerede",
        "ssh config dosyası nerede",
        "hangi portları açmalıyım",
    ])
    def test_info_question_routed_to_info(self, det, q):
        assert det.detect(q).type == "info_request"

    @pytest.mark.parametrize("q", [
        "ufw firewall oluştur",                         # imperative → action
        "ubuntu için ssh sıkılaştırma scripti yaz",     # imperative + soru kelimesi yok
    ])
    def test_imperative_stays_action(self, det, q):
        assert det.detect(q).type == "action_request"
