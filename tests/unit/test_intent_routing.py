"""
Intent yönlendirme sağlamlığı + prompt-leak temizleme testleri.
Branch: feature/intent-routing-robustness.

Kapsam:
- is_smalltalk (deterministik regex): TR selamlama/argo (naber, ne haber, slm, naptın...) True,
  güvenlik soruları False.
- detect(): greeting → smalltalk (pattern, conf 1.0); güvenlik → info/action; konu-dışı → out_of_scope.
- Düşük-güven emniyet ağı (C): güvenlik sinyali olmayan tanınmayan girdi güvenlik cevabına sızmaz.
- strip_grounding_directive: LLM çıktısına sızan 'ÖNEMLİ — KANITA DAYAN ...' talimatını temizler.
"""

from __future__ import annotations

import pytest

from llm.core.context import RequestContext
from llm.pipelines.layers.hybrid_intent_detector import HybridIntentDetector, is_smalltalk
from llm.prompts.simple_prompts import GROUNDING_DIRECTIVE, build_simple_prompt, build_medium_prompt

GREETINGS = [
    "naber", "Naber", "naber?", "n'aber", "ne haber", "nbr", "slm", "sa", "selam",
    "merhaba", "merhabalar", "nasılsın", "naptın", "napıyorsun", "napıyon",
    "nasıl gidiyor", "iyi misin", "günaydın", "iyi akşamlar", "hey",
]
FAREWELL = ["görüşürüz", "hoşça kal", "baybay", "kendine iyi bak"]
THANKS = ["teşekkürler", "sağ ol", "eyvallah"]
SMALLTALK_ALL = GREETINGS + FAREWELL + THANKS

SECURITY = [
    "ssh root login nasıl kapatılır", "ufw firewall yapılandır",
    "PermitRootLogin nedir", "parola politikası nasıl sıkılaştırılır",
    "cramfs modülünü devre dışı bırak", "ssh için ansible playbook yaz",
]
OUT_OF_SCOPE = ["hava durumu nasıl", "2+2 kaç eder", "film öner", "yemek tarifi ver"]

# Zorlu smalltalk varyantları (ekli/çok-kelimeli) — modül düzeyinde (parametrize için)
HARD_SMALLTALK = [
    "merhabalar", "baybay", "günaydınlar", "bb", "selam dostum", "naber kanka",
    "iyi geceler", "eyvallah görüşürüz", "selamün aleyküm", "merhaba arkadaşlar",
    "çok teşekkür ederim", "kendine iyi bak", "selamlar", "naptınız",
]
# Greeting KELİMESİ içeren ama GÜVENLİK sorusu olanlar → smalltalk OLMAMALI
GREETING_PREFIX_SECURITY = [
    "merhaba ssh nasıl sıkılaştırılır", "selam ufw firewall yapılandır",
    "iyi bir firewall kuralı yaz",
]


@pytest.fixture(scope="module")
def detector():
    # Pattern+lexicon+guard katmanlarını test ederiz; ML backend'i TF-IDF'e sabitle
    # (deterministik + AĞSIZ). Embedding router'ın kendi ağsız testi: test_embedding_router.py
    return HybridIntentDetector(use_ml=True, debug=False, use_embedding_router=False)


class TestIsSmalltalkDeterministic:
    @pytest.mark.parametrize("q", SMALLTALK_ALL)
    def test_smalltalk_true(self, q):
        assert is_smalltalk(q) is True, f"{q!r} smalltalk olmalı"

    @pytest.mark.parametrize("q", SECURITY + OUT_OF_SCOPE)
    def test_non_smalltalk_false(self, q):
        assert is_smalltalk(q) is False, f"{q!r} smalltalk OLMAMALI"

    def test_empty(self):
        assert is_smalltalk("") is False
        assert is_smalltalk("   ") is False


class TestGreetingRouting:
    @pytest.mark.parametrize("q", GREETINGS)
    def test_greeting_is_smalltalk_via_pattern(self, detector, q):
        # Pattern ML'den ÖNCE → conf 1.0 smalltalk (deterministik)
        r = detector.detect(q)
        assert r.type == "smalltalk", f"{q!r} → {r.type} (smalltalk bekleniyor)"
        assert r.confidence == 1.0 and r.method == "pattern"


class TestSecurityRouting:
    @pytest.mark.parametrize("q", SECURITY)
    def test_security_to_info_or_action(self, detector, q):
        r = detector.detect(q)
        assert r.type in ("info_request", "action_request"), f"{q!r} → {r.type}"


class TestOutOfScopeRouting:
    @pytest.mark.parametrize("q", OUT_OF_SCOPE)
    def test_off_topic_rejected(self, detector, q):
        r = detector.detect(q)
        assert r.type == "out_of_scope", f"{q!r} → {r.type}"


class TestRobustSmalltalk:
    """ML'siz deterministik smalltalk: ekli/çok-kelimeli selamlamalar + yanlış-pozitif yok."""

    @pytest.mark.parametrize("q", HARD_SMALLTALK)
    def test_hard_variants_are_smalltalk(self, detector, q):
        assert is_smalltalk(q) is True, f"{q!r} smalltalk olmalı"
        assert detector.detect(q).type == "smalltalk", f"{q!r} → {detector.detect(q).type}"

    @pytest.mark.parametrize("q", GREETING_PREFIX_SECURITY)
    def test_greeting_word_in_security_not_smalltalk(self, detector, q):
        assert is_smalltalk(q) is False, f"{q!r} smalltalk OLMAMALI (güvenlik sorusu)"
        assert detector.detect(q).type in ("info_request", "action_request"), f"{q!r}"


class TestGroundingDirectiveNotInUserPrompt:
    """KÖK FIX: direktif user prompt'una GÖMÜLMEZ (system mesajı olarak geçer) → echo yok."""

    def _ctx(self):
        return RequestContext(
            user_question="ssh root login nasıl kapatılır",
            os="ubuntu_24_04", role="sysadmin",
            retrieved_context="CIS 5.1.20 Ensure sshd PermitRootLogin is disabled ...",
        )

    def test_directive_text_exists_as_constant(self):
        assert "KANITA DAYAN" in GROUNDING_DIRECTIVE

    def test_simple_prompt_excludes_directive(self):
        # RAG bağlamı OLSA BİLE direktif user prompt'unda olmamalı (system'e taşındı)
        assert "KANITA DAYAN" not in build_simple_prompt(self._ctx())

    def test_medium_prompt_excludes_directive(self):
        assert "KANITA DAYAN" not in build_medium_prompt(self._ctx())
