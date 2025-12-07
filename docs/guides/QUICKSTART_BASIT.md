# Basit Kullanim Kilavuzu

## Sistem Nedir?

AI tabanli isletim sistemi guvenlik sikilaştirma asistani.

**Ne Yapar:**
- SSH, RDP, Firewall hardening sorularina cevap verir
- Guvenlik scriptleri olusturur
- CIS Benchmarks'e uygun oneriler sunar
- Zero Trust prensiplerini uygular

---

## 1. Kurulum (İlk Kez)

### Adim 1: Gereksinimler
```bash
# Python 3.12+ gerekli
python --version

# Git gerekli
git --version
```

### Adim 2: Projeyi İndir
```bash
cd C:\Users\<KULLANICI_ADIN>\Documents
git clone <REPO_URL>
cd ai-powered-os-hardening
```

### Adim 3: API Anahtarlarini Ayarla
```bash
# .env dosyasi olustur
cp llm/.env.example llm/.env

# Notepad ile ac
notepad llm/.env
```

**Gerekli API Anahtarlari:**
```
GROQ_API_KEY=gsk_xxx...  # ZORUNLU (ucretsiz: groq.com)
OPENAI_API_KEY=sk-xxx... # OPSIYONEL
```

### Adim 4: Paketleri Yukle
```bash
pip install -r requirements.txt
```

**Hata alirsan:** Windows dosya kilitleme sorunu olabilir, bilgisayari yeniden baslat.

---

## 2. Sistemi Baslat

### API Server'i Baslat
```bash
python main.py
```

**Basarili olursa:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Tarayicida ac:**
```
http://localhost:8000/docs
```

Swagger UI'da tum endpoint'leri gorebilirsin.

---

## 3. Nasil Kullanilir?

### Yontem 1: Swagger UI (En Kolay)

1. Tarayicida ac: `http://localhost:8000/docs`
2. `/api/chat` endpoint'ini bul
3. "Try it out" butonuna tikla
4. Soru yaz, "Execute" tikla

**Ornek Soru:**
```json
{
  "question": "Ubuntu 22.04 SSH hardening scripti olustur",
  "os": "ubuntu_22_04",
  "role": "sysadmin",
  "security_level": "balanced"
}
```

### Yontem 2: cURL (Terminal)

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "SSH hardening best practices?",
    "os": "ubuntu_22_04",
    "security_level": "balanced"
  }'
```

### Yontem 3: Python Script

```python
import requests

response = requests.post(
    "http://localhost:8000/api/chat",
    json={
        "question": "Ubuntu SSH port nasil degistirilir?",
        "os": "ubuntu_22_04"
    }
)

print(response.json()["answer"])
```

---

## 4. Ornek Sorular

### Basit Sohbet
```
Soru: "Merhaba"
Cevap: Pattern-based hizli yanit (0ms)
```

### Bilgi Sorusu (Generic)
```
Soru: "SSH nedir?"
Cevap: Genel tanim (RAG kullanilmaz, hizli)
```

### Bilgi Sorusu (Spesifik)
```
Soru: "Ubuntu 22.04'te SSH port nasil degistirilir?"
Cevap: CIS Benchmark referansli detayli aciklama (RAG kullanilir)
```

### Script Olusturma
```
Soru: "Ubuntu 22.04 icin SSH hardening scripti olustur"
Cevap: Bash script + ZT prensipleri + Rollback stratejisi
```

### Kapsamdisi Soru
```
Soru: "Bugun hava nasil?"
Cevap: "Ben sadece guvenlik konularinda yardimci olabilirim..."
```

### Saldiri Amacli Soru
```
Soru: "Brute force nasil yapilir?"
Cevap: REDDEDILIR (guvenlik uyarisi)
```

---

## 5. Test Etme

### Otomatik Testler Calistir

```bash
# Tum testleri calistir (40+ test case)
python -m llm.eval.pipeline_evaluator

# Sadece smalltalk testleri
python -m llm.eval.pipeline_evaluator --tags smalltalk

# Sadece info testleri
python -m llm.eval.pipeline_evaluator --tags info

# Debug mode ile
python -m llm.eval.pipeline_evaluator --debug

# Sonuclari dosyaya kaydet
python -m llm.eval.pipeline_evaluator --save results.json
```

**Basarili Test Ciktisi:**
```
PIPELINE EVALUATION
======================================================================
Total test cases: 40
======================================================================

RESULTS
======================================================================

Overall:
  Total Tests:    40
  Passed:         38 (95.0%)
  Failed:         2
  Errors:         0

Accuracy by Component:
  Intent Detection:    97.5%
  Layer Routing:       95.0%
  Safety Classification: 100.0%

Performance:
  Avg Latency:    1250ms
  Total Cost:     $0.0120
  Avg Cost/Query: $0.000300

SUCCESS: Accuracy 95.0%
```

---

## 6. Sorun Giderme

### Hata: "GROQ_API_KEY not found"
**Cozum:** `llm/.env` dosyasini kontrol et, API anahtarini ekle.

### Hata: "Port 8000 already in use"
**Cozum:** Baska bir uygulamayi kapat veya farkli port kullan:
```bash
uvicorn main:app --port 8001
```

### Hata: "Could not install packages (WinError 5)"
**Cozum:** Bilgisayari yeniden baslat, tekrar dene.

### Hata: "Pipeline error: ..."
**Cozum:** `--debug` modu ile calistir, detayli hata goster:
```bash
python main.py --debug
```

---

## 7. Performans Metrikleri

### Ortalama Süreler
- Smalltalk (selam, tesekkur): <1 saniye
- Kapsam disi red (hava durumu): <1 saniye
- Basit bilgi (SSH nedir?): 1-2 saniye
- Detayli bilgi (OS-spesifik): 2-3 saniye
- Script olusturma: 4-6 saniye

### Ortalama Maliyetler
- Smalltalk: $0.0001
- Kapsam disi: $0.0001
- Basit bilgi: $0.0002
- Detayli bilgi: $0.0015
- Script olusturma: $0.0041

**Gunluk kullanim (100 soru):**
- Maliyet: ~$0.03 (3 cent)
- Sure: ~3 dakika (toplam LLM suresi)

---

## 8. Pipeline Katmanlari (Nasil Calisir?)

```
KULLANICI SORUSU
      |
      v
[1] SAFETY CHECK (Guvenlik Kontrolu)
      |
      +---> Saldiri amacli mi? ---> EVET ---> REDDET
      |
      v HAYIR (Guvenli)
      |
[2] INTENT DETECTION (Amaç Tespit)
      |
      +---> Selamlaşma mi? ------> [3A] Pattern Response (0ms)
      |
      +---> Kapsam disi mi? ------> [OUT_OF_SCOPE] Red mesaji
      |
      +---> Bilgi sorusu mu? -----> [3B] Info Pipeline (RAG + LLM)
      |
      +---> Script istegi mi? ----> [3C] Action Pipeline (ZT + Script + Validation)
      |
      v
CEVAP DONDUR
```

**Ornekler:**

1. "Merhaba" → 1→2→3A (pattern)
2. "Hava durumu" → 1→2→OUT_OF_SCOPE
3. "SSH nedir?" → 1→2→3B (info, no RAG)
4. "Ubuntu SSH port" → 1→2→3B (info, with RAG)
5. "Script olustur" → 1→2→3C (action)
6. "Brute force" → 1→REJECT (unsafe)

---

## 9. API Response Yapisi

```json
{
  "answer": "SSH hardening icin...",
  "intent": "info_request",
  "safety_category": "safe_defensive",
  "layer_path": "1->2->3B->4",
  "rag_sources": [
    {
      "id": "source_1",
      "score": 0.89,
      "source": "CIS_Ubuntu_24.04_Benchmark",
      "section": "5.2.3 SSH Configuration"
    }
  ],
  "stats": {
    "total_time_s": 2.45,
    "layer_path": "1->2->3B->4"
  },
  "request_id": "req_abc123",
  "estimated_cost": 0.0015
}
```

**Onemli Alanlar:**
- `answer`: LLM cevabi
- `intent`: Tespit edilen amac (info_request, action_request, vb.)
- `safety_category`: Guvenlik kategorisi
- `layer_path`: Hangi katmanlardan gecti (debug icin)
- `rag_sources`: RAG kaynaklari (CIS Benchmark referanslari)
- `estimated_cost`: Tahmini maliyet ($)

---

## 10. Gelismis Kullanim

### Rollback Stratejisi Almak
Script olustururken otomatik gelir:

```
Soru: "Ubuntu 22.04 SSH hardening scripti olustur"

Cevap:
  - Bash script (idempotent, hata kontrollu)
  - ZT Prensipleri: least_privilege, continuous_verification
  - CIS Standartlari: CIS_Ubuntu_22_04:5.2.5, 5.2.10
  - ROLLBACK: sudo cp /etc/ssh/sshd_config.bak /etc/ssh/sshd_config
```

### Session Context Kullanimi
Bir kez belirt, sonra hatirlaniyor:

```
1. Soru: "Ubuntu 22.04 SSH hardening"
   → OS kaydedildi: ubuntu_22_04

2. Soru: "Simdi firewall yapilandirmasi"
   → OS hatirlanir, tekrar belirtmene gerek yok
```

### Farkli Guvenlik Seviyeleri

```json
{
  "question": "SSH hardening",
  "security_level": "minimal"   // Temel oneriler
}

{
  "question": "SSH hardening",
  "security_level": "balanced"  // Dengeli (DEFAULT)
}

{
  "question": "SSH hardening",
  "security_level": "strict"    // Maksimum guvenlik
}
```

---

## 11. SSS (Sik Sorulan Sorular)

**S: Hangi dilleri destekliyor?**
C: Turkce ve Ingilizce.

**S: Internet baglantisi gerekli mi?**
C: Evet, LLM API'lerine baglanmak icin.

**S: Ucretsiz mi?**
C: Groq API ucretsiz (gunluk 14,400 istek limiti).

**S: Cevaplar ne kadar dogru?**
C: CIS Benchmarks'e dayali, %90+ dogruluk.

**S: Script'ler guvenli mi?**
C: Evet, tehlikeli komutlar (rm -rf /, vb.) validation layer'da engelleniyor.

**S: RAG nedir?**
C: Retrieval-Augmented Generation. CIS Benchmark dokumanllarindan ilgili bilgileri bulup LLM'e verir.

**S: ZT nedir?**
C: Zero Trust (Sifir Guven) - Modern guvenlik mimarisi.

---

## 12. Daha Fazla Bilgi

**Detayli Dokumantasyon:**
- [LLM_PIPELINE_FLOW.md](LLM_PIPELINE_FLOW.md) - Pipeline nasil calisir?
- [API.md](API.md) - API dokumantasyonu
- [STEPS_TO_LAYERS_MIGRATION.md](STEPS_TO_LAYERS_MIGRATION.md) - Mimari gelistirme

**Test ve Gelistirme:**
- [LLM_IMPROVEMENTS_ANALYSIS.md](LLM_IMPROVEMENTS_ANALYSIS.md) - Gelecek iyilestirmeler

**Kod:**
- `llm/pipeline_v2.py` - Ana pipeline
- `llm/layers/` - Katman implementasyonlari
- `llm/eval/` - Test framework

---

## Ozet

**3 Adimda Baslat:**
1. API anahtarini ekle (`llm/.env`)
2. `python main.py` calistir
3. Tarayicida `http://localhost:8000/docs` ac

**3 Soru Turu:**
1. Bilgi: "SSH nedir?"
2. Nasil yapilir: "SSH port degistir"
3. Script: "SSH hardening scripti olustur"

**Basarilar!**
