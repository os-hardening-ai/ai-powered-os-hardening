# utils/local_responder.py
"""
Lokal Pattern-Based Response Sistemi

LLM çağrısı yapmadan basit soruları yanıtlar:
- Selamlaşma / Vedalaşma
- Teşekkür
- Genel sorular ("sana bir sorum var" gibi)
- Basit yönlendirmeler

Avantajlar:
- Maliyet: $0 (LLM yok)
- Hız: <1ms (regex matching)
- Tutarlılık: Her zaman aynı profesyonel ton
"""

from __future__ import annotations
import re
import random
from typing import Optional


class LocalResponder:
    """
    Pattern-based lokal cevap sistemi.

    Basit keyword/regex matching ile hızlı cevaplar üretir.
    LLM çağrısı yapmaz, maliyeti sıfır.
    """

    def __init__(self):
        # Selamlaşma pattern'leri
        self.greeting_patterns = [
            r'\b(merhaba|selam|hey|hi|hello|günaydın|iyi günler|hoş geldin)\b',
        ]

        self.greeting_responses = [
            "Merhaba! Siber güvenlik konusunda size nasıl yardımcı olabilirim?",
            "Selam! Güvenlik sorunuz için buradayım.",
            "Merhaba! OS hardening, Zero Trust veya güvenlik yapılandırmaları hakkında soru sorabilirsiniz.",
        ]

        # Vedalaşma pattern'leri
        self.farewell_patterns = [
            r'\b(görüşürüz|hoşça kal|bye|güle güle|kendine iyi bak|bb|elveda)\b',
        ]

        self.farewell_responses = [
            "Görüşürüz! Güvenli kalın.",
            "Hoşça kalın! Başka sorunuz olursa bekliyorum.",
            "İyi günler! Sistemleriniz güvende olsun.",
        ]

        # Teşekkür pattern'leri
        self.thanks_patterns = [
            r'\b(teşekkür|sağ ol|thanks|thank you|eyvallah|süper oldu|harika)\b',
        ]

        self.thanks_responses = [
            "Rica ederim! Başka bir konuda yardımcı olabilir miyim?",
            "Memnun oldum! Başka güvenlik sorunuz varsa sorabilirsiniz.",
            "Bir şey değil! Güvenli kalın.",
        ]

        # Genel soru/yardım pattern'leri
        self.help_patterns = [
            r'\b(sana bir sorum var|soru sormak istiyorum|yardım|help|nasıl çalışırsın)\b',
        ]

        self.help_responses = [
            "Tabii, size nasıl yardımcı olabilirim? Güvenlik, hardening, Zero Trust veya sistem yapılandırması hakkında sorular sorabilirsiniz.",
            "Elbette! SSH, firewall, RDP, monitoring gibi konularda size yardımcı olabilirim. Sorunuzu sorabilirsiniz.",
            "Buyurun! Siber güvenlik, OS hardening, log yönetimi gibi konularda destek verebilirim.",
        ]

        # Onaylama/Olumlama pattern'leri
        self.affirmation_patterns = [
            r'^(evet|evet devam et|tamam|ok|okay|anladım|peki)$',
        ]

        self.affirmation_responses = [
            "Harika! Devam edelim. Başka bir sorunuz var mı?",
            "Tamam! Size başka nasıl yardımcı olabilirim?",
        ]

        # Domain-Specific: Cyber Security Tanımları
        self.security_definitions = {
            # Zero Trust
            "zero trust": "Zero Trust, 'hiçbir şeye güvenme, her şeyi doğrula' prensibiyle çalışan bir güvenlik modelidir. Network içinde/dışında tüm erişimler sürekli doğrulanır.",
            "zt": "ZT (Zero Trust) = Hiçbir kullanıcı veya cihaza varsayılan güven yoktur. Her erişim istek-bazlı doğrulanır.",

            # Standards
            "cis": "CIS (Center for Internet Security) Benchmarks, sistem güvenliği için endüstri standardı yapılandırma kılavuzlarıdır. Ubuntu, Windows, Docker vb. için kontrol listeleri sunar.",
            "nist": "NIST (National Institute of Standards and Technology), ABD hükümeti için güvenlik standartları geliştirir. NIST 800-53, 800-171 gibi kontrol çerçeveleri vardır.",
            "iso 27001": "ISO 27001, bilgi güvenliği yönetim sistemleri (ISMS) için uluslararası standarttır. Sertifikasyon gerektirir.",

            # Common Terms
            "selinux": "SELinux (Security-Enhanced Linux), Linux kerneline entegre mandatory access control (MAC) güvenlik mekanizmasıdır. RedHat/CentOS'ta varsayılan aktif.",
            "apparmor": "AppArmor, SELinux'a alternatif MAC (Mandatory Access Control) sistemidir. Ubuntu'da varsayılan. Profil-bazlı çalışır.",
            "hardening": "Hardening (sıkılaştırma), bir sistemin saldırı yüzeyini azaltmak için gereksiz servisleri kapatma, güvenlik ayarlarını artırma sürecidir.",
            "least privilege": "Least Privilege (en az yetki) prensibi: Her kullanıcı/süreç, işini yapmak için gereken MINIMUM yetkiye sahip olmalıdır.",

            # Attack Types
            "brute force": "Brute force saldırısı, tüm olası şifre kombinasyonlarını deneyerek sisteme giriş yapmaya çalışmaktır. Fail2ban gibi araçlarla önlenebilir.",
            "ddos": "DDoS (Distributed Denial of Service), birçok kaynaktan gelen trafik ile hedef sistemi çökertme saldırısıdır. Firewall rate limiting ile azaltılabilir.",
            "man in the middle": "Man-in-the-Middle (MITM), saldırganın iki taraf arasındaki iletişimi dinleme/değiştirme saldırısıdır. TLS/SSL ile önlenir.",
        }

        # Domain-Specific: Quick Commands (keywords for flexible matching)
        self.quick_commands = {
            ("ssh", "port"): "SSH port değiştirme:\n1. sudo nano /etc/ssh/sshd_config\n2. Port 22 → Port 2222 (örnek)\n3. sudo systemctl restart sshd\n4. sudo firewall-cmd --add-port=2222/tcp (firewall için)",
            ("firewall", "durum"): "Firewall kontrol:\nUbuntu/Debian: sudo ufw status\nCentOS/RHEL: sudo firewall-cmd --state",
            ("ssh", "restart"): "SSH restart:\nUbuntu: sudo systemctl restart ssh\nCentOS: sudo systemctl restart sshd",
            ("fail2ban", "kurulum"): "Fail2ban kurulum:\nUbuntu: sudo apt install fail2ban -y\nCentOS: sudo yum install fail2ban -y\nBaşlat: sudo systemctl enable --now fail2ban",
        }

    def check_and_respond(self, question: str) -> Optional[str]:
        """
        Soruyu kontrol et ve lokal cevap dönebiliyorsa döndür.

        Args:
            question: Kullanıcı sorusu

        Returns:
            Lokal cevap string veya None (LLM gerekli)
        """
        q_lower = question.lower().strip()

        # Çok kısa sorular için ekstra kontrol (1-2 kelime)
        word_count = len(question.split())

        # 1. Selamlaşma
        if word_count <= 3:  # Kısa selamlaşmalar
            for pattern in self.greeting_patterns:
                if re.search(pattern, q_lower, re.IGNORECASE):
                    return random.choice(self.greeting_responses)

        # 2. Vedalaşma
        for pattern in self.farewell_patterns:
            if re.search(pattern, q_lower, re.IGNORECASE):
                return random.choice(self.farewell_responses)

        # 3. Teşekkür
        for pattern in self.thanks_patterns:
            if re.search(pattern, q_lower, re.IGNORECASE):
                return random.choice(self.thanks_responses)

        # 4. Yardım/Genel soru
        for pattern in self.help_patterns:
            if re.search(pattern, q_lower, re.IGNORECASE):
                return random.choice(self.help_responses)

        # 5. Onaylama (sadece tek kelime/kısa)
        if word_count <= 2:
            for pattern in self.affirmation_patterns:
                if re.search(pattern, q_lower, re.IGNORECASE):
                    return random.choice(self.affirmation_responses)

        # 6. Domain-Specific: Security Definitions
        # "nedir?" veya "ne demek?" pattern'i varsa
        if re.search(r'\b(nedir|ne demek|nedir ki|ne anlama gelir)\b', q_lower):
            for term, definition in self.security_definitions.items():
                if term in q_lower:
                    return f"**{term.upper()}**: {definition}"

        # 7. Domain-Specific: Quick Commands
        # "nasıl" veya command-related pattern varsa
        if re.search(r'\b(nasıl|nasil|komutu|komutları|değiş|degis|restart|kontrol|durum|kurulum)\b', q_lower):
            for cmd_keywords, cmd_response in self.quick_commands.items():
                # cmd_keywords artık tuple (örn: ("ssh", "port"))
                if all(keyword in q_lower for keyword in cmd_keywords):
                    return cmd_response

        # Lokal cevap yok, LLM gerekli
        return None

    def get_stats(self) -> dict:
        """İstatistik bilgisi döndür."""
        return {
            "total_patterns": (
                len(self.greeting_patterns) +
                len(self.farewell_patterns) +
                len(self.thanks_patterns) +
                len(self.help_patterns) +
                len(self.affirmation_patterns)
            ),
            "categories": {
                "greeting": len(self.greeting_patterns),
                "farewell": len(self.farewell_patterns),
                "thanks": len(self.thanks_patterns),
                "help": len(self.help_patterns),
                "affirmation": len(self.affirmation_patterns),
            }
        }


# Global instance
_local_responder = LocalResponder()


def get_local_response(question: str) -> Optional[str]:
    """
    Lokal cevap döndür (varsa).

    Args:
        question: Kullanıcı sorusu

    Returns:
        Lokal cevap veya None
    """
    return _local_responder.check_and_respond(question)


# ─────────────────────────────────────────────
# Test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        # Lokal cevap dönmeli
        ("merhaba", True),
        ("selam", True),
        ("görüşürüz", True),
        ("teşekkür ederim", True),
        ("sağ ol", True),
        ("sana bir sorum var", True),
        ("evet", True),

        # LLM gerekli
        ("SELinux nedir?", False),
        ("SSH yapılandırması nasıl yapılır", False),
        ("merhaba, SSH hardening hakkında bilgi alabilir miyim", False),  # Uzun, LLM gerekli
    ]

    print("="*70)
    print("LOCAL RESPONDER - TEST")
    print("="*70)

    responder = LocalResponder()

    for question, should_respond_locally in test_cases:
        response = responder.check_and_respond(question)

        if should_respond_locally:
            status = "OK" if response else "FAIL"
            expected = "LOCAL"
        else:
            status = "OK" if not response else "FAIL"
            expected = "LLM"

        result = "LOCAL" if response else "LLM"

        print(f"[{status:4s}] [{result:5s} | Expected: {expected:5s}] {question}")
        if response:
            print(f"        Response: {response[:60]}...")

    print("="*70)
    stats = responder.get_stats()
    print(f"Total patterns: {stats['total_patterns']}")
    print(f"Categories: {stats['categories']}")
    print("="*70)
