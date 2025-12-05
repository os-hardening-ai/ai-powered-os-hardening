# utils/question_classifier.py
"""
Soru Karmaşıklık Sınıflandırıcı

Kullanıcı sorularını 3 seviyeye ayırır:
1. SIMPLE: Basit bilgi soruları (düşük model + minimal format)
2. MEDIUM: Orta karmaşıklık (gpt-4o-mini + orta format)
3. COMPLEX: Karmaşık güvenlik analizi (gpt-4o + CoT + tam format)
"""

from __future__ import annotations
import re
from typing import Literal

QuestionComplexity = Literal["simple", "medium", "complex"]


class QuestionClassifier:
    """
    Soru karmaşıklığını belirler - hızlı ve maliyet-etkin.
    """

    # Basit bilgi soruları için keyword'ler
    SIMPLE_PATTERNS = [
        # Tek komut/kavram soruları
        r'\b(nedir|ne demek|nasıl yapılır)\b',
        r'\b(command|komut) (nedir|ne)\b',
        r'\b(explain|açıkla|anlat)\s+\w+\s*$',  # Tek kelime açıklama

        # Smalltalk
        r'\b(merhaba|selam|hey|hi|hello|günaydın)\b',
        r'\b(teşekkür|sağol|thanks)\b',

        # Çok kısa sorular (5 kelimeden az)
        # İşaretlenir ama diğer faktörlerle birlikte değerlendirilir
    ]

    # Karmaşık güvenlik analizi gerektiren keyword'ler
    COMPLEX_PATTERNS = [
        # Çoklu adım/sistem
        r'\b(full.*hardening|hardening.*script)\b',
        r'\b(zero trust|zt architecture|zt maturity)\b',

        # Kapsamlı audit/compliance
        r'\b(compliance|audit|full.*check|tam.*kontrol)\b',
        r'\b(incident.*response|saldırı.*analiz|analiz.*yap)\b',

        # Script/otomasyon talebi
        r'\b(script.*yaz|automation|otomasyon)\b',
        r'\b(monitoring.*kur|alerting.*kur|full.*setup)\b',
    ]

    # Orta seviye göstergeleri
    MEDIUM_PATTERNS = [
        # "nasıl" soruları genelde medium
        r'\b(nasıl.*güvenli|nasıl.*yapılır|how.*to)\b',

        # Spesifik servis yapılandırma
        r'\b(ssh.*config|ssh.*yapılandır|firewall.*rule|rdp.*hardening)\b',
        r'\b(log.*rotation|backup.*strategy)\b',

        # Tek servis güvenlik
        r'\b(nginx.*güvenlik|apache.*harden|güvenlik.*ayar)\b',
    ]

    def classify(self, question: str) -> QuestionComplexity:
        """
        Soruyu sınıflandır.

        Args:
            question: Kullanıcı sorusu

        Returns:
            "simple" | "medium" | "complex"
        """
        q_lower = question.lower()
        word_count = len(question.split())

        # ─── SIMPLE: Basit bilgi soruları ───
        # 1. Çok kısa sorular (3 kelime veya daha az)
        if word_count <= 3:
            return "simple"

        # 2. Pattern matching
        for pattern in self.SIMPLE_PATTERNS:
            if re.search(pattern, q_lower, re.IGNORECASE):
                return "simple"

        # ─── COMPLEX: Karmaşık analiz gerektiren ───
        for pattern in self.COMPLEX_PATTERNS:
            if re.search(pattern, q_lower, re.IGNORECASE):
                return "complex"

        # ─── MEDIUM: Spesifik ama karmaşık değil ───
        for pattern in self.MEDIUM_PATTERNS:
            if re.search(pattern, q_lower, re.IGNORECASE):
                return "medium"

        # ─── DEFAULT: Kelime sayısına göre ───
        # Kısa sorular (4-10 kelime) → simple
        if word_count <= 10:
            return "simple"

        # Orta uzunluk (11-20 kelime) → medium
        elif word_count <= 20:
            return "medium"

        # Uzun sorular (20+) → genellikle complex
        else:
            return "complex"


# Global instance
_classifier = QuestionClassifier()


def classify_question(question: str) -> QuestionComplexity:
    """
    Soru karmaşıklığını sınıflandır (global classifier kullanır).

    Args:
        question: Kullanıcı sorusu

    Returns:
        "simple" | "medium" | "complex"
    """
    return _classifier.classify(question)


# ─────────────────────────────────────────────
# Test Examples
# ─────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        # SIMPLE
        ("SELinux nedir?", "simple"),
        ("merhaba", "simple"),
        ("ssh port değiştir", "simple"),
        ("firewall nedir", "simple"),

        # MEDIUM
        ("SSH yapılandırmasını nasıl güvenli hale getiririm?", "medium"),
        ("nginx için güvenlik ayarları nelerdir", "medium"),
        ("log rotation nasıl yapılır ubuntu'da", "medium"),

        # COMPLEX
        ("Ubuntu 22.04 için full hardening script yaz", "complex"),
        ("Zero Trust mimarisini nasıl uygularım", "complex"),
        ("Sistemde saldırı analizi yap ve raporla", "complex"),
        ("Monitoring ve alerting sistemi kur", "complex"),
    ]

    print("="*70)
    print("QUESTION COMPLEXITY CLASSIFIER - TEST")
    print("="*70)

    classifier = QuestionClassifier()

    correct = 0
    for question, expected in test_cases:
        result = classifier.classify(question)
        status = "OK" if result == expected else "FAIL"

        if result == expected:
            correct += 1

        print(f"[{status:4s}] [{result.upper():8s}] {question}")
        if result != expected:
            print(f"          Expected: {expected.upper()}")

    print("="*70)
    print(f"Accuracy: {correct}/{len(test_cases)} ({100*correct//len(test_cases)}%)")
    print("="*70)
