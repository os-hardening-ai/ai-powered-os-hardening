# Parametre Kullanım Tablosu

## Soru Tiplerine Göre Parametre Kullanımı

| Soru Tipi | OS | Role | Security Level | RAG | Açıklama |
|-----------|-----|------|---------------|-----|----------|
| **SIMPLE** (Genel bilgi) | ❌ | ❌ | ❌ | ⚠️ | Basit tanımlar, LLM genel bilgi verir |
| **MEDIUM** (Yapılandırma) | ✅ | ⚠️ | ⚠️ | ✅ | OS önemli, rol kısmen etkili |
| **COMPLEX** (Analiz/Script) | ✅ | ✅ | ✅ | ✅ | Tüm parametreler kullanılır |

### Detaylı Açıklama

#### 1. SIMPLE Sorular
```
Soru: "Firewall nedir?"
Kullanılan: Sadece LLM
Kullanılmayan: OS, Role, Security Level
RAG: Kullanılmaz (genel bilgi LLM'de zaten var)

Cevap: "Firewall, ağ trafiğini kontrol eden güvenlik sistemidir..."
```

**Neden rol/security_level kullanılmaz?**
- Genel tanımlar tüm roller için aynı
- Security level fark yaratmaz (tanım sabit)
- LLM'in kendi bilgisi yeterli

#### 2. MEDIUM Sorular
```
Soru: "SSH nasıl yapılandırılır?"
Kullanılan: OS (Ubuntu/Windows farklı), RAG
Kısmen Etkili: Role (sysadmin vs developer farklı detay)
               Security Level (high → daha katı)

Cevap: "Ubuntu 22.04'te SSH yapılandırması:
        1. /etc/ssh/sshd_config düzenle
        2. PermitRootLogin no (balanced için)
        ..."
```

**Neden OS önemli ama role kısmen?**
- OS kesinlikle gerekli (farklı komutlar)
- Role detay seviyesini etkiler
- Security level kuralların katılığını belirler

#### 3. COMPLEX Sorular
```
Soru: "Full hardening script yaz"
Kullanılan: TÜM PARAMETRELER
- OS: Ubuntu 22.04 → apt, systemd
- Role: sysadmin → detaylı izleme, audit
- Security Level: strict → maksimum sıkılaştırma
- RAG: Mevcut best practice'ler

Cevap: [Detaylı, role-specific, security-level aware script]
```

**Neden hepsi gerekli?**
- Script OS'e spesifik olmalı
- Role belirsiz görevleri belirler
- Security level hangi kuralların uygulanacağını etkiler
- RAG en güncel best practice'leri sağlar

---

## ConfigManager Kullanımı

### İlk Kurulum (Tek Seferlik)
```python
manager = ConfigManager()
config = manager.get_config()  # İlk kullanımda kurulum yapılır
```

Kullanıcıya sorulur:
1. ✅ **Role** → Bir kez seçilir, kaydedilir
2. ✅ **Security Level** → Bir kez seçilir, kaydedilir
3. ✅ **OS** → Otomatik tespit edilir

### Sonraki Kullanımlar
```python
# Kullanıcı sadece soru sorar
question = "SSH nedir?"

# Config otomatik yüklenir
manager = ConfigManager()
config = manager.get_config()  # Kayıtlı değerleri yükler

# API'ye gönder (ama simple soruda kullanılmaz!)
```

---

## Akıllı Optimizasyon

Pipeline otomatik optimizasyon yapar:

```python
# SIMPLE soru
"Firewall nedir?"
→ Pipeline: "Bu SIMPLE, role/security_level ignore et"
→ Model: Küçük model (Groq Llama 8B - BEDAVA)
→ Maliyet: $0
→ Süre: <1 saniye

# COMPLEX soru
"Full hardening script yaz (role=sysadmin, strict)"
→ Pipeline: "Bu COMPLEX, tüm parametreleri kullan + RAG"
→ Model: Büyük model (GPT-4o)
→ Maliyet: $0.05
→ Süre: 5-10 saniye
```

---

## Kullanıcı Deneyimi

### Senaryo 1: Basit Soru
```bash
$ python examples/simple_chat.py

💬 Soru: Firewall nedir?

⏳ Cevap hazırlanıyor...

📝 CEVAP:
Firewall, ağ trafiğini kontrol eden güvenlik sistemidir...

# Role/Security Level kullanılmadı, ama kullanıcı farkında değil!
```

### Senaryo 2: Karmaşık Soru
```bash
💬 Soru: Ubuntu 22.04 için SSH hardening scripti yaz

⏳ Cevap hazırlanıyor...

📝 CEVAP:
Rolünüze (SysAdmin) ve güvenlik seviyenize (Balanced) uygun script:

#!/bin/bash
# SSH Hardening - Ubuntu 22.04
# Security Level: Balanced
# ...

📚 KAYNAKLAR:
1. CIS Ubuntu 22.04 Benchmark (Skor: 0.94)
   Bölüm: SSH Configuration
```

---

## Sonuç

✅ **Kullanıcı perspektifi:**
- Sadece soru sorar
- İlk seferde rol/security level seçer (kolay)
- Sonra sadece soru yazar

✅ **Sistem perspektifi:**
- SIMPLE: Parametreleri ignore eder (maliyet düşür)
- MEDIUM: Kısmen kullanır
- COMPLEX: Hepsini kullanır

✅ **Maliyet optimizasyonu:**
- Basit sorular: BEDAVA (Groq)
- Karmaşık: Gerektiğinde GPT-4o

Bu tasarım **kullanıcı dostu** ve **maliyet-etkin**!
