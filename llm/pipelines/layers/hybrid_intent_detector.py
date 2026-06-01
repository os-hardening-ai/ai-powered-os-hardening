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
    Hybrid intent detector combining ML and pattern-based approaches

    Decision flow:
    1. Check smalltalk patterns first (100% accuracy, <1ms)
    2. Check out-of-scope keywords (fast filtering)
    3. Use ML for info vs action classification
    4. If ML confidence < 0.6, use pattern fallback

    Performance:
    - Smalltalk: <1ms (pattern) or ~5ms (ML fallback)
    - Info/Action: ~5-10ms (ML primary)
    - Out-of-scope: <1ms (keyword) or ~5ms (ML fallback)
    """

    # Confidence thresholds
    ML_HIGH_CONFIDENCE = 0.75  # Use ML result directly
    ML_MED_CONFIDENCE = 0.60   # Use ML but with caution
    ML_LOW_CONFIDENCE = 0.60   # Fallback to patterns

    # ═════════════════════════════════════════════
    # SMALLTALK PATTERNS (High precision)
    # ═════════════════════════════════════════════

    SMALLTALK_PATTERNS = {
        "greeting": [
            r'^\s*(merhaba(?:lar)?|selam(?:lar)?|slm|sa|hi|hello|hey|günaydın|iyi\s*günler|iyi\s*akşamlar)\s*[!?.]?\s*$',
            r'^\s*(nasılsın|nasılsınız|how\s*are\s*you|naber|n[\'’]?aber|nbr|ne\s*haber|naptın|napıyorsun|napıyon|nasıl\s*gidiyor|iyi\s*misin)\s*[?!.]*\s*$',
            r'^\s*(hey\s*there|hi\s*there|hoşgeldin|hoş\s*geldin)\s*[!]?\s*$',
        ],
        "farewell": [
            r'^\s*(görüşürüz|hoşça\s*kal|hoşçakal|bay\s*bay|baybay|bb|bye|güle\s*güle|elveda)\s*[!.]?\s*$',
            r'^\s*(kendine\s*iyi\s*bak|take\s*care|see\s*you)\s*[!.]?\s*$',
        ],
        "thanks": [
            r'\b(teşekkür|teşekkürler|sağ\s*ol|sağol|eyvallah)\b',
            r'\b(thanks|thank\s*you|thx|ty)\b',
        ],
        "help": [
            r'^\s*(yardım|help|destek|support|assist)\s*[?!]?\s*$',
            r'^\s*(sana\s*bir\s*sorum\s*var|can\s*you\s*help)\s*[?]?\s*$',
        ],
    }

    # Lexicon (kök kelimeler) — anchored pattern'i KAÇIRAN ekli/çok-kelimeli selamlamaları
    # yakalamak için. Yalnız KISA mesajda (<=5 kelime) ve GÜVENLİK sinyali YOKKEN uygulanır
    # ("merhaba ssh'i sıkılaştır" → güvenlik kelimesi var → smalltalk DEĞİL). TF-IDF ML bunlarda
    # zayıf olduğundan selamlama/veda/teşekkür burada deterministik yakalanır.
    SMALLTALK_LEXICON = {
        "greeting": [
            "merhaba", "selam", "naber", "ne haber", "napt", "napıyor", "nbr", "günaydın",
            "iyi günler", "iyi akşamlar", "iyi geceler", "nasılsın", "nasıl gidiyor",
            "hoş geldin", "hoşgeldin", "selamün", "iyi misin", "iyi sabahlar",
        ],
        "farewell": [
            "görüşürüz", "hoşça kal", "hoşçakal", "baybay", "bay bay", "kendine iyi bak",
            "güle güle", "elveda", "görüşmek üzere", "allahaısmarladık", "selametle",
        ],
        "thanks": [
            "teşekkür", "sağ ol", "sağol", "minnettar", "eline sağlık", "ellerine sağlık",
            "eyvallah", "makbule geçti", "emeğine sağlık",
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

    def __init__(
        self,
        ml_detector: Optional[MLIntentDetector] = None,
        use_ml: bool = True,
        debug: bool = False
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

        # Try to load ML models if not provided
        if self.use_ml and self.ml_detector is None:
            try:
                self.ml_detector = MLIntentDetector(debug=False)
                self.ml_detector.load_models()
                if self.debug:
                    print("[HybridIntentDetector] ML models loaded successfully")
            except Exception as e:
                print(f"[HybridIntentDetector] Warning: Could not load ML models: {e}")
                print("[HybridIntentDetector] Falling back to pattern-only mode")
                self.use_ml = False

        self.stats = {
            "total": 0,
            "ml_used": 0,
            "pattern_used": 0,
            "hybrid_used": 0,
        }

    def detect(self, question: str) -> HybridIntent:
        """
        Detect intent using hybrid approach

        Args:
            question: User input

        Returns:
            HybridIntent with detection result
        """
        self.stats["total"] += 1

        if not question or not question.strip():
            return HybridIntent(
                type="smalltalk",
                subtype="other",
                confidence=1.0,
                method="pattern"
            )

        q_stripped = question.strip()
        q_lower = q_stripped.lower()

        # ─────────────────────────────────────────
        # Step 1: Smalltalk (pattern + lexicon, ML'siz / deterministik / hızlı)
        # ─────────────────────────────────────────
        st = self._smalltalk_subtype(q_lower)
        if st:
            self.stats["pattern_used"] += 1
            if self.debug:
                print(f"[HybridIntent] Smalltalk: {st}")
            return HybridIntent(type="smalltalk", subtype=st, confidence=1.0, method="pattern")

        # ─────────────────────────────────────────
        # Step 2: Check out-of-scope keywords (FAST)
        # ─────────────────────────────────────────
        out_of_scope_matches = [kw for kw in self.OUT_OF_SCOPE_KEYWORDS if kw in q_lower]

        if out_of_scope_matches:
            # Check if security keywords also present
            has_security = any(kw in q_lower for kw in self.SECURITY_KEYWORDS)

            if not has_security:
                self.stats["pattern_used"] += 1

                if self.debug:
                    print(f"[HybridIntent] Out-of-scope keywords: {out_of_scope_matches}")

                return HybridIntent(
                    type="out_of_scope",
                    confidence=0.95,
                    method="pattern"
                )

        # ─────────────────────────────────────────
        # Step 3: Use ML for info vs action (PRIMARY)
        # ─────────────────────────────────────────
        if self.use_ml and self.ml_detector:
            try:
                ml_result: MLIntent = self.ml_detector.predict(question)

                if self.debug:
                    print(f"[HybridIntent] ML result: {ml_result.type} (conf: {ml_result.confidence:.3f})")

                # Map ML intents to our intent types
                intent_type = self._map_ml_intent(ml_result.type)
                subtype = self._get_subtype(ml_result.type)

                # GUARD: ML "smalltalk" dese bile sorguda GÜVENLİK sinyali varsa bu yanlıştır.
                # (Gerçek smalltalk Step-1 pattern/lexicon'da zaten yakalanırdı; buraya geldiyse
                # ve güvenlik kelimesi varsa TF-IDF "merhaba/selam" token'ına aldanmış demektir →
                # "merhaba ssh nasıl sıkılaştırılır" greeting DEĞİL.) imperative varsa action, yoksa info.
                if intent_type == "smalltalk" and any(kw in q_lower for kw in self.SECURITY_KEYWORDS):
                    if self.debug:
                        print("[HybridIntent] ML smalltalk + güvenlik sinyali → override (info/action)")
                    intent_type = "action_request" if self._check_imperative_patterns(q_lower) else "info_request"
                    subtype = None

                # High confidence - use ML directly
                if ml_result.confidence >= self.ML_HIGH_CONFIDENCE:
                    self.stats["ml_used"] += 1

                    return HybridIntent(
                        type=intent_type,
                        subtype=subtype,
                        confidence=ml_result.confidence,
                        method="ml",
                        ml_probabilities=ml_result.probabilities
                    )

                # Medium confidence - use ML but check imperative patterns
                elif ml_result.confidence >= self.ML_MED_CONFIDENCE:
                    # Check imperative patterns for action requests
                    imperative_match = self._check_imperative_patterns(q_lower)

                    if imperative_match and intent_type != "action_request":
                        # Override ML if imperative pattern found
                        self.stats["hybrid_used"] += 1

                        if self.debug:
                            print(f"[HybridIntent] Overriding ML with pattern (imperative found)")

                        return HybridIntent(
                            type="action_request",
                            confidence=0.90,
                            method="hybrid",
                            ml_probabilities=ml_result.probabilities
                        )

                    # Use ML result
                    self.stats["ml_used"] += 1

                    return HybridIntent(
                        type=intent_type,
                        subtype=subtype,
                        confidence=ml_result.confidence,
                        method="ml",
                        ml_probabilities=ml_result.probabilities
                    )

                # Low confidence - use pattern fallback
                else:
                    if self.debug:
                        print(f"[HybridIntent] Low ML confidence, using pattern fallback")

                    pattern_result = self._pattern_fallback(q_lower)

                    if pattern_result:
                        self.stats["hybrid_used"] += 1
                        return pattern_result

                    # Emniyet ağı (C): ML çok kararsız VE sorguda güvenlik sinyali yoksa,
                    # zayıf info/action tahminine GÜVENME → kibar red. ("ne haber" gibi
                    # tanınmayan chitchat'in güvenlik cevabına sızmasını engeller.)
                    has_security = any(kw in q_lower for kw in self.SECURITY_KEYWORDS)
                    if intent_type in ("info_request", "action_request") and not has_security:
                        if self.debug:
                            print("[HybridIntent] Düşük güven + güvenlik sinyali yok → out_of_scope (emniyet)")
                        self.stats["ml_used"] += 1
                        return HybridIntent(
                            type="out_of_scope",
                            confidence=ml_result.confidence,
                            method="lowconf_safety",
                            ml_probabilities=ml_result.probabilities,
                        )

                    # Last resort: use ML result anyway but mark as low confidence
                    self.stats["ml_used"] += 1

                    return HybridIntent(
                        type=intent_type,
                        subtype=subtype,
                        confidence=ml_result.confidence,
                        method="ml_lowconf",
                        ml_probabilities=ml_result.probabilities
                    )

            except Exception as e:
                if self.debug:
                    print(f"[HybridIntent] ML error: {e}, falling back to patterns")

        # ─────────────────────────────────────────
        # Step 4: Pattern-only fallback (NO ML)
        # ─────────────────────────────────────────
        self.stats["pattern_used"] += 1

        pattern_result = self._pattern_fallback(q_lower)
        if pattern_result:
            return pattern_result

        # Default: info_request (safe)
        return HybridIntent(
            type="info_request",
            confidence=0.5,
            method="default"
        )

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
