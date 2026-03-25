# CIS 1.1.1.10 - Kullanım Kılavuzu

## ⚠️ ÖNEMLİ UYARI

Bu kontrol **MANUEL** bir kontroldür. Yanlış kullanım sisteminizin açılmamasına neden olabilir!

---

## Hızlı Başlangıç

### 1. Önce Audit Çalıştırın

```bash
sudo bash audit.sh
```

Bu komut size:
- Hangi modüllerin sistemde olduğunu
- Hangi modüllerin aktif kullanıldığını (BUNLARI KAPATMAYIN!)
- Hangi modüllerin CVE'si olduğunu
gösterecektir.

### 2. Sonuçları İnceleyin

Audit çıktısını dikkatlice okuyun:

```
[ PASS ] veya [ FAIL ] - Durumu gösterir
"protected" - Korumalı modüller (ASLA kapatmayın)
"mounted" - Aktif kullanılan modüller (ASLA kapatmayın)
"CVE exists" - Güvenlik açığı var (kapatılması önerilir)
"built into kernel" - Kernel içinde (kapatılamaz)
```

### 3. Remediation Seçenekleri

#### ✅ Önerilen: Manuel Tek Tek Kapatma (EN GÜVENLİ)

Her modülü tek tek kapatın:

```bash
sudo bash remediation_manual.sh gfs2
sudo bash remediation_manual.sh cifs
sudo bash remediation_manual.sh nfsd
# ... vb
```

**Avantajları:**
- ✅ Maksimum güvenlik
- ✅ Her adımı kontrol edebilirsiniz
- ✅ Hata durumunda tek modül etkilenir
- ✅ Production sistemler için ideal

#### ⚠️ Alternatif: Otomatik Toplu Kapatma (RİSKLİ)

**SADECE test sistemlerinde kullanın!**

```bash
sudo bash remediation.sh
```

**Dikkat:**
- ⚠️ Birden fazla modülü birden kapatır
- ⚠️ Production sistemlerde kullanmayın
- ⚠️ Önce test ortamında deneyin

---

## Hangi Modülleri Kapatmalıyım?

### 🔴 Öncelikli: CVE'si Olan Modüller

Audit çıktısında `<- CVE exists!` yazan modüller:

```bash
# CVE'li modülleri tek tek kapatın:
sudo bash remediation_manual.sh afs
sudo bash remediation_manual.sh ceph
sudo bash remediation_manual.sh cifs
sudo bash remediation_manual.sh exfat
sudo bash remediation_manual.sh gfs2
sudo bash remediation_manual.sh nfs_common
sudo bash remediation_manual.sh nfsd
```

### 🟡 İkincil: Kullanmadığınız Dosya Sistemleri

Eğer şunları kullanmıyorsanız kapatabilirsiniz:
- `btrfs` - Btrfs dosya sistemi
- `jfs` - IBM JFS dosya sistemi
- `udf` - DVD/CD dosya sistemi
- `isofs` - ISO 9660 dosya sistemi (CD-ROM)
- `ntfs3` - Windows NTFS dosya sistemi
- `vboxsf` - VirtualBox paylaşımlı klasörler
- `nfs/nfsd` - Network File System (ağ paylaşımı)

### 🟢 Asla Kapatmayın

Bu modüller **KORUMALIdır:**
- `ext2`, `ext3`, `ext4` - Linux standart dosya sistemleri
- `xfs` - Yaygın Linux dosya sistemi
- `vfat` - FAT32 (EFI boot için gerekli)
- `overlay` - Docker/container'lar için gerekli
- `fuse` - Kullanıcı alanı dosya sistemleri

---

## Örnek İş Akışı

### Senaryo 1: Production Sunucu

```bash
# 1. Audit yapın
sudo bash audit.sh > audit_sonuc.txt

# 2. Sonuçları inceleyin
cat audit_sonuc.txt

# 3. CVE'li ve kullanmadığınız her modül için:
sudo bash remediation_manual.sh gfs2
# Çıktıyı okuyun, onaylayın

sudo bash remediation_manual.sh cifs
# Çıktıyı okuyun, onaylayın

# ... devam edin

# 4. Doğrulama
sudo bash audit.sh

# 5. Yeniden başlatma (isteğe bağlı, ama önerilir)
sudo reboot
```

### Senaryo 2: Test Sistemi

```bash
# 1. Audit yapın
sudo bash audit.sh

# 2. Otomatik remediation (sadece test için!)
sudo bash remediation.sh

# 3. Doğrulama
sudo bash audit.sh

# 4. Test edin
sudo reboot
```

---

## Sorun Giderme

### Sistem Açılmıyorsa

1. Rescue mode'da boot edin
2. Root dosya sistemini mount edin:
   ```bash
   mount /dev/sdXX /mnt
   ```
3. Sorunlu config dosyasını silin:
   ```bash
   rm /mnt/etc/modprobe.d/SORUNLU_MODUL.conf
   ```
4. Initramfs'i yeniden oluşturun:
   ```bash
   chroot /mnt
   update-initramfs -u -k all
   exit
   ```
5. Yeniden başlatın

### Modülü Tekrar Etkinleştirmek

```bash
# Config dosyasını silin
sudo rm /etc/modprobe.d/MODUL_ADI.conf

# Initramfs güncelle
sudo update-initramfs -u -k all

# Modülü yükle
sudo modprobe MODUL_ADI

# Yeniden başlat
sudo reboot
```

---

## Sık Sorulan Sorular

### Hangi remediation scriptini kullanmalıyım?

**Production sistemler için:** `remediation_manual.sh`
**Test sistemler için:** İkisi de olur, ama `remediation_manual.sh` daha güvenli

### "built into kernel" ne demek?

Bu modül kernel'e gömülü, modül olarak yüklenemiyor. Kapatılamaz, bu normal.

### CVE'si olan modülü kapatamıyorsam?

Eğer "built into kernel" ise kapatılamaz. Bu durumda:
- Modülü sadece gerektiğinde kullanın
- Firewall kuralları ile koruyun
- Kernel güncellemelerini takip edin

### Fat modülü CVE'si var ama kapatılamıyor?

Evet, `fat` genelde EFI boot için kernel'e gömülüdür. Bu normal ve kabul edilebilir.

---

## Kontrol Listesi

Remediation yapmadan önce:

- [ ] Audit scriptini çalıştırdım
- [ ] Sonuçları dikkatlice okudum
- [ ] Hangi modüllerin mounted olduğunu kontrol ettim
- [ ] Kapatacağım modüllerin ne olduğunu anladım
- [ ] Test ortamında denedim (production için)
- [ ] Backup aldım / snapshot oluşturdum
- [ ] Fiziksel/konsol erişimim var
- [ ] README.md'yi okudum

---

## Özet

| Durum | Remediation Yöntemi | Güvenlik | Hız |
|-------|-------------------|----------|-----|
| **Production** | `remediation_manual.sh` | ⭐⭐⭐⭐⭐ | 🐢 Yavaş |
| **Test** | `remediation.sh` veya manuel | ⭐⭐⭐ | 🚀 Hızlı |
| **Kritik Sistem** | Sadece `remediation_manual.sh` | ⭐⭐⭐⭐⭐ | 🐢 Yavaş |

**Altın Kural:** Şüphe durumunda **her zaman manuel yöntemi** kullanın!

---

## Ek Bilgi

Detaylı teknik bilgi için [README.md](README.md) dosyasına bakın.

**Yardım için:**
- CIS Benchmark dokümantasyonu
- `man modprobe`
- `man modprobe.d`
