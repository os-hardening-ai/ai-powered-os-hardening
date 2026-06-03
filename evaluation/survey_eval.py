"""
İP-12 + H2 + H4 — Skorlama Fonksiyonları (deterministik, LLM'siz)

Öneri formundaki üç maddenin SAF skorlama mantığı:

  İP-12  Memnuniyet (Likert ≥4 oranı) > %70
  H2     Karar süresi: araçla vs araçsız — azalma
  H4     Öneri kabul oranı (accept=1, modify=0.5, reject=0)

Bu fonksiyonlar (satisfaction_rate/acceptance_rate/decision_times/summarize) saf ve
unit-test edilebilir; girdi şeması verilirse metriği deterministik üretir.

VERİ KAYNAĞI: İnsan pilotu YERİNE otomatik LLM-judge (evaluation/auto_eval.py) bu şemayı
üretir — bkz. `main()`. Endüstri-standardı LLM-as-a-judge (MT-Bench/AlpacaEval/RAGAS hattı):
tekrarlanabilir, objektif, ölçeklenebilir. (İnsan-anketi protokolü docs/16'da arşiv olarak durur.)

Çalıştırma:   python -m evaluation.survey_eval          # auto_eval'i koşar + skorlar
              python -m evaluation.survey_eval <responses.json>   # hazır JSON'u skorlar
Çıktı:        evaluation/results/survey_report.md + survey_results.json
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# 5'li Likert ölçeği alanları (anket sonu memnuniyet soruları)
LIKERT_FIELDS = ("usefulness", "trust", "clarity", "would_use_again", "overall_satisfaction")
SAT_THRESHOLD = 4        # ≥4 → "memnun" sayılır (5'li ölçek)
SAT_TARGET = 0.70        # İP-12 başarı eşiği (>%70)

# Öneri kararı → kredi (kabul tam, uyarlama yarım, ret sıfır)
ACCEPT_CREDIT = {"accept": 1.0, "modify": 0.5, "reject": 0.0}

MIN_RECOMMENDED_N = 5    # bunun altında örneklem "pilot/gösterge" olarak işaretlenir


# ── Saf skorlama fonksiyonları (LLM'siz, deterministik → unit-test edilebilir) ──

def satisfaction_rate(surveys: List[dict], threshold: int = SAT_THRESHOLD) -> float:
    """İP-12: tüm Likert yanıtları içinde ≥threshold olanların oranı (0.0–1.0)."""
    vals = [v for s in surveys for v in (s.get(f) for f in LIKERT_FIELDS)
            if isinstance(v, (int, float))]
    if not vals:
        return 0.0
    return round(sum(1 for v in vals if v >= threshold) / len(vals), 4)


def acceptance_rate(participants: List[dict]) -> float:
    """H4: tüm öneriler üzerinde ağırlıklı kabul oranı (accept=1, modify=0.5, reject=0)."""
    recs = [r for p in participants for t in p.get("tasks", [])
            for r in t.get("recommendations", [])]
    if not recs:
        return 0.0
    credit = sum(ACCEPT_CREDIT.get(str(r.get("verdict", "reject")).lower(), 0.0) for r in recs)
    return round(credit / len(recs), 4)


def decision_times(participants: List[dict]) -> Dict[str, float]:
    """H2: araçla vs araçsız ortalama karar süresi + azalma oranı."""
    with_tool: List[float] = []
    baseline: List[float] = []
    for p in participants:
        for t in p.get("tasks", []):
            wt = t.get("decision_time_with_tool_s")
            bl = t.get("decision_time_baseline_s")
            if isinstance(wt, (int, float)):
                with_tool.append(float(wt))
            if isinstance(bl, (int, float)):
                baseline.append(float(bl))
    mw = round(sum(with_tool) / len(with_tool), 2) if with_tool else 0.0
    mb = round(sum(baseline) / len(baseline), 2) if baseline else 0.0
    reduction = round((mb - mw) / mb, 4) if mb else 0.0
    return {"mean_with_tool_s": mw, "mean_baseline_s": mb, "reduction_pct": reduction,
            "n_with_tool": len(with_tool), "n_baseline": len(baseline)}


def _real_participants(data: dict) -> List[dict]:
    """`example: true` ile işaretli şablon satırlarını skorlamadan çıkar."""
    return [p for p in data.get("participants", []) if not p.get("example")]


def summarize(data: dict) -> Dict[str, object]:
    participants = _real_participants(data)
    surveys = [p["survey"] for p in participants if isinstance(p.get("survey"), dict)]
    sat = satisfaction_rate(surveys)
    acc = acceptance_rate(participants)
    dt = decision_times(participants)
    n = len(participants)
    return {
        "n_participants": n,
        "small_sample": n < MIN_RECOMMENDED_N,          # dürüstlük: küçük örneklemi işaretle
        "ip12_satisfaction": {"rate": sat, "target": SAT_TARGET, "passed": sat >= SAT_TARGET},
        "h4_acceptance": {"rate": acc, "n_recommendations":
                          sum(len(t.get("recommendations", [])) for p in participants
                              for t in p.get("tasks", []))},
        "h2_decision_time": dt,
        "h2_supported": dt["reduction_pct"] > 0 and dt["n_baseline"] > 0,
    }


# ── Raporlama ───────────────────────────────────────────────────────────────────

def to_markdown(summary: Dict[str, object]) -> str:
    sat = summary["ip12_satisfaction"]          # type: ignore[index]
    acc = summary["h4_acceptance"]              # type: ignore[index]
    dt = summary["h2_decision_time"]            # type: ignore[index]
    sat_mark = "✅" if sat["passed"] else "⚠️"
    h2_mark = "✅" if summary["h2_supported"] else "⚠️"
    L = [
        "# İP-12 / H2 / H4 — Kullanıcı Çalışması Sonuçları",
        "",
        f"**Katılımcı sayısı (n):** {summary['n_participants']}"
        + ("  ⚠️ *küçük örneklem (pilot/gösterge)*" if summary["small_sample"] else ""),
        "",
        "| Madde | Metrik | Sonuç | Eşik/Yön | Durum |",
        "|-------|--------|------:|:--------:|:-----:|",
        f"| İP-12 | Memnuniyet (Likert ≥{SAT_THRESHOLD} oranı) | {sat['rate']:.0%} | >%70 | {sat_mark} |",
        f"| H4 | Öneri kabul oranı | {acc['rate']:.0%} | yüksek | — |",
        f"| H2 | Karar süresi azalması | {dt['reduction_pct']:.0%} | >0 (azalma) | {h2_mark} |",
        "",
        f"- **H2 detay:** araçla {dt['mean_with_tool_s']}s vs araçsız {dt['mean_baseline_s']}s "
        f"(n_araçla={dt['n_with_tool']}, n_araçsız={dt['n_baseline']})",
        f"- **H4 detay:** {acc['n_recommendations']} öneri değerlendirildi "
        f"(accept=1.0, modify=0.5, reject=0.0 ağırlıklı)",
        "",
        "> **Dürüstlük notu:** Sonuçlar gerçek kullanıcı pilotundan gelir; örneklem küçükse "
        "(n<5) bu **gösterge** niteliğindedir, istatistiksel genelleme için n büyütülmelidir.",
    ]
    return "\n".join(L)


def save_results(summary: Dict[str, object], out_dir: str | Path = "evaluation/results") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "survey_report.md").write_text(to_markdown(summary), encoding="utf-8")
    (out / "survey_results.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    from evaluation import force_utf8_output
    force_utf8_output()                       # Türkçe çıktı Windows'ta bozulmasın
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Argüman verildiyse hazır JSON'u skorla (geriye uyumlu); verilmediyse otomatik
    # LLM-judge (auto_eval) koş → aynı şemayı üret → skorla.
    if len(sys.argv) > 1:
        p = Path(sys.argv[1])
        if not p.exists():
            print(f"[Survey] Yanıt dosyası yok: {p}")
            sys.exit(1)
        data = json.loads(p.read_text(encoding="utf-8"))
    else:
        print("[Survey] Otomatik LLM-judge değerlendirmesi koşuluyor (auto_eval)...")
        from evaluation.auto_eval import AutoEvalHarness, SCENARIOS
        from llm.clients import get_llm_clients
        import os as _os
        small, large = get_llm_clients()
        throttle = float(_os.environ.get("AUTO_EVAL_THROTTLE_S", "3"))
        rep = AutoEvalHarness(llm_fn=large, judge_fn=small, throttle_s=throttle).run(SCENARIOS)
        data = rep.to_survey_data()

    summary = summarize(data)
    out = save_results(summary)
    print(to_markdown(summary))
    print(f"\nRapor: {out / 'survey_report.md'} ve {out / 'survey_results.json'}")


if __name__ == "__main__":
    main()
