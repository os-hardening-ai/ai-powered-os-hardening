# steps/answer_generator.py
from __future__ import annotations

"""
Project-Specific Answer Generator
---------------------------------
Proje gereksinimlerine uygun formatlanmış çıktı üretir:

ÇIKTI YAPISI:
1. Özet (ne yapılacak?)
2. Gerekçe (neden yapılmalı?)
3. Zero Trust İlişkisi (hangi prensipler?)
4. Risk Etkisi (ne kadar kritik?)
5. Önerilen Adımlar (nasıl yapılacak?)
6. Örnek Komutlar/Konfigürasyonlar (Bash/PowerShell)
7. Standart Referansları (CIS/NIST/ISO maddeleri)
8. Rollback Yaklaşımı (sorun olursa ne yapılacak?)
"""

from typing import Callable, List

from context import RequestContext, PlanStep


LLMCallable = Callable[[str], str]


def _format_plan_steps(steps: List[PlanStep]) -> str:
    """Plan adımlarını prompt'a uygun formata çevirir."""
    if not steps:
        return "- (Plan adımı yok, mantıklı bir akış sen oluştur.)"

    lines: List[str] = []
    for step in steps:
        detail_part = f" - Detay: {step.detail}" if step.detail else ""
        lines.append(f"{step.id}. {step.goal}{detail_part}")
    return "\n".join(lines)


def _build_project_answer_prompt(ctx: RequestContext) -> str:
    """
    Proje gereksinimlerine göre yapılandırılmış answer prompt.
    
    Çıktı Formatı:
    - Gerekçeli açıklamalar
    - Spesifik komut örnekleri
    - ZT prensip eşleştirmeleri
    - Risk ve rollback bilgisi
    """
    os_name = ctx.os or "ubuntu_22_04"
    role = ctx.role or "sysadmin"
    intent = ctx.intent or "generic_qna"
    target_area = ctx.target_area or "general"

    zt_list = ctx.zt_principles or []
    std_list = ctx.standards or []
    
    impact_level = ctx.extra.get("impact_level", "medium")
    rollback_approach = ctx.extra.get("rollback_approach", "Bilinmiyor")

    zt_str = ", ".join(zt_list) if zt_list else "belirtilmedi"
    std_str = "\n".join([f"- {s}" for s in std_list]) if std_list else "- Belirtilmedi"
    
    plan = ctx.plan
    plan_str = _format_plan_steps(plan.steps) if plan else "- (Plan yok, mantıklı akış oluştur.)"

    retrieved_context = ctx.retrieved_context or ""

    # Script türü belirleme (OS'ye göre)
    if "windows" in os_name.lower():
        script_examples = """
**PowerShell Örneği:**
```powershell
# Örnek güvenlik ayarı
Set-ItemProperty -Path "HKLM:\\..." -Name "..." -Value 1
```

**Registry (REG) Örneği:**
```reg
Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\\SOFTWARE\\...]
"SettingName"=dword:00000001
```
"""
    else:  # Linux/Ubuntu
        script_examples = """
**Bash Script Örneği:**
```bash
#!/bin/bash
# Örnek güvenlik ayarı
sudo sed -i 's/^#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

**Ansible Playbook Örneği (opsiyonel):**
```yaml
---
- name: SSH Hardening
  hosts: all
  tasks:
    - name: Disable root login
      lineinfile:
        path: /etc/ssh/sshd_config
        regexp: '^#?PermitRootLogin'
        line: 'PermitRootLogin no'
```
"""

    return f"""
SENİN ROLÜN:
- Siber güvenlik uzmanısın
- Zero Trust odaklı, savunma amaçlı rehberlik sağlıyorsun
- Proje formatına uygun, yapılandırılmış çıktı üretiyorsun

KULLANICI MESAJI:
\"\"\"{ctx.user_question}\"\"\"


BAĞLAM:
- Kullanıcı rolü: {role}
- Intent: {intent}
- Hedef alan: {target_area}
- İşletim sistemi: {os_name}
- Güvenlik seviyesi: {ctx.security_level}
- Zero Trust olgunluk: {ctx.zt_maturity}


ZERO TRUST PRENSİPLERİ:
{zt_str}


STANDART REFERANSLARI:
{std_str}


RİSK SEVİYESİ:
{impact_level}


ROLLBACK YAKLAŞIMI:
{rollback_approach}


İZLENCEK PLAN:
{plan_str}


RAG BAĞLAMI (varsa):
\"\"\"{retrieved_context}\"\"\"


ÇIKTI FORMATI (ZORUNLU):

Türkçe cevap ver. Aşağıdaki yapıyı TAM OLARAK KULLAN:

---

## 📋 ÖZET
[1-2 cümle: Ne yapılacak?]

## 🎯 GEREKÇE
[Neden bu öneri gerekli? Hangi tehditlere karşı koruma sağlıyor?]

## 🔐 ZERO TRUST İLİŞKİSİ
[Bu öneri hangi ZT prensiplerini destekliyor? Örnek:
- **Least Privilege**: Root erişimini kısıtlayarak...
- **Continuous Verification**: Her erişimde kimlik doğrulama...]

## ⚠️ RİSK ETKİSİ
- **Seviye**: {impact_level}
- **Açıklama**: [Bu değişiklik sistem üzerinde nasıl bir etki yaratır?]

## ✅ ÖNERİLEN ADIMLAR

### Adım 1: [Başlık]
[Detaylı açıklama]

### Adım 2: [Başlık]
[Detaylı açıklama]

[Gerektiği kadar adım ekle...]


## 💻 ÖRNEK KOMUTLAR/KONFİGÜRASYONLAR

{script_examples}

**Not:** Yukarıdaki örnekler, gerçek ortamınıza göre uyarlanmalıdır.


## 📚 STANDART REFERANSLARI

{std_str}

Her referansın kısa açıklaması:
[Her standart için 1 cümle açıklama]


## 🔄 ROLLBACK YAKLAŞIMI

{rollback_approach}

**Rollback Komutları:**
[Somut komut örnekleri ver]

---


KURALLAR:
- Yukarıdaki yapıyı TAM OLARAK kullan
- Her bölüm MUTLAKA doldurulmalı
- Komut örnekleri SOMUT ve ÇALIŞIR durumda olmalı
- ZT prensipleriyle ilişkiyi açıkça belirt
- Standart referanslarını madde numarasıyla ver (örn: CIS_Ubuntu_22_04:5.2.5)
- Rollback için pratik komutlar ver
- Saldırı/exploit adımları verme, savunma odaklı ol
- Markdown formatı kullan
""".strip()


def run_project_answer_generator(llm: LLMCallable, ctx: RequestContext) -> RequestContext:
    """
    Proje formatına uygun answer generator.
    
    Çıktı:
    - Yapılandırılmış (Özet, Gerekçe, ZT İlişkisi, Risk, Adımlar, Komutlar, Standartlar, Rollback)
    - Spesifik komut örnekleri
    - CIS/NIST/ISO madde referanslı
    """
    prompt = _build_project_answer_prompt(ctx)

    try:
        raw_answer = llm(prompt)
        draft = raw_answer.strip()
        if not draft:
            raise ValueError("LLM'den boş cevap döndü.")
        ctx.draft_answer = draft
    except Exception:
        # Fallback: Minimal yapılandırılmış cevap
        ctx.draft_answer = f"""
## 📋 ÖZET
Şu anda detaylı teknik cevap üretemedim.

## 🎯 GEREKÇE
Zero Trust yaklaşımında en az ayrıcalık (least privilege), sürekli doğrulama 
(continuous verification) ve ihlal varsayımı (assume breach) kritik öneme sahiptir.

## 🔐 ZERO TRUST İLİŞKİSİ
- **Least Privilege**: Erişimi mümkün olduğunca daralt
- **Continuous Verification**: Kimlik doğrulamayı güçlendir
- **Assume Breach**: Loglama ve izlemeyi aktif tut

## ⚠️ RİSK ETKİSİ
- **Seviye**: {ctx.extra.get('impact_level', 'medium')}
- **Açıklama**: Test ortamında denenmeli

## ✅ ÖNERİLEN ADIMLAR

### Adım 1: Mevcut durumu analiz et
Sistem yapılandırmasını gözden geçir.

### Adım 2: Güvenlik önlemlerini uygula
İlgili standartlara göre sıkılaştırma yap.

## 💻 ÖRNEK KOMUTLAR
Lütfen soruyu daha spesifik hale getirin.

## 📚 STANDART REFERANSLARI
{chr(10).join([f"- {s}" for s in ctx.standards]) if ctx.standards else "- Belirtilmedi"}

## 🔄 ROLLBACK YAKLAŞIMI
{ctx.extra.get('rollback_approach', 'Config dosyalarını yedekleyin.')}
"""

    return ctx


# Backward compatibility
run_answer_generator = run_project_answer_generator