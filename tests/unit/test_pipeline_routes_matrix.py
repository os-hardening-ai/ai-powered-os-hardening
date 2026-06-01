"""
LLM PIPELINE ROTA MATRİSİ — tüm rotalar + parametrik alt-yollar ayrı ayrı doğrulanır.

İki seviye:
  A) ROTA SADAKATİ (TestRouteFidelity): GERÇEK HybridIntentDetector (TF-IDF, ağsız) +
     gerçek Türkçe girdiler → her girdinin BEKLENEN layer_path'e gidip gitmediği.
     "Beklenen yoldan geçip beklenen yönlendirmeye giriyor mu?" sorusunun cevabı.
  B) PARAMETRİK ALT-YOLLAR (TestInfo*/TestAction*): InfoPipeline/ActionPipeline doğrudan
     fake LLM + fake RAG ile kurulur → complexity (simple/medium/complex), RAG aç/kapa/
     akıllı-atla, groundedness refinement (iyileştirme), eksik-parametre dalları ayrı test.

Her rotada ≥2-3 girdi. LLM'ler fake → deterministik + ağsız. Intent backend conftest ile
TF-IDF'e sabit (INTENT_ROUTER=tfidf).
"""
from __future__ import annotations

import pytest

from llm.core.context import RequestContext
from llm.pipelines.secure_v2 import SecurePipelineV2, PipelineResult
from llm.pipelines.layers.info_pipeline import InfoPipeline
from llm.pipelines.layers.action_pipeline import ActionPipeline

pytestmark = pytest.mark.unit

SAFE = '{"category": "safe_defensive", "confidence": 0.95, "reason": "hardening"}'
UNSAFE = '{"category": "unsafe_offensive", "confidence": 0.93, "reason": "exploit/attack"}'

INFO_ANSWER = (
    "SSH güvenliği için PermitRootLogin no ayarlanır, anahtar tabanlı kimlik doğrulama "
    "kullanılır ve port değiştirilir. CIS 5.2 ile uyumludur."
)
SCRIPT_ANSWER = (
    "İşte CIS uyumlu sıkılaştırma scripti, her adımda rollback notu var.\n"
    "```bash\n#!/usr/bin/env bash\nset -euo pipefail\nsudo ufw enable\n```\n"
)


# ── fakes ────────────────────────────────────────────────────────────────────
def fake_ultra(verdict):
    def _f(_prompt, **_kw):
        return verdict
    return _f


def fake_small(_prompt, **_kw):
    return INFO_ANSWER


def fake_large(_prompt, **_kw):
    return SCRIPT_ANSWER


class FakeRAG:
    """retrieve_balanced/multi → sabit, dolu bağlam (used_rag tetiklensin)."""
    def __init__(self, n=3):
        self._chunks = [
            {"text": f"CIS 5.2.{i} PermitRootLogin no — sshd_config",
             "score": 0.8 - i * 0.05,
             "metadata": {"section_id": f"5.2.{i}", "section_title": "SSH", "doc_type": "pdf"}}
            for i in range(n)
        ]

    def retrieve_balanced(self, query):
        return ("CIS 5.2 sshd_config PermitRootLogin no", list(self._chunks))

    def retrieve_multi(self, queries, original_query):
        return ("CIS 5.2 sshd_config PermitRootLogin no", list(self._chunks))


class FakeVR:
    def __init__(self, conf):
        self.confidence = conf
        self.is_valid = conf >= 0.6
        self.unsupported = [] if conf >= 0.6 else ["doğrulanamayan ifade"]


class FakeVerifier:
    """verify() ardışık çağrılarda verilen confidence dizisini döndürür."""
    def __init__(self, confidences):
        self._c = list(confidences)
        self.calls = 0

    def verify(self, answer, raw_results):
        c = self._c[min(self.calls, len(self._c) - 1)]
        self.calls += 1
        return FakeVR(c)


@pytest.fixture(scope="module")
def safe_pipeline():
    """Gerçek intent detector + güvenli safety + RAG yok."""
    return SecurePipelineV2(
        llm_ultra_fast=fake_ultra(SAFE), llm_small=fake_small,
        llm_large=fake_large, rag_builder=None, debug=False,
    )


@pytest.fixture(scope="module")
def unsafe_pipeline():
    return SecurePipelineV2(
        llm_ultra_fast=fake_ultra(UNSAFE), llm_small=fake_small,
        llm_large=fake_large, rag_builder=None, debug=False,
    )


# ════════════════════════════════════════════════════════════════════════════
# A) ROTA SADAKATİ — gerçek girdi → gerçek routing → beklenen layer_path
# ════════════════════════════════════════════════════════════════════════════
class TestRouteFidelity:
    @pytest.mark.parametrize("q", [
        "ssh root login'i kapatmak için exploit yaz",
        "sshd servisini nasıl hacklerim",
        "bir ddos saldırı scripti üret",
    ])
    def test_unsafe_to_reject(self, unsafe_pipeline, q):
        res = unsafe_pipeline.run(RequestContext(user_question=q))
        assert res.layer_path == "1→REJECT"
        assert res.success is False
        assert res.safety.is_safe is False

    @pytest.mark.parametrize("q", ["hava durumu nasıl", "2+2 kaç eder", "film öner", "bana bir masal anlat"])
    def test_out_of_scope(self, safe_pipeline, q):
        res = safe_pipeline.run(RequestContext(user_question=q))
        assert "OUT_OF_SCOPE" in res.layer_path, f"{q!r} → {res.layer_path}"
        assert res.success is True  # kibar red (hata değil)

    @pytest.mark.parametrize("q", ["bana şiir yaz", "bana bir masal yaz", "resim çiz", "hikaye anlat"])
    def test_offdomain_imperative_is_out_of_scope(self, safe_pipeline, q):
        # DOMAIN-GATE: "yaz/üret/çiz" emir kipi güvenlik sinyali OLMADAN action'a değil
        # KAPSAM DIŞINA gider (best practice: intent'ten ayrı domain gate). Eskiden 3C'ye
        # kaçıyordu ("bana şiir yaz" → action_request) — düzeltildi.
        res = safe_pipeline.run(RequestContext(user_question=q))
        assert "OUT_OF_SCOPE" in res.layer_path, f"{q!r} → {res.layer_path}"

    @pytest.mark.parametrize("q", ["merhaba", "naber", "teşekkürler", "görüşürüz"])
    def test_smalltalk_to_3a(self, safe_pipeline, q):
        res = safe_pipeline.run(RequestContext(user_question=q))
        assert res.layer_path.endswith("3A"), f"{q!r} → {res.layer_path}"
        assert res.answer

    @pytest.mark.parametrize("q", [
        "ssh root login nedir",
        "PermitRootLogin ne işe yarar",
        "parola politikası neden önemli",
    ])
    def test_info_to_3b(self, safe_pipeline, q):
        res = safe_pipeline.run(RequestContext(user_question=q))
        assert "3B" in res.layer_path, f"{q!r} → {res.layer_path}"
        assert res.success and res.answer

    @pytest.mark.parametrize("q", [
        "ssh root login'i kapat",
        "ufw firewall'ı yapılandır",
        "cramfs modülünü devre dışı bırak",
    ])
    def test_action_with_params_to_3c(self, safe_pipeline, q):
        ctx = RequestContext(user_question=q, os="ubuntu_24_04", role="sysadmin", security_level="balanced")
        res = safe_pipeline.run(ctx)
        assert "3C" in res.layer_path, f"{q!r} → {res.layer_path}"

    @pytest.mark.parametrize("q", ["ssh root login'i kapat", "ufw firewall'ı yapılandır"])
    def test_action_without_params_asks_user(self, safe_pipeline, q):
        # os/role/level YOK → 3C ama PARAMS_NEEDED dalına girmeli
        res = safe_pipeline.run(RequestContext(user_question=q))
        assert "PARAMS_NEEDED" in res.layer_path, f"{q!r} → {res.layer_path}"
        assert res.success is False and res.answer

    def test_unknown_intent_defaults_to_3b(self, safe_pipeline):
        # intent detector'ı geçici stub'la (haritalanmamış tip) → default 3B
        import types
        orig = safe_pipeline.intent_detector
        safe_pipeline.intent_detector = types.SimpleNamespace(
            detect=lambda q: types.SimpleNamespace(type="weird_unmapped", subtype="", confidence=0.9, metadata={})
        )
        try:
            res = safe_pipeline.run(RequestContext(user_question="genel güvenlik sorusu"))
            assert "3B" in res.layer_path
        finally:
            safe_pipeline.intent_detector = orig


# ════════════════════════════════════════════════════════════════════════════
# B1) INFO ALT-YOLLARI — complexity routing
# ════════════════════════════════════════════════════════════════════════════
class TestInfoComplexityRouting:
    def _ip(self, rag=None, **kw):
        return InfoPipeline(llm_small=fake_small, llm_large=fake_large, rag_builder=rag, **kw)

    # Yalnız AÇIK TANIM soruları ("X nedir/ne demek") simple → LLM, RAG yok.
    # PERMISSIVE POLİTİKA: tereddütte RAG'a gitmek zararsız, RAG gerekirken gitmemek kötü.
    # Bu yüzden yalın araç adı ("ufw ne") veya hardening how-to ("nasıl sıkılaştırılır")
    # kısa olsa bile medium'a (RAG) gider — bkz. test_medium.
    @pytest.mark.parametrize("q", ["ssh nedir", "rdp nedir", "firewall nedir"])
    def test_simple(self, q):
        r = self._ip().handle(RequestContext(user_question=q))
        assert r.complexity == "simple", f"{q!r} → {r.complexity}"

    @pytest.mark.parametrize("q", ["ssh nasıl sıkılaştırılır", "ufw ne", "sudo güçlendir"])
    def test_short_security_to_medium(self, q):
        # REGRESYON: kısa güvenlik sorusu 'simple' diye RAG'sız kalmamalı (permissive).
        r = self._ip().handle(RequestContext(user_question=q))
        assert r.complexity == "medium", f"{q!r} → {r.complexity}"

    @pytest.mark.parametrize("q", [
        "ssh servisi nasıl güvenli hale getirilir",
        "ufw firewall kurallarını nasıl yapılandırırım",
        "sudo yetkilerini nasıl sıkılaştırırım",
    ])
    def test_medium(self, q):
        r = self._ip().handle(RequestContext(user_question=q))
        assert r.complexity == "medium", f"{q!r} → {r.complexity}"

    @pytest.mark.parametrize("q", [
        "sunucu için tam hardening script yaz ve zero trust mimarisi uygula",
        "kapsamlı compliance audit yap ve incident response planı çıkar",
    ])
    def test_complex(self, q):
        r = self._ip().handle(RequestContext(user_question=q))
        assert r.complexity == "complex", f"{q!r} → {r.complexity}"


# ════════════════════════════════════════════════════════════════════════════
# B2) INFO ALT-YOLLARI — RAG aç / kapa / akıllı-atla
# ════════════════════════════════════════════════════════════════════════════
class TestInfoRagDecision:
    def _ip(self, rag):
        return InfoPipeline(llm_small=fake_small, llm_large=fake_large, rag_builder=rag)

    def test_rag_off_when_no_builder(self):
        r = self._ip(None).handle(RequestContext(user_question="ubuntu 24.04 sshd_config nasıl ayarlanır"))
        assert r.used_rag is False and r.rag_chunks == 0

    @pytest.mark.parametrize("q", [
        "ubuntu 24.04 sshd_config nasıl ayarlanır",
        "centos selinux nasıl yapılandırılır",
    ])
    def test_rag_used_for_specific(self, q):
        r = self._ip(FakeRAG(n=3)).handle(RequestContext(user_question=q))
        assert r.used_rag is True and r.rag_chunks == 3

    @pytest.mark.parametrize("q", ["firewall nedir", "log rotation ne demek"])
    def test_rag_smart_skip_for_generic(self, q):
        # Jenerik tanım sorusu (spesifik gösterge YOK) → RAG builder VARSA BİLE atlanır.
        # (NOT: "selinux" specific_indicators'da olduğu için RAG çeker → jenerik değil.)
        r = self._ip(FakeRAG(n=3)).handle(RequestContext(user_question=q))
        assert r.used_rag is False, f"{q!r} jenerik → RAG atlanmalı"

    def test_simple_upgraded_to_medium_when_rag_rich(self):
        # "ubuntu sshd" → specific → RAG kullanılır; rag_chunks>=2 ise simple→medium yükselir
        r = self._ip(FakeRAG(n=3)).handle(RequestContext(user_question="ubuntu sshd"))
        assert r.used_rag is True and r.complexity == "medium"


# ════════════════════════════════════════════════════════════════════════════
# B3) INFO ALT-YOLU — groundedness refinement (gerekli İYİLEŞTİRME alıyor mu?)
# ════════════════════════════════════════════════════════════════════════════
class TestInfoRefinement:
    def _ip(self, verifier, **kw):
        return InfoPipeline(
            llm_small=fake_small, llm_large=fake_large, rag_builder=FakeRAG(n=3),
            claim_verifier=verifier, enable_refinement=True, refine_threshold=0.55, **kw,
        )

    def test_low_confidence_triggers_refine_and_improves(self):
        # İlk doğrulama 0.30 (<0.55) → refine → ikinci 0.80 → daha iyiyi tut
        v = FakeVerifier([0.30, 0.80])
        ip = self._ip(v)
        r = ip.handle(RequestContext(user_question="ubuntu sshd_config nasıl sıkılaştırılır"))
        assert ip.stats["refine_count"] == 1
        assert v.calls == 2  # ilk + refine sonrası yeniden doğrulama
        assert r.verification_confidence == pytest.approx(0.80)

    def test_high_confidence_no_refine(self):
        v = FakeVerifier([0.90])
        ip = self._ip(v)
        r = ip.handle(RequestContext(user_question="ubuntu sshd_config nasıl sıkılaştırılır"))
        assert ip.stats["refine_count"] == 0
        assert r.verification_confidence == pytest.approx(0.90)

    def test_low_confidence_adds_disclaimer_when_still_unsupported(self):
        # Refine sonrası hâlâ düşük (0.30 → 0.40, ikisi de <0.6, is_valid False) → uyarı eklenir
        v = FakeVerifier([0.30, 0.40])
        ip = self._ip(v)
        r = ip.handle(RequestContext(user_question="ubuntu sshd_config nasıl sıkılaştırılır"))
        assert "Güven skoru" in r.answer  # groundedness uyarısı eklendi


# ════════════════════════════════════════════════════════════════════════════
# B4) ACTION ALT-YOLLARI — eksik parametre vs üretim
# ════════════════════════════════════════════════════════════════════════════
class TestActionParams:
    def _ap(self, rag=None):
        return ActionPipeline(llm_large=fake_large, llm_small=fake_small, rag_builder=rag)

    # NOT: security_level RequestContext'te "balanced" default → asla eksik olmaz.
    # Eksik olabilecekler yalnız os ve role.
    @pytest.mark.parametrize("ctx_kw,expected_missing", [
        ({}, {"os", "role"}),                                    # ikisi de yok
        ({"os": "ubuntu_24_04"}, {"role"}),                      # role eksik
        ({"role": "sysadmin"}, {"os"}),                          # os eksik
    ])
    def test_missing_params_asks_user(self, ctx_kw, expected_missing):
        r = self._ap().handle(RequestContext(user_question="ssh hardening scripti yaz", **ctx_kw))
        assert r.success is False
        assert set(r.missing_params) == expected_missing
        assert r.user_prompt_message

    @pytest.mark.parametrize("q", [
        "ssh hardening scripti yaz",
        "ufw firewall kurallarını uygulayan script üret",
    ])
    def test_all_params_generates_script(self, q):
        ctx = RequestContext(user_question=q, os="ubuntu_24_04", role="sysadmin", security_level="balanced")
        r = self._ap().handle(ctx)
        assert r.success is True
        assert "```" in r.answer  # kod bloğu içeriyor

    def test_validation_runs_on_output(self):
        ctx = RequestContext(user_question="ssh hardening scripti yaz",
                             os="ubuntu_24_04", role="sysadmin", security_level="balanced")
        r = self._ap().handle(ctx)
        assert r.validation is not None  # OutputValidator çalıştı (düzeltme/uyarı kapısı)
