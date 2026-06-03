"""
A1 ABLATION + A3 genişletilmiş soru seti runner.

RAG bileşenlerinin (Hybrid / MMR / QueryPlan) RETRIEVAL katkısını izole ölçer:
baseline → +hybrid → +mmr → +queryplan → full. Metrik: avg chunks, avg max retrieval score,
avg latency (config başına). Generation/judge YOK → hafif (yalnız retrieval + queryplan LLM).

Soru seti A3 ile genişletildi (7→18, çoklu OS + kategori) → istatistiksel güç.
Çalıştırma:  python -m evaluation.run_ablation
"""
from __future__ import annotations
import json
from pathlib import Path

# A3 — genişletilmiş ablation/değerlendirme soru seti (Ubuntu + Win11, çoklu kategori).
QUESTIONS = [
    "Ubuntu 24.04'te SSH sıkılaştırma nasıl yapılır?",
    "SSH PermitRootLogin nasıl devre dışı bırakılır?",
    "SSH MaxAuthTries değeri ne olmalı?",
    "CIS Benchmark Level 1 kernel modülü kuralları nelerdir?",
    "cramfs ve usb-storage modülleri nasıl devre dışı bırakılır?",
    "Dosya sistemi izinleri nasıl güvenli hale getirilir?",
    "/tmp için nodev,nosuid,noexec nasıl uygulanır?",
    "UFW güvenlik duvarı yapılandırması nasıl yapılır?",
    "iptables ile varsayılan deny politikası nasıl kurulur?",
    "PAM parola politikası nasıl ayarlanır?",
    "Hesap kilitleme (faillock) nasıl yapılandırılır?",
    "Audit logging (auditd) nasıl etkinleştirilir?",
    "auditd ile zaman değişikliği kuralı nasıl eklenir?",
    "Cron job güvenliği nasıl sağlanır?",
    "sysctl ile ağ kernel parametreleri nasıl sıkılaştırılır?",
    "Windows 11'de SMBv1 nasıl devre dışı bırakılır?",
    "Windows 11'de hesap kilitleme eşiği nasıl ayarlanır?",
    "Windows 11'de Windows Defender nasıl zorunlu kılınır?",
]


def main():
    from evaluation import force_utf8_output
    force_utf8_output()
    import logging
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    from evaluation.ablation_study import AblationStudy
    from llm.clients import get_llm_clients

    small, _ = get_llm_clients()
    study = AblationStudy(llm_fn=small)
    print(f"A1 ABLATION — {len(QUESTIONS)} soru × 5 config (baseline→+hybrid→+mmr→+queryplan→full)\n")
    reports = study.run(questions=QUESTIONS)
    AblationStudy.print_report(reports)

    out = Path("evaluation/results"); out.mkdir(parents=True, exist_ok=True)
    payload = {r.config_name: r.summary() for r in reports}
    (out / "ablation_results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Sonuç: {out/'ablation_results.json'}")


if __name__ == "__main__":
    main()
