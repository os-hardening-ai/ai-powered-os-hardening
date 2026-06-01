#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Türkçe intent eğitim verisini domain-uygun örneklerle genişletir.

`data/intent_training_dataset.csv` (text,intent) dosyasına 7 kategoriye dengeli,
güvenlik-domain varlıklarıyla (OS / servis / konu / araç / port) çeşitlendirilmiş
~1000 YENİ Türkçe örnek ekler. Mevcut satırlara ve kendi içinde DEDUP yapar.

Etiketler (mevcut şema): info_request | action_request | greeting | farewell |
thanks | help | out_of_scope

Kullanım:  python scripts/expand_intent_dataset.py            # üret + ekle
           python scripts/expand_intent_dataset.py --dry-run  # sadece say, yazma

NOT: Eklemeden sonra ML modeli YENİDEN EĞİTİLMELİ (intent_model.joblib +
intent_vectorizer.joblib), aksi halde yeni veri çalışan modele yansımaz.
"""
from __future__ import annotations
import csv
import random
import sys
from pathlib import Path

# Seed --seed N ile değişir → aynı script 5x farklı seed ile çalıştırılınca her run
# YENİ örnekler üretir (dedup CSV'ye karşı). Varsayılan 42 (tekrarlanabilir).
_SEED = 42
if "--seed" in sys.argv:
    try:
        _SEED = int(sys.argv[sys.argv.index("--seed") + 1])
    except (IndexError, ValueError):
        pass
random.seed(_SEED)

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "intent_training_dataset.csv"

# ── Domain varlıkları (OS-AİLESİ-UYUMLU) ─────────────────────────────────────
# Anlamsız kombinasyonları (örn. "Windows'ta sudo/cramfs") önlemek için OS aileleri +
# servis/konu uyumluluğu: linux-only / windows-only / her ikisi (cross) ayrılır.
LINUX_OS = ["Ubuntu 24.04", "Ubuntu 22.04", "Debian 12", "CentOS 9", "RHEL 9",
            "Rocky Linux 9", "AlmaLinux 9", "openSUSE", "Fedora 40"]
WIN_OS = ["Windows Server 2025", "Windows 11"]
OS = LINUX_OS + WIN_OS

LINUX_SVC = ["SSH", "sshd", "UFW", "iptables", "nftables", "firewalld", "SELinux",
             "AppArmor", "auditd", "fail2ban", "PAM", "sudo", "cron", "rsyslog", "systemd", "NFS"]
WIN_SVC = ["RDP", "WinRM", "BitLocker", "Windows Defender", "AppLocker"]
CROSS_SVC = ["Docker", "NGINX", "Apache", "PostgreSQL", "MySQL", "Redis", "Samba", "Kerberos"]
ALL_SVC = LINUX_SVC + WIN_SVC + CROSS_SVC

LINUX_TOPIC = ["PermitRootLogin ayarı", "SSH portunu değiştirme", "kernel sıkılaştırma",
               "sysctl ayarları", "umask", "cramfs modülünü kapatma", "X11 forwarding kapatma",
               "AllowUsers/AllowGroups", "core dump kapatma", "boş parolaları engelleme"]
WIN_TOPIC = ["GPO ayarları", "RDP NLA", "BitLocker şifreleme", "AppLocker politikası",
             "Windows Defender yapılandırması", "hesap kilitleme politikası"]
CROSS_TOPIC = ["parola politikası", "MFA", "anahtar tabanlı kimlik doğrulama", "dosya izinleri",
               "log rotation", "TLS/SSL cipher seçimi", "parola yaşlandırma", "audit kuralları",
               "idle timeout", "banner ekleme", "USB depolama engelleme"]
ALL_TOPIC = LINUX_TOPIC + WIN_TOPIC + CROSS_TOPIC


def svc_for(os):
    return (LINUX_SVC if os in LINUX_OS else WIN_SVC) + CROSS_SVC


def topic_for(os):
    return (LINUX_TOPIC if os in LINUX_OS else WIN_TOPIC) + CROSS_TOPIC


def fmt_for(os):
    base = ["bash scripti"] if os in LINUX_OS else ["PowerShell scripti"]
    return base + ["Ansible playbook'u", "script", "yapılandırma"]
CONCEPT = ["zero trust", "least privilege", "defense in depth", "mikro segmentasyon",
           "NIST 800-207", "CIS Benchmark", "ISO 27001", "saldırı yüzeyi", "attack surface",
           "hardening", "tehdit modelleme", "RBAC", "ayrıcalık yükseltme", "yan hareket",
           "assume breach", "sürekli doğrulama", "güvenlik denetimi"]
FMT = ["bash scripti", "PowerShell scripti", "Ansible playbook'u", "script", "yapılandırma"]
LEVEL = ["temel", "dengeli", "katı", "CIS Level 1", "CIS Level 2"]


def cap(s: str) -> str:
    return s[0].upper() + s[1:] if s else s


# ── Kategori üreticileri (her biri bir cümle listesi döndürür) ───────────────
def gen_info():
    t = []
    for os in OS:
        for s in svc_for(os):
            t += [f"{os} üzerinde {s} nasıl sıkılaştırılır?",
                  f"{os}'te {s} güvenliğini nasıl artırırım?",
                  f"{s} için {os} üzerinde en iyi güvenlik pratikleri nelerdir?"]
    for s in ALL_SVC:
        t += [f"{s} nedir ve neden güvenlik açısından önemlidir?",
              f"{s} loglarını nasıl izlerim?",
              f"CIS Benchmark {s} için ne öneriyor?",
              f"{s} için hangi ayarlar güvenliği artırır?",
              f"{s} yapılandırmasında en sık yapılan güvenlik hataları nelerdir?",
              f"{s} ile ilgili bilinen güvenlik açıkları nelerdir?"]
    for tp in ALL_TOPIC:
        t += [f"{cap(tp)} neden gereklidir?",
              f"{cap(tp)} nasıl yapılır?",
              f"{cap(tp)} güvenliğe nasıl katkı sağlar?",
              f"{cap(tp)} hangi CIS kuralıyla ilişkilidir?"]
    for c in CONCEPT:
        t += [f"{cap(c)} ne demektir?",
              f"{cap(c)} prensibini açıkla",
              f"{cap(c)} neden önemlidir?",
              f"{cap(c)} işletim sistemi sıkılaştırmasıyla nasıl ilişkilidir?"]
    return t


def gen_action():
    t = []
    for os in OS:
        for s in svc_for(os):
            t += [f"{os} için {s} sıkılaştırma scripti yaz",
                  f"{os}'te {s} güvenliğini uygulayan {random.choice(fmt_for(os))} üret",
                  f"{os} {s} hardening {random.choice(fmt_for(os))} hazırla"]
    for os in OS:
        for tp in topic_for(os):
            t += [f"{os} için {tp} uygulayan script oluştur",
                  f"{os}'te {tp} ayarını yapan {random.choice(fmt_for(os))} yaz"]
    for s in ALL_SVC:
        t += [f"{s} için CIS uyumlu {random.choice(FMT)} üret",
              f"{s} {random.choice(LEVEL)} sıkılaştırma scripti ver"]
    return t


def gen_greeting():
    base = ["merhaba", "selam", "selamlar", "merhabalar", "günaydın", "iyi günler",
            "iyi akşamlar", "iyi geceler", "naber", "nasılsın", "ne haber", "nasıl gidiyor",
            "hey", "selam dostum", "iyi sabahlar", "selamün aleyküm", "aleyküm selam",
            "hoş geldin", "hoşgeldin", "slm", "mrb", "mrhb", "sa", "nbr", "naptın",
            "ne var ne yok", "hayırlı sabahlar", "hayırlı günler", "selamcım", "merhabaa"]
    follow = ["", "", "", "yardımcı olur musun", "bir sorum olacak", "müsait misin",
              "nasılsın", "bir konuda yardım lazım", "vakit var mı", "beni duyuyor musun",
              "bugün nasılsın"]
    out = list(base)
    for b in base:
        for f in follow:
            out.append(f"{b} {f}".strip() if f else b)
    return out


def gen_farewell():
    base = ["görüşürüz", "hoşça kal", "hoşçakal", "hoşçakalın", "kendine iyi bak",
            "kendine dikkat et", "güle güle", "elveda", "bay bay", "görüşmek üzere",
            "iyi çalışmalar", "iyi günler dilerim", "sonra görüşürüz", "sonra konuşuruz",
            "kapatıyorum artık", "çıkıyorum artık", "hadi bana müsaade", "bana izin",
            "selametle", "bb", "grşrz", "sağlıcakla kal", "allahaısmarladık",
            "tamam görüşürüz", "hadi görüşürüz"]
    suffix = ["", "", "kolay gelsin", "iyi çalışmalar", "teşekkürler", "iyi günler"]
    out = []
    for b in base:
        for s in suffix:
            out.append(f"{b} {s}".strip() if s else b)
    return out


def gen_thanks():
    base = ["teşekkürler", "teşekkür ederim", "çok teşekkür ederim", "sağ ol", "sağol",
            "sağ olun", "çok sağ ol", "eline sağlık", "ellerine sağlık", "minnettarım",
            "yardımın için teşekkürler", "sağolasın", "eyvallah", "harika teşekkürler",
            "süper teşekkürler", "tşk", "tsk", "tşkler", "tşk ederim", "çok makbule geçti",
            "emeğine sağlık", "valla sağ ol", "mükemmel teşekkür ederim", "helal olsun",
            "allah razı olsun", "eyw", "teşekkür ederim dostum", "binlerce teşekkür"]
    suffix = ["", "", "", "çok işime yaradı", "çok yardımcı oldun", "harikaydı",
              "tam istediğim buydu", "süpersin"]
    out = []
    for b in base:
        for s in suffix:
            out.append(f"{b} {s}".strip() if s else b)
    return out


def gen_help():
    return ["ne yapabilirsin?", "nasıl yardımcı olabilirsin?", "hangi konularda yardım edersin?",
            "bana ne konuda destek olursun?", "yeteneklerin neler?", "nasıl kullanılır?",
            "hangi komutları destekliyorsun?", "bana yol gösterir misin?",
            "ne tür sorular sorabilirim?", "bu sistem ne işe yarıyor?", "sen kimsin ne yaparsın?",
            "nasıl başlarım?", "bana örnek bir soru verir misin?", "neler yapabildiğini anlat",
            "hangi işletim sistemlerini destekliyorsun?", "kullanım kılavuzu var mı?",
            "bana nasıl faydan olur?", "hangi güvenlik standartlarını biliyorsun?",
            "ne için tasarlandın?", "özelliklerin neler?", "yardım menüsü nerede?",
            "hangi script formatlarını üretebilirsin?", "beni yönlendirir misin?",
            "ne sorabileceğimi bilmiyorum yardım et"]


def gen_oos():
    cities = ["İstanbul", "Ankara", "İzmir", "Bursa", "Antalya", "Paris", "Tokyo", "Londra"]
    foods = ["pizza", "makarna", "köfte", "mantı", "lahmacun", "kek", "çorba"]
    t = []
    for c in cities:
        t += [f"{c} hava durumu nasıl?", f"{c} nüfusu kaç?", f"{c}'da gezilecek yerler neler?"]
    for f in foods:
        t += [f"{f} tarifi verir misin?", f"nasıl {f} yapılır?"]
    for a in range(2, 10):
        b = random.randint(2, 12)
        t += [f"{a} çarpı {b} kaç eder?", f"{a} artı {b} kaç yapar?"]
    t += ["bugün hava nasıl?", "en iyi film önerisi nedir?", "futbol maçı kaçta başlıyor?",
          "en yakın restoran nerede?", "tatil için nereyi önerirsin?", "bana bir şiir yaz",
          "bana bir fıkra anlat", "dolar kuru kaç oldu?", "yarın ne giysem?",
          "kilo vermek için ne yapmalıyım?", "araba almak istiyorum ne önerirsin?",
          "matematik ödevime yardım eder misin?", "en sevdiğin renk ne?", "kahve nasıl yapılır?",
          "Türkiye'nin başkenti neresi?", "bir kitap önerir misin?", "namaz vakitleri ne zaman?",
          "burç yorumu yapar mısın?", "en yakın eczane nerede?", "uçak bileti nasıl alınır?",
          "evcil hayvan bakımı hakkında bilgi ver", "hangi diziyi izlemeliyim?",
          "doğum günü hediyesi ne alsam?", "ingilizce nasıl öğrenirim?"]
    return t


GENERATORS = {
    "info_request": (gen_info, 300),
    "action_request": (gen_action, 300),
    "out_of_scope": (gen_oos, 160),
    "help": (gen_help, 110),
    "greeting": (gen_greeting, 250),
    "thanks": (gen_thanks, 200),
    "farewell": (gen_farewell, 150),
}


def main():
    dry = "--dry-run" in sys.argv
    existing = set()
    if CSV_PATH.exists():
        with open(CSV_PATH, encoding="utf-8") as f:
            for row in csv.reader(f):
                if len(row) >= 2:
                    existing.add(row[0].strip().lower())

    new_rows = []
    seen = set(existing)
    per_cat = {}
    for label, (gen, target) in GENERATORS.items():
        pool = list(dict.fromkeys(gen()))  # üretim-içi sıra-koruyan dedup
        random.shuffle(pool)
        added = 0
        for text in pool:
            key = text.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            new_rows.append((text, label))
            added += 1
            if added >= target:
                break
        per_cat[label] = added

    random.shuffle(new_rows)
    print(f"Mevcut: {len(existing)} | Üretilen YENİ (dedup'lı): {len(new_rows)}")
    for k, v in per_cat.items():
        print(f"  {k:16s} +{v}")

    if dry:
        print("[dry-run] yazılmadı.")
        return
    with open(CSV_PATH, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        for text, label in new_rows:
            w.writerow([text, label])
    print(f"→ {CSV_PATH} güncellendi (+{len(new_rows)} satır).")


if __name__ == "__main__":
    main()
