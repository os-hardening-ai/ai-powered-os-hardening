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

        # Türkçe hardening fiilleri
        r'\b(s[ıi]k[ıi]laşt[ıi]r|güçlendir|harden|koru[mn]|yapılandır|configure|secure)\b',

        # Güvenlik araçları / servisler
        r'\b(ssh|rdp|firewall|sudo|ufw|selinux|apparmor|auditd|sysctl)\b',

        # Spesifik servis yapılandırma
        r'\b(ssh.*config|ssh.*yapılandır|firewall.*rule|rdp.*hardening)\b',
        r'\b(log.*rotation|backup.*strategy)\b',

        # Tek servis güvenlik
        r'\b(nginx.*güvenlik|apache.*harden|güvenlik.*ayar)\b',
    ]

    # KISA olsa bile RAG'a gitmesi gereken hardening AKSIYON / how-to sinyalleri.
    # YALIN araç adı (ufw/ssh/rdp) BURADA YOK — "ufw ne", "ssh nedir" gibi TANIM soruları
    # simple kalsın (LLM bilir, RAG'a gerek yok). Yalnız bir EYLEM/prosedür sinyali varsa
    # ("nasıl sıkılaştırılır", "nasıl yapılandırılır", "harden") medium'a yükseltilir.
    HARDENING_ACTION_PATTERNS = [
        r'\b(s[ıi]k[ıi]laşt[ıi]r|güçlendir|harden(?:ing)?|yapılandır|configure|secure)\b',
        r'nasıl.*(güvenli|yap[ıi]l|ayarla|aç[ıi]l|kapat|değiştir|kur|engelle|etkinleştir|devre)',
        r'\bhow\s+to\b',
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

        # ─── SIMPLE: açık tanım/smalltalk pattern'leri ───
        # ("firewall nedir", "ssh ne demek" → basit tanım → LLM bilir, RAG'a gerek yok)
        for pattern in self.SIMPLE_PATTERNS:
            if re.search(pattern, q_lower, re.IGNORECASE):
                return "simple"

        # ─── COMPLEX: Karmaşık analiz gerektiren ───
        for pattern in self.COMPLEX_PATTERNS:
            if re.search(pattern, q_lower, re.IGNORECASE):
                return "complex"

        # ─── MEDIUM: Spesifik/hardening (kısa olsa bile) ───
        # ÖNEMLİ: bu kontrol, "word_count <= 3 → simple" KISA-DEVRESİNDEN ÖNCE çalışır.
        # Aksi halde "SSH nasıl sıkılaştırılır" (3 kelime) basit tanım sanılıp 'simple'
        # olur ve RAG atlanır → hardening sorusu kaynaksız (CIS'siz) cevaplanır.
        for pattern in self.MEDIUM_PATTERNS:
            if re.search(pattern, q_lower, re.IGNORECASE):
                return "medium"

        # ─── Çok kısa + hiçbir tanım/hardening sinyali YOK → simple (LLM bilir) ───
        if word_count <= 3:
            return "simple"

        # ─── DEFAULT: Kelime sayısına göre ───
        # Kısa sorular (4-10 kelime) → medium (security chatbot için)
        if word_count <= 10:
            return "medium"

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
