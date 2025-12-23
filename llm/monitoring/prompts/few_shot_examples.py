# prompts/few_shot_examples.py
"""
Few-Shot Examples for Quality Improvement

Bu örnekler LLM'e format ve kalite standardını gösterir.
"""

FEW_SHOT_EXAMPLES = """
═══════════════════════════════════════════════════════════════════
📚 ÖRNEK 1: SSH Hardening (Optimal Cevap Formatı)
═══════════════════════════════════════════════════════════════════

KULLANICI SORUSU:
"SSH'yi nasıl güvenli hale getiririm?"

BAĞLAM:
- OS: ubuntu_22_04
- Rol: sysadmin
- Security Level: strict
- ZT Maturity: medium

─────────────────────────────────────────────────────────────────

ADIM 1: GÜVENLİK DEĞERLENDİRMESİ

Bu bir savunma amaçlı sistem sıkılaştırma talebi. Kullanıcı SSH servisinin
güvenlik açıklarını kapatmak ve yetkisiz erişimi önlemek istiyor.

**Sonuç:** ✅ defensive_security

─────────────────────────────────────────────────────────────────

ADIM 2: NİYET ANALİZİ

Kullanıcı SSH servisi için güvenlik yapılandırması istiyor. Bu hem konfigürasyon
değişiklikleri hem de potansiyel olarak script içerebilir.

**Intent:** os_hardening
**Hedef Alan:** ssh
**Script Gerekli:** Evet (otomasyon için)

─────────────────────────────────────────────────────────────────

ADIM 3: ZERO TRUST PRENSİPLERİ

Bu taleple ilişkili ZT prensipleri:

✓ **least_privilege**: Root login'i devre dışı bırakarak, sadece gerekli
  kullanıcıların sudo ile yetki alması sağlanır.

✓ **strong_identity**: SSH key-based authentication, password'den çok daha
  güçlü kimlik doğrulama sağlar. Private key olmadan giriş imkansızdır.

✓ **continuous_verification**: Fail2ban ile başarısız login denemelerini
  izleyerek sürekli tehdit tespiti yapılır.

**Standart Referansları:**
- CIS_Ubuntu_22_04:5.2.5 (PermitRootLogin disabled)
- CIS_Ubuntu_22_04:5.2.10 (PasswordAuthentication disabled)
- NIST_800-53:AC-17 (Remote Access Controls)
- ISO_27001:A.9.2.3 (Management of privileged access rights)

─────────────────────────────────────────────────────────────────

ADIM 4: RİSK DEĞERLENDİRMESİ

**Risk Seviyesi:** medium

**Etki Analizi:**
- SSH servis restart gerekir (~1 saniye kesinti)
- Yanlış yapılandırma halinde sistem erişimi kaybolabilir (kritik!)
- Test ortamında mutlaka denenmeli
- Aktif bir SSH oturumu açık tutulmalı (rollback için)

**Rollback Stratejisi:**
1. Config dosyasını yedekle: /etc/ssh/sshd_config
2. Değişiklik öncesi yeni bir terminal oturumu aç
3. Sorun olursa: backup'tan geri yükle ve servisi restart et

─────────────────────────────────────────────────────────────────

ADIM 5: UYGULAMA PLANI

1. Backup alma
2. SSH key pair oluşturma (yoksa)
3. Public key'i authorized_keys'e ekleme
4. sshd_config düzenleme
5. Config syntax kontrolü
6. Test bağlantısı (yeni terminal)
7. Servis restart
8. Final test

─────────────────────────────────────────────────────────────────

ADIM 6: DETAYLI KULLANICI CEVABI

## 📋 ÖZET

SSH servisini CIS Benchmark standardlarına göre sıkılaştırarak brute-force
saldırıları ve yetkisiz erişim riskini minimuma indireceğiz.

## 🎯 GEREKÇE

SSH, Linux sistemlerde uzaktan yönetim için kritik bir servistir. Ancak
default yapılandırması ciddi güvenlik açıkları içerir:

- **Root login aktif**: Saldırganlar doğrudan root hesabını hedefleyebilir
- **Password authentication**: Brute-force ve credential stuffing saldırılarına açık
- **Zayıf cipher'lar**: Eski şifreleme algoritmaları kullanımda olabilir

Bu açıklar, özellikle internet'e açık sunucularda ciddi risk oluşturur.

## 🔐 ZERO TRUST İLİŞKİSİ

- **Least Privilege (En Az Yetki)**: Root erişimini tamamen kapat. Kullanıcılar
  normal hesaplarla giriş yapıp, sadece gerektiğinde sudo ile yetki alsın.

- **Strong Identity (Güçlü Kimlik)**: SSH key-based authentication zorunlu
  kılınarak, password tahmin saldırıları imkansız hale gelir.

- **Continuous Verification (Sürekli Doğrulama)**: Fail2ban ile başarısız
  login denemelerini izle ve otomatik IP ban uygula.

## ⚠️ RİSK ETKİSİ

- **Seviye**: Medium
- **Etki**: SSH servisi restart gerektirir (~1 saniye kesinti)
- **Dikkat**: Yanlış konfigürasyon halinde sistem erişimi kaybolabilir
- **Önlem**: Değişiklik öncesi MUTLAKA yeni bir terminal oturumu açık tutun

## ✅ ÖNERİLEN ADIMLAR

### Adım 1: Config Backup

```bash
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup.$(date +%Y%m%d)
```

### Adım 2: SSH Key Oluştur (yoksa)

```bash
# Local makinende çalıştır
ssh-keygen -t ed25519 -C "your_email@example.com"

# Public key'i server'a kopyala
ssh-copy-id user@server_ip
```

### Adım 3: SSH Config Düzenle

```bash
sudo nano /etc/ssh/sshd_config
```

Aşağıdaki satırları değiştir/ekle:

```
# Root erişimini kapat
PermitRootLogin no

# Password authentication'ı kapat
PasswordAuthentication no
PubkeyAuthentication yes

# Sadece belirli kullanıcılara izin ver (opsiyonel)
AllowUsers yourusername

# Güvenli protokol
Protocol 2

# Güçlü cipherlar
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com

# Login timeout
LoginGraceTime 30
MaxAuthTries 3
```

### Adım 4: Config Test Et

```bash
sudo sshd -t
```

Çıktı: "sshd: config file /etc/ssh/sshd_config: configuration OK" olmalı

### Adım 5: Yeni Terminal Aç (Kritik!)

Değişiklikleri uygulamadan önce MUTLAKA yeni bir terminal oturumu açın.
Sorun olursa bu oturumdan rollback yapabilirsiniz.

### Adım 6: Servisi Restart Et

```bash
sudo systemctl restart sshd
```

### Adım 7: Yeni Oturumla Test Et

```bash
# Yeni terminalde
ssh user@server_ip
```

SSH key ile bağlanabildiğinizi doğrulayın.

## 💻 ÖRNEK KOMUTLAR

### Otomatik Hardening Script

```bash
#!/bin/bash
# ssh_hardening.sh
# SSH güvenlik yapılandırma scripti

set -euo pipefail

echo "🛡️  SSH Hardening Script"
echo "===================="

# Root check
if [[ $EUID -ne 0 ]]; then
   echo "❌ Bu script root olarak çalıştırılmalı"
   exit 1
fi

# Backup
BACKUP_FILE="/etc/ssh/sshd_config.backup.$(date +%Y%m%d_%H%M%S)"
echo "📦 Backup alınıyor: $BACKUP_FILE"
cp /etc/ssh/sshd_config "$BACKUP_FILE"

# Config değişiklikleri
echo "🔧 Config düzenleniyor..."

sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config

# Protocol ekle (yoksa)
if ! grep -q "^Protocol 2" /etc/ssh/sshd_config; then
    echo "Protocol 2" >> /etc/ssh/sshd_config
fi

# MaxAuthTries ekle
if ! grep -q "^MaxAuthTries" /etc/ssh/sshd_config; then
    echo "MaxAuthTries 3" >> /etc/ssh/sshd_config
fi

# Config test
echo "✅ Config test ediliyor..."
if ! sshd -t; then
    echo "❌ Config hatası! Backup'tan geri yükleniyor..."
    cp "$BACKUP_FILE" /etc/ssh/sshd_config
    exit 1
fi

echo "✅ Config test başarılı!"
echo ""
echo "⚠️  ÖNEMLİ UYARI:"
echo "   - Devam etmeden önce BAŞKA BİR TERMINAL AÇIN!"
echo "   - SSH key ile bağlanabildiğinizi doğrulayın"
echo "   - Sorun olursa rollback: cp $BACKUP_FILE /etc/ssh/sshd_config"
echo ""
read -p "Devam edilsin mi? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🔄 SSH servisi yeniden başlatılıyor..."
    systemctl restart sshd
    echo "✅ SSH hardening tamamlandı!"
    echo "   Yeni bir terminalde SSH bağlantısını test edin."
else
    echo "❌ İşlem iptal edildi. Config değişiklikleri uygulanmadı."
    cp "$BACKUP_FILE" /etc/ssh/sshd_config
fi
```

### Kullanım:

```bash
chmod +x ssh_hardening.sh
sudo ./ssh_hardening.sh
```

## 📚 STANDART REFERANSLARI

- **CIS_Ubuntu_22_04:5.2.5**: SSH PermitRootLogin disabled
  → Root hesabı ile doğrudan SSH erişimini engeller

- **CIS_Ubuntu_22_04:5.2.10**: SSH PasswordAuthentication disabled
  → Password tabanlı kimlik doğrulamayı kapatır, sadece key kullanımı

- **NIST_800-53:AC-17**: Remote Access
  → Uzaktan erişim kontrollerinin uygulanması

- **ISO_27001:A.9.2.3**: Management of privileged access rights
  → Ayrıcalıklı erişim haklarının yönetimi

## 🔄 ROLLBACK YAKLAŞIMI

Sorun çıkarsa aşağıdaki adımları izle:

### 1. Backup'tan Geri Yükle

```bash
sudo cp /etc/ssh/sshd_config.backup.YYYYMMDD /etc/ssh/sshd_config
```

### 2. Servisi Restart Et

```bash
sudo systemctl restart sshd
```

### 3. Bağlantıyı Test Et

```bash
ssh user@server_ip
```

### Acil Durum: Console Access

Eğer SSH erişimi tamamen kaybettiyseniz:
- Cloud console / KVM / IPMI kullanarak sunucuya bağlanın
- `/etc/ssh/sshd_config` dosyasını backup'tan geri yükleyin
- `systemctl restart sshd` çalıştırın

**Not**: Bu yüzden değişiklik öncesi mutlaka yedek bir SSH oturumu açık tutulmalı!

═══════════════════════════════════════════════════════════════════
📚 ÖRNEK 2: Windows RDP Güvenliği (Kısa Format)
═══════════════════════════════════════════════════════════════════

KULLANICI SORUSU:
"RDP'yi nasıl güvenli hale getirebilirim?"

BAĞLAM:
- OS: windows_server_2022
- Rol: sysadmin
- Security Level: balanced
- ZT Maturity: low

ADIM 1-5: [Benzer analiz yapısı...]

ADIM 6: KULLANICI CEVABI

## 📋 ÖZET

Windows RDP (Remote Desktop Protocol) servisini NLA, hesap kilitleme ve
güvenlik duvarı kuralları ile güvenli hale getireceğiz.

## 🎯 GEREKÇE

RDP, Windows sunucularda en sık hedef alınan servistir:
- Default port (3389) otomatik taranır
- Brute-force saldırılara açık
- Man-in-the-middle riskleri

## 🔐 ZERO TRUST İLİŞKİSİ

- **Least Privilege**: Administrator grubu yerine özel RDP grubu oluştur
- **Strong Identity**: NLA (Network Level Authentication) zorunlu kıl
- **Continuous Verification**: Account lockout ile başarısız denemeleri sınırla

## ⚠️ RİSK ETKİSİ

- **Seviye**: High (RDP kritik servis)
- **Etki**: Yanlış config tüm remote erişimi kapatabilir
- **Test**: Önce lab/test ortamında dene

## ✅ ÖNERİLEN ADIMLAR

### Adım 1: NLA Aktif Et

```powershell
# Registry ile
Set-ItemProperty -Path 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp' -Name "UserAuthentication" -Value 1

# veya Group Policy ile
# Computer Config → Admin Templates → Windows Components → Remote Desktop Services
# → RDP Host → Security → "Require user authentication for remote connections"
```

### Adım 2: Account Lockout Policy

```powershell
# Account lockout threshold
net accounts /lockoutthreshold:5

# Lockout duration (30 dakika)
net accounts /lockoutduration:30

# Reset counter (30 dakika)
net accounts /lockoutwindow:30
```

### Adım 3: Firewall Kuralı (IP Kısıtlama)

```powershell
# Sadece belirli IP'lerden RDP izni
New-NetFirewallRule -DisplayName "RDP from Office" -Direction Inbound -LocalPort 3389 -Protocol TCP -Action Allow -RemoteAddress 203.0.113.0/24

# Default RDP kuralını disable et
Disable-NetFirewallRule -DisplayName "Remote Desktop*"
```

### Adım 4: Port Değiştir (Opsiyonel)

```powershell
# Registry'de port değiştir
Set-ItemProperty -Path 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp' -Name "PortNumber" -Value 13389

# Firewall kuralını güncelle
New-NetFirewallRule -DisplayName "RDP Custom Port" -Direction Inbound -LocalPort 13389 -Protocol TCP -Action Allow
```

## 💻 ÖRNEK KOMUTLAR

**PowerShell Script:**

```powershell
# rdp_hardening.ps1

Write-Host "🛡️ RDP Hardening Script" -ForegroundColor Cyan

# NLA Aktif
Set-ItemProperty -Path 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp' -Name "UserAuthentication" -Value 1
Write-Host "✅ NLA enabled" -ForegroundColor Green

# Account Lockout
net accounts /lockoutthreshold:5 /lockoutduration:30 /lockoutwindow:30
Write-Host "✅ Account lockout configured" -ForegroundColor Green

# Restart RDP Service
Restart-Service TermService -Force
Write-Host "✅ RDP service restarted" -ForegroundColor Green

Write-Host "`n⚠️  IMPORTANT: Test RDP connection before closing this session!" -ForegroundColor Yellow
```

## 📚 STANDART REFERANSLARI

- CIS_Windows_Server_2022:18.9.58.1 (NLA requirement)
- NIST_800-53:AC-7 (Unsuccessful login attempts)
- ISO_27001:A.9.4.2 (Secure log-on procedures)

## 🔄 ROLLBACK

Sorun olursa:

```powershell
# NLA disable (geçici)
Set-ItemProperty -Path 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp' -Name "UserAuthentication" -Value 0

# Servisi restart
Restart-Service TermService -Force
```

═══════════════════════════════════════════════════════════════════

**ÖRNEKLER BİTTİ - ŞİMDİ SENİN SIRADA**

Yukarıdaki örnekleri format ve kalite rehberi olarak kullan.
Aynı yapıyı takip et: 6 adımlı analiz + kullanıcı cevabı.
"""
