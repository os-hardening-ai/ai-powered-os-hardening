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
    # ── EK Ubuntu — SSH derinlik ──
    ("SSH için izinli MAC algoritmaları nasıl sınırlandırılır", "ubuntu_24_04"),
    ("SSH KexAlgorithms (anahtar değişimi) nasıl sıkılaştırılır", "ubuntu_24_04"),
    ("SSH LoginGraceTime ve MaxStartups nasıl ayarlanır", "ubuntu_24_04"),
    ("SSH banner (uyarı mesajı) nasıl yapılandırılır", "ubuntu_24_04"),
    ("SSH X11Forwarding neden kapatılmalı ve nasıl yapılır", "ubuntu_24_04"),
    # ── EK Ubuntu — kimlik / yetki ──
    ("root dışı kullanıcılar için sudo yetkisi nasıl kısıtlanır", "ubuntu_24_04"),
    ("su komutu kullanımı pam_wheel ile nasıl sınırlandırılır", "ubuntu_24_04"),
    ("Boş parolalı hesaplar nasıl tespit edilir ve engellenir", "ubuntu_24_04"),
    ("UID 0 olan tek hesabın root olması nasıl doğrulanır", "ubuntu_24_04"),
    ("Inaktif hesapların otomatik kilitlenmesi nasıl ayarlanır", "ubuntu_24_04"),
    # ── EK Ubuntu — audit kuralları ──
    ("auditd ile kullanıcı/grup değişikliklerini izleyen kural", "ubuntu_24_04"),
    ("auditd ile sudoers değişikliklerini izleyen kural", "ubuntu_24_04"),
    ("auditd ile başarısız oturum açma denemelerini izleme", "ubuntu_24_04"),
    ("auditd log dosyalarının boyutu ve saklama politikası nasıl ayarlanır", "ubuntu_24_04"),
    # ── EK Ubuntu — ağ / kernel ──
    ("sysctl ile source routing nasıl devre dışı bırakılır", "ubuntu_24_04"),
    ("sysctl ile SYN flood koruması (tcp_syncookies) nasıl açılır", "ubuntu_24_04"),
    ("sysctl ile ASLR (randomize_va_space) nasıl etkinleştirilir", "ubuntu_24_04"),
    ("IPv6 gerekli değilse nasıl güvenli devre dışı bırakılır", "ubuntu_24_04"),
    ("Çekirdek çekirdek dökümü (core dump) nasıl kısıtlanır", "ubuntu_24_04"),
    # ── EK Ubuntu — dosya sistemi / modül ──
    ("squashfs ve udf modülleri nasıl devre dışı bırakılır", "ubuntu_24_04"),
    ("Sticky bit dünya-yazılabilir dizinlerde nasıl doğrulanır", "ubuntu_24_04"),
    ("Sahipsiz (unowned) dosyalar nasıl bulunur", "ubuntu_24_04"),
    ("/home için ayrı bölüm ve nodev nasıl uygulanır", "ubuntu_24_04"),
    ("SUID/SGID dosyalar nasıl denetlenir", "ubuntu_24_04"),
    # ── EK Ubuntu — servis / zaman / patching ──
    ("NTP/chrony ile zaman senkronizasyonu güvenli nasıl kurulur", "ubuntu_24_04"),
    ("rsync, telnet, ftp gibi güvensiz servisler nasıl kaldırılır", "ubuntu_24_04"),
    ("GRUB önyükleyici parolası nasıl ayarlanır", "ubuntu_24_04"),
    ("Otomatik ekran kilidi ve idle timeout nasıl zorunlu kılınır", "ubuntu_24_04"),
    ("APT için yalnız imzalı paket deposu nasıl zorunlu kılınır", "ubuntu_24_04"),
    ("MOTD ve issue banner yasal uyarısı nasıl ayarlanır", "ubuntu_24_04"),
    # ── EK Windows 11 / Server — derinlik ──
    ("Windows'ta NTLMv1 nasıl devre dışı bırakılır", "windows_11"),
    ("Windows'ta LSA korumasını (RunAsPPL) nasıl etkinleştirilir", "windows_11"),
    ("Windows'ta PowerShell script block logging nasıl açılır", "windows_11"),
    ("Windows'ta Credential Guard nasıl etkinleştirilir", "windows_11"),
    ("Windows'ta anonim SID/Name çevirimi nasıl engellenir", "windows_11"),
    ("Windows'ta ekran koruyucu parola zorunluluğu nasıl ayarlanır", "windows_11"),
    ("Windows'ta USB depolama aygıtları nasıl kısıtlanır", "windows_11"),
    ("Windows'ta Windows Firewall tüm profillerde nasıl açılır", "windows_11"),
    ("Windows'ta minimum parola uzunluğu ve karmaşıklık GPO ile nasıl", "windows_11"),
    ("Windows Server'da SMB imzalama nasıl zorunlu kılınır", "windows_server_2025"),
    ("Windows Server'da LDAP imzalama nasıl zorunlu kılınır", "windows_server_2025"),
    ("Windows Server'da gereksiz hesapların denetimi nasıl yapılır", "windows_server_2025"),
    # ── EK kavramsal (RAG'siz de cevaplanabilir, generic) ──
    ("PermitRootLogin no neden önemlidir", "ubuntu_24_04"),
    ("Least privilege ilkesi sysadmin için ne anlama gelir", "ubuntu_24_04"),
    ("CIS Benchmark ile DISA STIG arasındaki fark nedir", "ubuntu_24_04"),
    ("Defense in depth katmanları nelerdir", "ubuntu_24_04"),
    ("NIST 800-207 Zero Trust temel ilkeleri nelerdir", "ubuntu_24_04"),
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
