# hybrid_intent_detector.py
"""
Hybrid Intent Detection: ML + Pattern-based

Strategy:
1. Try ML first (fast, accurate for most cases)
2. If ML confidence < threshold, use pattern-based fallback
3. Special handling for smalltalk (patterns are 100% accurate)
4. Special handling for out-of-scope (keyword matching)

Benefits:
- Best of both worlds: ML generalization + Pattern precision
- Handles edge cases better
- More robust to Turkish characters
- Faster for common patterns (greeting, farewell)
"""

from __future__ import annotations
from typing import Literal, Optional
from dataclasses import dataclass
import os
import re

# Import ML detector
# NOTE: the real implementation lives in llm/ml/intent_detector.py. The previous
# relative path (``..ml_intent_detector``) pointed at a non-existent module, so
# ML_AVAILABLE was always False and the hybrid detector silently degraded to
# pattern-only matching. Fixed to the correct absolute import.
try:
    from llm.ml.intent_detector import MLIntentDetector, MLIntent
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    MLIntentDetector = None
    MLIntent = None


IntentType = Literal[
    "smalltalk",        # Will be mapped from greeting/farewell/thanks/help
    "info_request",
    "action_request",
    "out_of_scope"
]


@dataclass
class HybridIntent:
    """Hybrid intent detection result"""
    type: IntentType
    subtype: Optional[str] = None  # For smalltalk: greeting, farewell, thanks, help
    confidence: float = 0.0
    method: str = "hybrid"  # ml / pattern / hybrid
    ml_probabilities: dict = None
    metadata: dict = None  # Additional info for compatibility

    def __post_init__(self):
        if self.ml_probabilities is None:
            self.ml_probabilities = {}
        if self.metadata is None:
            self.metadata = {}


class HybridIntentDetector:
    """
    Alan-içi niyet sınıflandırıcı: smalltalk vs info_request vs action_request.

    TEK TEMİZ KARAR AKIŞI (konsolide — eski 7-mekanizmalı whack-a-mole değil):
      1. Smalltalk kapısı (deterministik, $0, LLM-öncesi) → `_smalltalk_subtype`
      2. TF-IDF ML ile info-vs-action + TEK imperatif tiebreak + TEK güven eşiği
      3. ML yoksa/başarısızsa pattern-only fallback

    KAPSAM (out_of_scope) BURADA KARARLAŞTIRILMAZ. Alan-içi/dışı kararı tek otorite olan
    L1 LLM safety kategorisine aittir (secure_v2 "semantik kapsam kapısı": off_topic →
    out_of_scope). Bu detector yalnız ALAN-İÇİ niyeti seçer. (Eski keyword-tabanlı oos
    üretimi + düşük-güven oos emniyet ağı KALDIRILDI — aynı kararın 3 yerde verilmesi
    her yeni sorguda yeni kenar-durum/bug doğuruyordu.)

    Performans: smalltalk <1ms (pattern); info/action ~5-10ms (TF-IDF ML).
    """

    # Tek güven eşiği: ML bundan eminse info/action'ına güven, değilse güvenli default
    # (info_request). Eski 3-kademeli HIGH/MED/LOW ladder'ı (her kademe farklı override
    # dalına sapıyordu → whack-a-mole) tek eşiğe indirildi.
    ML_CONFIDENCE = 0.60

    # ═════════════════════════════════════════════
    # SMALLTALK PATTERNS (High precision)
    # ═════════════════════════════════════════════

    # Anchored (^...$) = TAM mesaj smalltalk olmalı → "hi/yo/sa/ty/thx" gibi çok-kısa
    # tek-kelimeleri burada GÜVENLE tutabiliriz (mesajın tamamı eşleşmeli). thanks ise
    # \b...\b (mesaj içinde geçebilir: "çok teşekkürler dostum").
    SMALLTALK_PATTERNS = {
        "greeting": [
            r'^\s*(merhaba(?:lar)?|selam(?:lar)?|selamün\s*aleyküm|aleyküm\s*selam|slm|sa|mrb|mrhb|hi+|hey+|hello+|helo|yo|hola|günaydın|tünaydın|iyi\s*(günler|akşamlar|geceler|sabahlar))\s*[!?.]*\s*$',
            r'^\s*(nasılsın(?:ız)?|how\s*(are|r)\s*(you|u|ya)|naber|n[\'’]?aber|nbr|ne\s*haber|napt[ıi]n|nap[ıi]yorsun|nap[ıi]yon|nasıl\s*gidiyor|iyi\s*misin|keyifler\s*nasıl)\s*[?!.]*\s*$',
            r'^\s*(hey\s*there|hi\s*there|hello\s*there|howdy|hoşgeldin(?:iz)?|hoş\s*geldin(?:iz)?|good\s*(morning|evening|afternoon|day)|what[\'’]?s?\s*up|wassup|sup)\s*[!?.]*\s*$',
        ],
        "farewell": [
            r'^\s*(görüşürüz|görüşmek\s*(üzere|dileğiyle)|hoşça\s*kal(?:ın)?|hoşçakal(?:ın)?|bay\s*bay|baybay|bb|bye(?:\s*bye)?|byebye|good\s*bye|goodbye|güle\s*güle|elveda|allaha?\s*ısmarladık|selametle)\s*[!.?]*\s*$',
            r'^\s*(kendine\s*(iyi\s*)?bak|kendine\s*dikkat\s*et|take\s*care|see\s*(you|ya|u)(\s*(soon|later))?|catch\s*you\s*later|talk\s*later|later|cya|ttyl|peace(\s*out)?|farewell)\s*[!.?]*\s*$',
        ],
        "thanks": [
            r'\b(teşekkür(?:ler|\s*eder(?:im|iz))?|sağ\s*ol(?:un)?|sağol(?:un)?|eyvallah|minnettar(?:ım)?|el(?:in|lerin)e\s*sağlık|emeğine\s*sağlık|çok\s*sağol)\b',
            r'\b(thanks(?:\s*a\s*lot|\s*so\s*much)?|thank\s*(you|u)(\s*(so|very)\s*much)?|thx|tysm|ty|much\s*appreciated|appreciate\s*(it|that)|cheers)\b',
        ],
        "help": [
            r'^\s*(yardım|help|destek|support|assist)\s*[?!]?\s*$',
            r'^\s*(sana\s*bir\s*sorum\s*var|can\s*you\s*help|bana\s*yardım\s*eder\s*misin)\s*[?]?\s*$',
        ],
    }

    # Lexicon (kök kelimeler) — anchored pattern'i KAÇIRAN ekli/çok-kelimeli selamlamaları
    # yakalamak için. Yalnız KISA mesajda (<=5 kelime) ve GÜVENLİK sinyali YOKKEN uygulanır
    # ("merhaba ssh'i sıkılaştır" → güvenlik kelimesi var → smalltalk DEĞİL). TF-IDF ML bunlarda
    # zayıf olduğundan selamlama/veda/teşekkür burada deterministik yakalanır.
    # Kısa-mesaj (<=4 kelime, güvenlik/oos sinyali yok) substring sözlüğü. Stem'ler
    # AYIRT EDİCİ (>=3 char) seçilir; "hi/yo/ty/sa" gibi ÇOK kısa/çift-anlamlılar burada
    # DEĞİL (yanlış eşleşme riski) — onlar anchored PATTERN'de (tam mesaj). TR + EN kapsamlı.
    SMALLTALK_LEXICON = {
        "greeting": [
            # TR
            "merhaba", "merhabalar", "selam", "selamlar", "selamün", "naber", "ne haber",
            "napt", "napıyor", "napıyon", "nbr", "günaydın", "tünaydın",
            "iyi günler", "iyi akşamlar", "iyi geceler", "iyi sabahlar", "nasılsın",
            "nasılsınız", "nasıl gidiyor", "iyi misin", "keyifler nasıl",
            "hoş geldin", "hoşgeldin", "hoş geldiniz", "selamün aleyküm", "aleyküm selam",
            "slm", "mrb", "mrhb", "mrhaba",   # kısaltmalar
            # EN
            "hello", "good morning", "good evening", "good afternoon", "good day",
            "hey there", "hi there", "hello there", "howdy", "greetings",
            "what's up", "whats up", "wassup",
        ],
        "farewell": [
            # TR
            "görüşürüz", "görüşmek üzere", "görüşmek dileğiyle", "hoşça kal", "hoşçakal",
            "baybay", "bay bay", "kendine iyi bak", "kendine dikkat", "güle güle", "elveda",
            "allahaısmarladık", "selametle", "grşrz", "bb",
            # EN  ("bye" → bye/bye bye/byebye/goodbye hepsini yakalar)
            "bye", "good bye", "goodbye", "see you", "see ya", "take care",
            "catch you later", "see you later", "talk later", "ttyl", "cya", "farewell",
        ],
        "thanks": [
            # TR
            "teşekkür", "teşekkur", "tesekkur", "sağ ol", "sağol", "sağ olun", "sağolun",
            "minnettar", "eline sağlık", "ellerine sağlık", "emeğine sağlık", "eyvallah",
            "makbule geçti", "çok sağol", "çok teşekkür",
            "tşk", "tsk", "tşkr", "tşkler", "teşekkurler", "sagol", "sgl", "eyw", "eyv",  # kısaltmalar
            # EN
            "thanks", "thank you", "thank u", "thx", "tysm", "much appreciated",
            "appreciate it", "appreciate that", "cheers",
        ],
    }

    # ═════════════════════════════════════════════
    # OUT-OF-SCOPE KEYWORDS
    # ═════════════════════════════════════════════

    OUT_OF_SCOPE_KEYWORDS = [
        # Weather
        "hava durumu", "hava nasıl", "weather", "bugün hava", "yarın hava",

        # Math/calculation
        "hesapla", "calculate", "matematik", "math", "kaç yapar",

        # General knowledge
        "tarih", "history", "coğrafya", "geography",

        # Personal
        "sevgilim", "girlfriend", "boyfriend", "ilişki", "relationship",

        # Entertainment
        "film", "movie", "müzik", "music", "oyun", "game",

        # Food/Travel/Sports
        "yemek", "recipe", "tatil", "vacation", "futbol", "football",
    ]

    # ═════════════════════════════════════════════
    # SECURITY KEYWORDS (güvenlik sinyali — düşük-güven emniyet ağında kullanılır)
    # ═════════════════════════════════════════════

    # NOT: Bu liste yalnızca HIZLI bir buluşsaldır (ML'siz, ekstra LLM call'sız). Eksik
    # terimler (örn. "rdp") burada AÇIK DEĞİL — kapsam kararının TEK dayanağı bu değildir.
    # Asıl emniyet/domain sinyali Layer-1 LLM safety kategorisidir (safe_defensive/
    # safe_educational); secure_v2 düşük-güvenli out_of_scope'u o semantik sinyalle ezer.
    # Bu sayede listeye sonsuza dek keyword eklemek (whack-a-mole) gerekmez.
    SECURITY_KEYWORDS = [
        "güvenlik", "security", "hardening", "sıkılaştır", "firewall", "ufw", "ssh",
        "sshd", "iptables", "selinux", "apparmor", "audit", "auditd", "parola", "password",
        "vulnerability", "zafiyet", "cis", "nist", "iso", "zero trust", "permission",
        "izin", "kernel", "modül", "module", "port", "tls", "ssl", "cipher", "sudo",
        "root", "login", "pam", "fail2ban", "umask", "benchmark", "policy", "politika",
    ]

    # ═════════════════════════════════════════════
    # ACTION IMPERATIVE PATTERNS
    # ═════════════════════════════════════════════

    ACTION_IMPERATIVE_PATTERNS = [
        r'\b(oluştur|yarat|üret|hazırla|yap|yaz)\b',  # Turkish imperatives
        r'için\s+(script|config|hardening|güvenlik)',  # "için X" patterns
        r'(script|config|betik)\s+(oluştur|yaz|hazırla)',
        r'\b(create|write|generate|make|build)\s+(script|config)',
    ]

    # ═════════════════════════════════════════════
    # SAF BİLGİ-SORU KELİMELERİ (action DEĞİL, açıklama ister)
    # ═════════════════════════════════════════════
    # "nerede/nedir/hangi" gibi EVRENSEL soru kelimeleri → script TALEBİ değildir. imperative
    # YOKKEN, ML "konfigürasyon dosyası nerede" gibi bir soruyu yanlışlıkla action sanarsa
    # bunu bilgi'ye çeker. (Domain keyword listesi DEĞİL → whack-a-mole değil; dilbilgisel.)
    # 'nasıl' BİLEREK YOK — "nasıl yaparım" gerçek bir script talebi olabilir (action kalsın).
    INFO_QUESTION_PATTERNS = [
        r'\b(nerede|nedir|ne\s*demek|hangi|kaç|ne\s*zaman|kim|neden|niçin|niye)\b',
        r'\bne\s*işe\s*yar',  # "ne işe yarar/yarıyor" — ek alabilir → trailing \b YOK
        r'\b(where\s+(is|are|can|do)|what\s+(is|are|does)|which|when\s+(is|do|to)|how\s+many|who)\b',
    ]

    def __init__(
        self,
        ml_detector: Optional[MLIntentDetector] = None,
        use_ml: bool = True,
        debug: bool = False,
        use_embedding_router: Optional[bool] = None,
    ):
        """
        Initialize hybrid intent detector

        Args:
            ml_detector: Pre-trained ML detector (optional)
            use_ml: Enable ML classification (default True)
            debug: Enable debug logging
        """
        self.debug = debug
        self.use_ml = use_ml and ML_AVAILABLE
        self.ml_detector = ml_detector
        self.classifier_backend = "tfidf"

        # Sınıflandırıcı backend: param > env (INTENT_ROUTER=embedding|tfidf) > varsayılan TF-IDF.
        # KANIT (scripts/evaluate_intent_router.py, 44 etiketli örnek, gerçek Novita):
        #   TF-IDF %93.2 / ~0.5ms   vs   embedding %75.0 / ~600-1300ms (p95 ~6s).
        # Embedding kosinüsü KONUYU yakalıyor ama info↔action KİP farkını ("nedir" vs "kapat")
        # yakalayamıyor + her sorguda canlı embed çağrısı = gecikme. Bu yüzden varsayılan TF-IDF.
        # Embedding router opt-in deneysel kalır (INTENT_ROUTER=embedding).
        if use_embedding_router is None:
            use_embedding_router = os.environ.get("INTENT_ROUTER", "tfidf").lower() == "embedding"

        if self.use_ml and self.ml_detector is None and use_embedding_router:
            try:
                from llm.ml.embedding_router import EmbeddingIntentRouter
                self.ml_detector = EmbeddingIntentRouter(debug=debug)
                self.classifier_backend = "embedding"
                if self.debug:
                    print("[HybridIntentDetector] Embedding router aktif (semantic similarity)")
            except Exception as e:
                if self.debug:
                    print(f"[HybridIntentDetector] Embedding router kurulamadı, TF-IDF'e düşülüyor: {e}")

        # Embedding router yoksa eski TF-IDF ML'i yükle (fallback / INTENT_ROUTER=tfidf)
        if self.use_ml and self.ml_detector is None:
            try:
                self.ml_detector = MLIntentDetector(debug=False)
                self.ml_detector.load_models()
                self.classifier_backend = "tfidf"
                if self.debug:
                    print("[HybridIntentDetector] TF-IDF ML models loaded successfully")
            except Exception as e:
                print(f"[HybridIntentDetector] Warning: Could not load ML models: {e}")
                print("[HybridIntentDetector] Falling back to pattern-only mode")
                self.use_ml = False
                self.classifier_backend = "none"

        self.stats = {
            "total": 0,
            "ml_used": 0,
            "pattern_used": 0,
            "hybrid_used": 0,
        }

    def detect(self, question: str) -> HybridIntent:
        """Alan-içi niyeti tespit et: smalltalk / info_request / action_request.

        KAPSAM (out_of_scope) BURADA verilmez — L1 LLM safety kategorisi tek otoritedir
        (secure_v2 kapsam kapısı). Detaylar için sınıf docstring'ine bak.
        """
        self.stats["total"] += 1

        if not question or not question.strip():
            return HybridIntent(type="smalltalk", subtype="other",
                                confidence=1.0, method="pattern")

        q_lower = question.strip().lower()

        # ── Adım 1: Smalltalk (deterministik, $0, LLM-öncesi) ──
        st = self._smalltalk_subtype(q_lower)
        if st:
            self.stats["pattern_used"] += 1
            if self.debug:
                print(f"[HybridIntent] Smalltalk: {st}")
            return HybridIntent(type="smalltalk", subtype=st, confidence=1.0, method="pattern")

        # İmperatif kip ("yaz/üret/oluştur...") action'ın en güçlü sinyali — bir kez hesapla.
        imperative = self._check_imperative_patterns(q_lower)

        # ── Adım 2: TF-IDF ML ile info-vs-action (BİRİNCİL) ──
        if self.use_ml and self.ml_detector:
            try:
                ml_result: MLIntent = self.ml_detector.predict(question)
                if self.debug:
                    print(f"[HybridIntent] ML: {ml_result.type} (conf {ml_result.confidence:.3f})")

                intent_type = self._map_ml_intent(ml_result.type)
                subtype = self._get_subtype(ml_result.type)

                # TEK, SIRALI override basamağı (eski dağınık guard/ladder/emniyet-ağı yerine):
                if imperative:
                    # İmperatif kip → action (ML "info/smalltalk/oos" dese de).
                    intent_type, subtype = "action_request", None
                elif intent_type in ("out_of_scope", "smalltalk"):
                    # Kapsam gate'in işi; gerçek smalltalk Adım-1'de yakalanırdı. ML buraya
                    # "merhaba ssh..." gibi token'a aldanıp gelmiş olabilir → alan-içi default.
                    intent_type, subtype = "info_request", None
                elif intent_type == "action_request" and self._is_info_question(q_lower):
                    # SAF BİLGİ sorusu ("konfigürasyon dosyası NEREDE", "X NEDİR") action
                    # sanıldı → bilgi'ye çek. imperative YOK (varsa yukarıda action olurdu) →
                    # kullanıcı script değil AÇIKLAMA istiyor. (Canlı bug: "...nerede?" → 3C.)
                    intent_type, subtype = "info_request", None
                # NOT: ML'in info/action TİPİNE güveniriz (düşük güvende bile) — "ssh root
                # login'i kapat" gibi imperatif-pattern'e UYMAYAN eylemler ML'de düşük-güvenli
                # action çıkar; bunu info'ya çevirmek yanlıştı. Güven yalnız method etiketinde.

                self.stats["ml_used"] += 1
                method = "ml" if (imperative or ml_result.confidence >= self.ML_CONFIDENCE) else "ml_lowconf"
                return HybridIntent(
                    type=intent_type, subtype=subtype,
                    confidence=ml_result.confidence, method=method,
                    ml_probabilities=ml_result.probabilities,
                )
            except Exception as e:
                if self.debug:
                    print(f"[HybridIntent] ML error: {e}, pattern fallback")

        # ── Adım 3: Pattern-only fallback (ML yok/başarısız) ──
        self.stats["pattern_used"] += 1
        return self._pattern_fallback(q_lower) or HybridIntent(
            type="info_request", confidence=0.5, method="default")

    def _smalltalk_subtype(self, q_lower: str) -> Optional[str]:
        """Smalltalk alt-türü (greeting/farewell/thanks/help) ya da None — ML'siz, deterministik.
        1) Anchored pattern (tam eşleşme). 2) Kısa mesaj (<=5 kelime) + lexicon + güvenlik-yok."""
        for subtype, patterns in self.SMALLTALK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, q_lower, re.IGNORECASE):
                    return subtype
        words = q_lower.split()
        if (
            len(words) <= 4
            and "?" not in q_lower
            and not any(kw in q_lower for kw in self.SECURITY_KEYWORDS)
            and not any(kw in q_lower for kw in self.OUT_OF_SCOPE_KEYWORDS)
        ):
            for subtype, stems in self.SMALLTALK_LEXICON.items():
                if any(stem in q_lower for stem in stems):
                    return subtype
        return None

    def _map_ml_intent(self, ml_intent: str) -> IntentType:
        """Map ML intent to our IntentType"""
        mapping = {
            "greeting": "smalltalk",
            "farewell": "smalltalk",
            "thanks": "smalltalk",
            "help": "smalltalk",
            "info_request": "info_request",
            "action_request": "action_request",
            "out_of_scope": "out_of_scope",
        }
        return mapping.get(ml_intent, "info_request")  # type: ignore

    def _get_subtype(self, ml_intent: str) -> Optional[str]:
        """Get subtype for smalltalk intents"""
        if ml_intent in ["greeting", "farewell", "thanks", "help"]:
            return ml_intent
        return None

    def _check_imperative_patterns(self, text: str) -> bool:
        """Check for Turkish/English imperative patterns"""
        for pattern in self.ACTION_IMPERATIVE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _is_info_question(self, text: str) -> bool:
        """Saf bilgi-soru kelimesi (nerede/nedir/hangi/where/what...) içeriyor mu?
        → action değil AÇIKLAMA isteyen soru. imperative override'ının simetriği."""
        for pattern in self.INFO_QUESTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _pattern_fallback(self, text: str) -> Optional[HybridIntent]:
        """Pattern-based fallback when ML fails or unavailable"""
        # Check imperative patterns for action
        if self._check_imperative_patterns(text):
            return HybridIntent(
                type="action_request",
                confidence=0.85,
                method="pattern"
            )

        # Check for question words (info request indicators)
        info_patterns = [
            r'\b(nedir|ne demek|nasıl|what|how|explain)\b',
            r'\?',  # Question mark
        ]

        for pattern in info_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return HybridIntent(
                    type="info_request",
                    confidence=0.80,
                    method="pattern"
                )

        return None

    def get_stats(self) -> dict:
        """Get detection statistics"""
        if self.stats["total"] == 0:
            return self.stats

        return {
            **self.stats,
            "ml_rate": self.stats["ml_used"] / self.stats["total"],
            "pattern_rate": self.stats["pattern_used"] / self.stats["total"],
            "hybrid_rate": self.stats["hybrid_used"] / self.stats["total"],
        }


def is_smalltalk(text: str) -> bool:
    """
    Hızlı/deterministik: metin bir smalltalk pattern'ine (selam/naber/teşekkür/veda/yardım)
    uyuyor mu? ML YOK — yalnız regex. QueryRewriter'ın greeting'i güvenlik sorusuna yeniden
    yazmasını engellemek için pipeline ÖNCESİNDE kullanılır (multi-turn fix).
    """
    ql = (text or "").strip().lower()
    if not ql:
        return False
    for patterns in HybridIntentDetector.SMALLTALK_PATTERNS.values():
        for p in patterns:
            if re.search(p, ql, re.IGNORECASE):
                return True
    # Kısa mesaj (<=4 kelime) + lexicon + '?' yok + güvenlik/oos sinyali yok → smalltalk
    # (ekli/çok-kelimeli selamlamalar; "merhaba hava durumu nasıl" gibi oos önekini DIŞLAR)
    words = ql.split()
    if (
        len(words) <= 4
        and "?" not in ql
        and not any(kw in ql for kw in HybridIntentDetector.SECURITY_KEYWORDS)
        and not any(kw in ql for kw in HybridIntentDetector.OUT_OF_SCOPE_KEYWORDS)
    ):
        for stems in HybridIntentDetector.SMALLTALK_LEXICON.values():
            if any(stem in ql for stem in stems):
                return True
    return False


# Convenience function
def detect_intent(question: str, use_ml: bool = True, debug: bool = False) -> HybridIntent:
    """Quick hybrid intent detection"""
    detector = HybridIntentDetector(use_ml=use_ml, debug=debug)
    return detector.detect(question)
