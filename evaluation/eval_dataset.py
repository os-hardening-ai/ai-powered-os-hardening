"""
A3 — Değerlendirme veri seti (50+ küratörlü soru). H1/RAGAS/İP-5/ablation için ortak kaynak.

Dengeli: Ubuntu 24.04 + Windows 11 + Windows Server; kategoriler — SSH, parola/PAM, audit,
firewall, kernel/sysctl, dosya sistemi, servis, patching, + GENİŞ/çok-alanlı (query-planning testi).
Her giriş: (soru, os_version). İstatistiksel güç için 24 → 52'ye çıkarıldı.
"""
from __future__ import annotations
from typing import List, Tuple

EVAL_QUESTIONS: List[Tuple[str, str]] = [
    # ── Ubuntu — SSH ──
    ("SSH için PermitRootLogin nasıl devre dışı bırakılır", "ubuntu_24_04"),
    ("SSH MaxAuthTries değeri ne olmalı ve neden", "ubuntu_24_04"),
    ("SSH idle timeout (ClientAlive) nasıl ayarlanır", "ubuntu_24_04"),
    ("sshd için izinli şifreleme algoritmaları (Ciphers) nasıl sınırlandırılır", "ubuntu_24_04"),
    ("SSH'de yalnız belirli kullanıcı/gruba (AllowGroups) erişim nasıl verilir", "ubuntu_24_04"),
    ("SSH PasswordAuthentication kapatılıp anahtar tabanlı kimlik nasıl zorunlu kılınır", "ubuntu_24_04"),
    # ── Ubuntu — parola / PAM ──
    ("Parola minimum uzunluğu ve karmaşıklığı nasıl zorunlu kılınır", "ubuntu_24_04"),
    ("PAM ile hesap kilitleme (faillock) nasıl yapılandırılır", "ubuntu_24_04"),
    ("Parola geçmişi (remember) ve yeniden kullanım engeli nasıl kurulur", "ubuntu_24_04"),
    ("Parola yaşlandırma (PASS_MAX_DAYS) nasıl ayarlanır", "ubuntu_24_04"),
    # ── Ubuntu — audit / logging ──
    ("auditd nasıl etkinleştirilir ve kuralları kalıcı yapılır", "ubuntu_24_04"),
    ("auditd ile zaman değişikliklerini izleyen kural nasıl eklenir", "ubuntu_24_04"),
    ("sudo komutlarının loglanması nasıl sağlanır", "ubuntu_24_04"),
    ("Log rotation (logrotate) güvenli nasıl yapılandırılır", "ubuntu_24_04"),
    # ── Ubuntu — firewall / ağ ──
    ("UFW ile varsayılan deny politikası nasıl ayarlanır", "ubuntu_24_04"),
    ("iptables ile yalnız gerekli portlara izin nasıl verilir", "ubuntu_24_04"),
    ("sysctl ile IP forwarding nasıl kapatılır", "ubuntu_24_04"),
    ("sysctl ile ICMP redirect kabulü nasıl engellenir", "ubuntu_24_04"),
    # ── Ubuntu — kernel modül / dosya sistemi ──
    ("cramfs dosya sistemi modülü nasıl devre dışı bırakılır", "ubuntu_24_04"),
    ("usb-storage modülü nasıl devre dışı bırakılır", "ubuntu_24_04"),
    ("/tmp için nodev,nosuid,noexec mount seçenekleri nasıl uygulanır", "ubuntu_24_04"),
    ("/var/tmp ve /dev/shm güvenli mount nasıl yapılır", "ubuntu_24_04"),
    ("Dünya-yazılabilir dosyalar nasıl bulunur ve düzeltilir", "ubuntu_24_04"),
    # ── Ubuntu — servis / bakım ──
    ("Gereksiz servisler (avahi, cups) nasıl tespit edilip durdurulur", "ubuntu_24_04"),
    ("Otomatik güvenlik güncellemeleri (unattended-upgrades) nasıl kurulur", "ubuntu_24_04"),
    ("Cron job güvenliği ve /etc/cron.allow nasıl yapılandırılır", "ubuntu_24_04"),
    ("AppArmor profilleri nasıl enforce moduna alınır", "ubuntu_24_04"),
    # ── Ubuntu — kavramsal (RAG'siz de cevaplanabilir) ──
    ("CIS Benchmark nedir ve Level 1 / Level 2 farkı nedir", "ubuntu_24_04"),
    ("Zero Trust mimarisinde least privilege ne demek", "ubuntu_24_04"),
    ("Defense in depth yaklaşımı nedir", "ubuntu_24_04"),
    # ── Windows 11 ──
    ("Windows 11'de parola geçmişi nasıl zorlanır", "windows_11"),
    ("Windows 11'de hesap kilitleme eşiği nasıl ayarlanır", "windows_11"),
    ("Windows 11'de SMBv1 nasıl devre dışı bırakılır", "windows_11"),
    ("Windows 11'de Windows Defender gerçek zamanlı koruma nasıl zorunlu kılınır", "windows_11"),
    ("Windows 11'de oturum açma denetim politikası nasıl ayarlanır", "windows_11"),
    ("Windows 11'de UAC en yüksek seviyeye nasıl alınır", "windows_11"),
    ("Windows 11'de BitLocker nasıl etkinleştirilir", "windows_11"),
    ("Windows 11'de PowerShell script execution policy nasıl kısıtlanır", "windows_11"),
    ("Windows 11'de AutoPlay/AutoRun nasıl devre dışı bırakılır", "windows_11"),
    ("Windows 11'de RDP NLA (Network Level Authentication) nasıl zorunlu kılınır", "windows_11"),
    ("Windows 11'de misafir (Guest) hesabı nasıl devre dışı bırakılır", "windows_11"),
    ("Windows 11'de LAN Manager kimlik doğrulama seviyesi nasıl sıkılaştırılır", "windows_11"),
    # ── Windows Server ──
    ("Windows Server'da gereksiz roller/özellikler nasıl kaldırılır", "windows_server_2025"),
    ("Windows Server'da denetim (audit) politikası nasıl yapılandırılır", "windows_server_2025"),
    ("Windows Server'da uzak masaüstü güvenliği nasıl sağlanır", "windows_server_2025"),
    # ── GENİŞ / çok-alanlı (query-planning / multi-query testi — İP-5 zorlu vakaları) ──
    ("SSH sunucusunu kapsamlı şekilde sıkılaştır", "ubuntu_24_04"),
    ("Parola politikasını ve PAM kurallarını güçlendir", "ubuntu_24_04"),
    ("Ağ ve kernel parametre güvenliğini yapılandır", "ubuntu_24_04"),
    ("Denetim (audit) ve sistem bütünlüğü kurallarını uygula", "ubuntu_24_04"),
    ("Yazılım ve servis yapılandırmasını sıkılaştır", "ubuntu_24_04"),
    ("Güvenlik yamaları ve erişim kontrolü politikasını uygula", "ubuntu_24_04"),
    ("Tam sistem sıkılaştırması yap (çok alanlı)", "ubuntu_24_04"),
    ("Windows 11 iş istasyonunu CIS'e göre baştan sona sıkılaştır", "windows_11"),
]

# Geniş/çok-alanlı sorgular (query-planning A/B + İP-5 zorlu vakaları için alt küme)
BROAD_QUESTIONS: List[Tuple[str, str]] = [q for q in EVAL_QUESTIONS if q[0].split()[-1] in
                                          ("sıkılaştır", "güçlendir", "yapılandır", "uygula", "alanlı)")
                                          or "kapsamlı" in q[0] or "baştan sona" in q[0]]
