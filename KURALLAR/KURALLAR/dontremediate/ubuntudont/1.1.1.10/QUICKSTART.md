# CIS 1.1.1.10 - Hızlı Başlangıç

## 🚀 3 Adımda Güvenli Kullanım

### Adım 1: Audit Çalıştır
```bash
sudo bash audit.sh
```

### Adım 2: Sonuçları İncele
Çıktıda şunlara dikkat et:
- ✅ **PASS** = İyi, değişiklik gerekmiyor
- ❌ **FAIL** + `CVE exists!` = Bu modülleri kapat
- ⚠️ **mounted** veya **protected** = ASLA kapatma!

### Adım 3: Manuel Remediation (Güvenli Yöntem)
```bash
# Sadece kullanmadığın ve CVE'si olan modülleri kapat
sudo bash remediation_manual.sh gfs2
sudo bash remediation_manual.sh cifs
sudo bash remediation_manual.sh nfsd
```

---

## ⚠️ ÖNEMLİ NOTLAR

### ✅ YAPILACAKLAR
- ✅ Audit sonucunda `CVE exists!` olanları kapat
- ✅ Kullanmadığın dosya sistemlerini kapat
- ✅ Her modülü tek tek kapat (remediation_manual.sh)
- ✅ Production'da test etmeden yapma

### ❌ YAPILMAMASI GEREKENLER
- ❌ `xfs`, `ext4`, `vfat`, `overlay` gibi korumalı modülleri kapatma
- ❌ "mounted" yazan modülleri kapatma
- ❌ Otomatik remediation'ı production'da kullanma
- ❌ Audit yapmadan remediation yapma

---

## 📋 Örnek Komutlar

### CVE'li modülleri kapat (önerilir):
```bash
sudo bash remediation_manual.sh afs
sudo bash remediation_manual.sh ceph
sudo bash remediation_manual.sh cifs
sudo bash remediation_manual.sh exfat
sudo bash remediation_manual.sh gfs2
sudo bash remediation_manual.sh nfs_common
sudo bash remediation_manual.sh nfsd
```

### Audit tekrar çalıştır (doğrulama):
```bash
sudo bash audit.sh
```

### Sistem yeniden başlat (isteğe bağlı):
```bash
sudo reboot
```

---

## 🆘 Yardım

- Detaylı bilgi: [KULLANIM.md](KULLANIM.md)
- Teknik detaylar: [README.md](README.md)
- Sorun yaşıyorsan: Önce audit.sh çıktısını kontrol et

---

## ⚡ Hızlı Referans

| Script | Ne Zaman Kullan | Güvenlik |
|--------|----------------|----------|
| `audit.sh` | Her zaman önce bunu çalıştır | ✅ Güvenli |
| `remediation_manual.sh` | Production sistemler | ⭐⭐⭐⭐⭐ |
| `remediation.sh` | SADECE test sistemler | ⚠️ Dikkatli |

**Altın Kural:** Şüphen varsa `remediation_manual.sh` kullan!
