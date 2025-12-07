"""
Kullanıcı yapılandırma yöneticisi
OS, rol ve güvenlik seviyesini otomatik/yarı-otomatik tespit eder
"""
import platform
import json
import os
from pathlib import Path

try:
    import distro
except ImportError:
    distro = None


class ConfigManager:
    """Kullanıcı konfigürasyonunu yönetir"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(os.path.expanduser("~"), ".ai_hardening_config.json")
        self.config_path = config_path
        self.config = self.load_config()

    def detect_os(self) -> str:
        """İşletim sistemini otomatik tespit et"""
        system = platform.system().lower()

        if system == "linux":
            if distro:
                dist_name = distro.id()
                dist_version = distro.version()

                # Normalize et
                if "ubuntu" in dist_name:
                    version = dist_version.split('.')[0] + "_" + dist_version.split('.')[1]
                    return f"ubuntu_{version}"
                elif "centos" in dist_name or "rhel" in dist_name:
                    version = dist_version.split('.')[0]
                    return f"centos_{version}"
                elif "debian" in dist_name:
                    version = dist_version.split('.')[0]
                    return f"debian_{version}"
            return "linux_generic"

        elif system == "windows":
            version = platform.release().lower()
            return f"windows_{version}"

        elif system == "darwin":
            return "macos"

        return "unknown"

    def prompt_role(self) -> str:
        """Kullanıcı rolünü sor"""
        print("\n" + "="*50)
        print("🎯 KULLANICI ROLÜ SEÇİMİ")
        print("="*50)
        print("\n1. 👨‍💼 Sistem Yöneticisi (SysAdmin)")
        print("   → Server yönetimi, sistem yapılandırma")
        print("\n2. 👨‍💻 Geliştirici (Developer)")
        print("   → Uygulama geliştirme, test ortamı")
        print("\n3. 🔧 DevOps Mühendisi")
        print("   → CI/CD, container, otomasyon")
        print("\n4. 🔐 Güvenlik Uzmanı (Security)")
        print("   → Penetrasyon testi, güvenlik denetimi")
        print("\n5. 👤 Son Kullanıcı (End User)")
        print("   → Günlük kullanım, masaüstü sistemi")

        while True:
            choice = input("\n✨ Seçiminiz (1-5) [Varsayılan: 5]: ").strip() or "5"
            roles = {
                "1": "sysadmin",
                "2": "developer",
                "3": "devops",
                "4": "security",
                "5": "end_user"
            }
            if choice in roles:
                return roles[choice]
            print("❌ Geçersiz seçim! Lütfen 1-5 arası bir sayı girin.")

    def prompt_security_level(self) -> str:
        """Güvenlik seviyesini sor"""
        print("\n" + "="*50)
        print("🔒 GÜVENLİK SEVİYESİ")
        print("="*50)
        print("\n1. 🔴 Yüksek (High)")
        print("   → Maksimum güvenlik, bazı özellikler kısıtlı")
        print("   → Uygun: Production serverlar, kritik sistemler")
        print("\n2. 🟡 Dengeli (Balanced) ⭐ Önerilen")
        print("   → Güvenlik ve kullanılabilirlik dengesi")
        print("   → Uygun: Çoğu kullanım senaryosu")
        print("\n3. 🟢 Normal")
        print("   → Daha esnek, geliştirme dostu")
        print("   → Uygun: Test/dev ortamları")

        while True:
            choice = input("\n✨ Seçiminiz (1-3) [Varsayılan: 2]: ").strip() or "2"
            levels = {
                "1": "high",
                "2": "balanced",
                "3": "normal"
            }
            if choice in levels:
                return levels[choice]
            print("❌ Geçersiz seçim! Lütfen 1-3 arası bir sayı girin.")

    def load_config(self) -> dict:
        """Mevcut konfigürasyonu yükle"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def save_config(self):
        """Konfigürasyonu kaydet"""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        print(f"\n✅ Konfigürasyon kaydedildi: {self.config_path}")

    def setup_first_time(self):
        """İlk kurulum - kullanıcıdan bilgi al"""
        print("\n" + "="*50)
        print("🚀 AI-POWERED OS HARDENING - İLK KURULUM")
        print("="*50)

        # OS otomatik tespit
        detected_os = self.detect_os()
        print(f"\n🖥️  İşletim Sistemi: {detected_os} (otomatik tespit edildi)")

        # Rol sor
        role = self.prompt_role()

        # Güvenlik seviyesi sor
        security_level = self.prompt_security_level()

        # RAG ayarları
        print("\n" + "="*50)
        print("🔍 RAG AYARLARI (Advanced)")
        print("="*50)
        use_rag = input("\nRAG kullanılsın mı? (y/n) [Varsayılan: y]: ").strip().lower() != 'n'

        if use_rag:
            rag_top_k = input("Kaç kaynak döndürülsün? [Varsayılan: 5]: ").strip() or "5"
            rag_min_score = input("Minimum benzerlik skoru? (0.0-1.0) [Varsayılan: 0.7]: ").strip() or "0.7"
        else:
            rag_top_k = 5
            rag_min_score = 0.7

        # Kaydet
        self.config = {
            "os": detected_os,
            "role": role,
            "security_level": security_level,
            "use_rag": use_rag,
            "rag_top_k": int(rag_top_k),
            "rag_min_score": float(rag_min_score),
            "setup_completed": True
        }

        self.save_config()
        self.print_summary()

    def print_summary(self):
        """Konfigürasyon özetini göster"""
        print("\n" + "="*50)
        print("📋 KONFIGÜRASYON ÖZETİ")
        print("="*50)
        print(f"\n🖥️  İşletim Sistemi: {self.config['os']}")
        print(f"👤 Rol: {self.config['role']}")
        print(f"🔒 Güvenlik Seviyesi: {self.config['security_level']}")
        print(f"🔍 RAG Kullanımı: {'Evet' if self.config['use_rag'] else 'Hayır'}")
        if self.config['use_rag']:
            print(f"   └─ Top K: {self.config['rag_top_k']}")
            print(f"   └─ Min Score: {self.config['rag_min_score']}")
        print("="*50 + "\n")

    def get_config(self) -> dict:
        """Konfigürasyonu al (kurulum yoksa yap)"""
        if not self.config.get("setup_completed"):
            self.setup_first_time()
        return self.config

    def update_setting(self, key: str, value):
        """Tek bir ayarı güncelle"""
        self.config[key] = value
        self.save_config()

    def reset_config(self):
        """Konfigürasyonu sıfırla"""
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        self.config = {}
        print("✅ Konfigürasyon sıfırlandı.")


# CLI kullanımı için
if __name__ == "__main__":
    manager = ConfigManager()

    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        manager.reset_config()
    else:
        config = manager.get_config()
        manager.print_summary()
