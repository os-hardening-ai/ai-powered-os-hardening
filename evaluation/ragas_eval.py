"""
STANDART OBJEKTİF DEĞERLENDİRME — RAGAS (RAG'in de-facto akademik değerlendirme çerçevesi).

Öznel kullanıcı anketi YERİNE evrensel standart metriklerle ölçüm (insan gerektirmez, LLM-judge):
  - faithfulness      : cevaptaki iddiaların bağlamca desteklenme oranı (= groundedness)
  - answer_relevancy  : cevap soruyu ne kadar karşılıyor
  - context_precision : çekilen chunk'ların soruyla alaka oranı (RETRIEVAL kalitesi)
  - context_recall    : bağlam cevabı üretmeye yetiyor mu (RETRIEVAL kapsama)

Bu, öneri formundaki şu maddeleri OBJEKTİF kapatır:
  - İP-3 "≥%80 semantic retrieval" → context_precision/recall (etiketsiz, standart)
  - İP-5 "halüsinasyon <%10" → faithfulness (≥0.90 hedef)
  - H1 destekleme kanıtı → tüm metrikler RAG bağlamıyla ölçülür

Gerçek pipeline koşulur (RAGContextBuilder retrieve + GROUNDING_DIRECTIVE'li üretim), sonra
RAGASEvaluator skorlar. Genişletilmiş soru seti (çoklu OS + kategori) istatistiksel güç için.

Çalıştırma:  LLM_PROVIDER=novita python -m evaluation.ragas_eval
Çıktı:       evaluation/results/ragas_report.md + ragas_results.json
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import List, Tuple

# ── Genişletilmiş soru seti — çoklu OS + kategori (dar VE geniş; istatistiksel güç) ──
# (question, os_version). İP senaryolarından + ek dar/spesifik sorulardan derlendi.
EVAL_QUESTIONS: List[Tuple[str, str]] = [
    # — Ubuntu — dar/spesifik (RAG'in güçlü olduğu) —
    ("SSH için PermitRootLogin nasıl devre dışı bırakılır", "ubuntu_24_04"),
    ("SSH MaxAuthTries değeri ne olmalı ve neden", "ubuntu_24_04"),
    ("Parola minimum uzunluğu ve karmaşıklığı nasıl zorunlu kılınır", "ubuntu_24_04"),
    ("PAM ile hesap kilitleme (faillock) nasıl yapılandırılır", "ubuntu_24_04"),
    ("auditd ile zaman değişikliklerini izleyen kural nasıl eklenir", "ubuntu_24_04"),
    ("UFW ile varsayılan deny politikası nasıl ayarlanır", "ubuntu_24_04"),
    ("cramfs dosya sistemi modülü nasıl devre dışı bırakılır", "ubuntu_24_04"),
    ("sysctl ile IP forwarding nasıl kapatılır", "ubuntu_24_04"),
    ("Idle timeout (TMOUT) nasıl ayarlanır", "ubuntu_24_04"),
    ("sshd için izinli şifreleme algoritmaları (Ciphers) nasıl sınırlandırılır", "ubuntu_24_04"),
    ("/tmp için nodev,nosuid,noexec mount seçenekleri nasıl uygulanır", "ubuntu_24_04"),
    ("Gereksiz servislerin (ör. avahi) durdurulması nasıl yapılır", "ubuntu_24_04"),
    # — Ubuntu — geniş/çok-alanlı (groundedness'in zorlandığı) —
    ("SSH sunucusunu kapsamlı şekilde sıkılaştır", "ubuntu_24_04"),
    ("Parola politikasını ve PAM kurallarını güçlendir", "ubuntu_24_04"),
    ("Denetim (audit) ve sistem bütünlüğü kurallarını uygula", "ubuntu_24_04"),
    ("Ağ ve kernel parametre güvenliğini yapılandır", "ubuntu_24_04"),
    ("Tam sistem sıkılaştırması yap (çok alanlı)", "ubuntu_24_04"),
    # — Windows 11 — dar/spesifik —
    ("Windows 11'de parola geçmişi (password history) nasıl zorlanır", "windows_11"),
    ("Windows 11'de hesap kilitleme eşiği nasıl ayarlanır", "windows_11"),
    ("Windows 11'de SMBv1 nasıl devre dışı bırakılır", "windows_11"),
    ("Windows 11'de Windows Defender gerçek zamanlı koruma nasıl zorunlu kılınır", "windows_11"),
    ("Windows 11'de denetim politikası (audit policy) oturum açma olayları için nasıl ayarlanır", "windows_11"),
    ("Windows 11'de UAC (Kullanıcı Hesabı Denetimi) en yüksek seviyeye nasıl alınır", "windows_11"),
    # — Windows 11 — geniş —
    ("Windows 11 iş istasyonunu CIS'e göre sıkılaştır", "windows_11"),
]


def _eval_questions():
    """A3 — paylaşımlı 52-soruluk dataset (evaluation/eval_dataset.py)."""
    from evaluation.eval_dataset import EVAL_QUESTIONS
    return EVAL_QUESTIONS


def _build_sample(question: str, os_version: str, llm_large, grounding: str) -> dict:
    """Gerçek pipeline: retrieve → GROUNDING_DIRECTIVE'li üretim → RAGAS örneği."""
    from llm.rag.integration import RAGContextBuilder
    try:
        rag = RAGContextBuilder(top_k=5, min_score=0.4, os_version=os_version)
        _ctx, chunks = rag.retrieve_balanced(question)
    except Exception as exc:
        chunks = []
    ctx_txt = "\n\n".join(c.get("text", "") for c in chunks)
    if chunks:
        prompt = (f"SORU: '{question}' için kısa, teknik bir sıkılaştırma önerisi yaz.\n\n"
                  f"CIS BENCHMARK REFERANSLARI:\n{ctx_txt}\n{grounding}\n\nYANIT:")
    else:
        prompt = f"'{question}' için kısa öneri:"
    answer = llm_large(prompt)
    return {
        "question": question,
        "answer": answer,
        "context_chunks": [c.get("text", "") for c in chunks],
        "n_chunks": len(chunks),
    }


def main() -> None:
    from evaluation import force_utf8_output
    force_utf8_output()
    import logging
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    from llm.clients import get_llm_clients
    from llm.prompts.simple_prompts import GROUNDING_DIRECTIVE
    from evaluation.ragas_evaluator import RAGASEvaluator

    small, large = get_llm_clients()
    # JUDGE'ı ÜRETİCİden ayır: 100 soru × ~4 metrik = ~400 judge çağrısı small lane'i (cerebras/
    # sambanova burst) RateLimitError'a sokuyordu. RAGAS_JUDGE_PROVIDER verilirse judge AYRI,
    # tek-sağlayıcı (kotasız novita) client olur → üretim hızlı/free kalır, judge rate-limit yemez.
    # İki override yolu (öncelik: LANES > PROVIDER):
    #  • RAGAS_JUDGE_LANES="openrouter:modelA,openrouter:modelB,..." → ÇOKLU-MODEL ROUND-ROBIN
    #    judge. Paralı ≠ kotasız: ~400 judge çağrısı tek modelde rate-limit'e girer. Havuz yükü
    #    1/N'e indirir + bir lane patlarsa diğerine düşer (LaneLoadBalancer hem dağıtım hem fallback).
    #  • RAGAS_JUDGE_PROVIDER=novita/gemini/... → tek ayrı sağlayıcı judge.
    # Her iki durumda da ÜRETİM (large) hızlı/free kalır → judge üretimden bağımsız.
    judge = small
    judge_lanes = os.environ.get("RAGAS_JUDGE_LANES", "").strip()
    judge_provider = os.environ.get("RAGAS_JUDGE_PROVIDER", "").strip().lower()
    if judge_lanes:
        from llm.clients import _build_lane_balancer
        stats = {"total_calls": 0, "fallback_count": 0, "failures": 0, "by_provider": {}}
        lb = _build_lane_balancer("small", judge_lanes, stats)
        if lb is not None:
            judge = lb
            print(f"[judge] ROUND-ROBIN havuz ({len(lb.lanes)} lane): {[l for l, _ in lb.lanes]}")
        else:
            print("[judge] lane kurulamadı (key/format?) → küçük modele düşüldü")
    elif judge_provider:
        from llm.clients import _PROVIDER_BUILDERS  # tek-sağlayıcı builder
        j_small, _ = _PROVIDER_BUILDERS[judge_provider]()
        judge = j_small
        print(f"[judge] ayrı sağlayıcı: {judge_provider} — üretimden bağımsız")
    evaluator = RAGASEvaluator(llm_fn=judge)   # judge = round-robin havuz / ayrı sağlayıcı / küçük model

    all_q = _eval_questions()  # A3 — paylaşımlı 53-soruluk dataset
    sample_n = int(os.environ.get("RAGAS_SAMPLE", "0")) or len(all_q)
    throttle = float(os.environ.get("RAGAS_THROTTLE_S", "1.5"))
    questions = all_q[:sample_n]

    print(f"RAGAS değerlendirme — {len(questions)} soru (gerçek pipeline + LLM-judge)")
    samples = []
    for i, (q, osv) in enumerate(questions, 1):
        print(f"  [{i}/{len(questions)}] retrieve+generate: {q[:55]}", flush=True)
        try:
            samples.append(_build_sample(q, osv, large, GROUNDING_DIRECTIVE))
        except Exception as exc:
            print(f"      ÜRETİM HATASI: {exc}", flush=True)
        if throttle and i < len(questions):
            time.sleep(throttle)

    report = evaluator.evaluate_batch(samples, progress=True)
    avgs = report.averages()

    out = Path("evaluation/results")
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "n": len(report.samples),
        "averages": avgs,
        "thresholds": {"faithfulness": 0.90, "context_precision": 0.80, "context_recall": 0.80},
        "samples": [{**s.to_dict(), "question": s.question} for s in report.samples],
    }
    (out / "ragas_results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "ragas_report.md").write_text(_to_markdown(avgs, len(report.samples)), encoding="utf-8")

    print(f"\nRapor: {out/'ragas_report.md'} + {out/'ragas_results.json'}")
    report.print_summary()


def _to_markdown(avgs: dict, n: int) -> str:
    if not avgs:
        return "# RAGAS — sonuç yok\n"
    thr = {"faithfulness": 0.90, "answer_relevancy": 0.80, "context_precision": 0.80, "context_recall": 0.80}
    L = [
        "# RAGAS Değerlendirme Raporu (standart, objektif — kullanıcı anketi DEĞİL)",
        "",
        f"**Örnek sayısı:** {n} soru (çoklu OS + kategori; dar + geniş). **Judge:** LLM-as-judge.",
        "**Yöntem:** gerçek RAG pipeline (RAGContextBuilder retrieve + GROUNDING_DIRECTIVE üretim) → RAGAS skorlama.",
        "",
        "| Metrik | Sonuç | Eşik | Durum | Anlamı |",
        "|---|------:|-----:|:-----:|---|",
    ]
    rows = [
        ("faithfulness", "İP-5 groundedness (1−halüsinasyon)"),
        ("answer_relevancy", "cevap soruyu karşılıyor mu"),
        ("context_precision", "İP-3 retrieval isabeti"),
        ("context_recall", "İP-3 retrieval kapsama"),
        ("overall", "genel"),
    ]
    for key, desc in rows:
        v = avgs.get(key, 0.0)
        t = thr.get(key)
        status = "—" if t is None else ("✅" if v >= t else "⚠️")
        tcell = f"{t:.2f}" if t is not None else "—"
        L.append(f"| {key} | {v:.3f} | {tcell} | {status} | {desc} |")
    L += ["", "> RAGAS, RAG sistemleri için standart değerlendirme çerçevesidir (faithfulness/relevancy/",
          "> context-precision/recall). İnsan anketi gerektirmez; LLM-as-judge ile objektif skorlar."]
    return "\n".join(L)


if __name__ == "__main__":
    main()
