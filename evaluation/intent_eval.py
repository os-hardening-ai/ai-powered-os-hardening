"""
Intent doğruluğu — TEKRARLANABİLİR, OFFLINE ($0) eval kapısı.

Intent konsolidasyonunun (whack-a-mole fix) DİREKSİYONU. `detect()` seviyesinde, TF-IDF
backend ile (AĞSIZ, deterministik) etiketli set üzerinde niyet doğruluğunu ölçer. Tek kaynak
etiketli set: `scripts/evaluate_intent_router.EVAL`.

İki mod:
  python -m evaluation.intent_eval            → ölç + baseline'ı evaluation/results/ altına YAZ
  python -m evaluation.intent_eval --check    → ölç + baseline'a karşı KARŞILAŞTIR; regresyon
                                                varsa exit 1 (commit kapısı: "eval düşürense merge yok")

DÜRÜSTLÜK NOTU — KAPSAM:
  Bu harness `detect()` seviyesinde TF-IDF'in SAHİBİ OLDUĞU kararı ölçer: alan-içi niyet
  (smalltalk / info_request / action_request). KAPSAM kararı (out_of_scope) artık detect()'te
  DEĞİL — L1 LLM safety kapısının (secure_v2) tek sorumluluğudur. Bu yüzden etiketli setteki
  `out_of_scope` örnekleri bu offline metriğin DIŞINDA tutulur (detect() onları üretmez; o
  karar canlı-LLM/yerel-safety gerektirir). Kapsam regresyonu fake-LLM route-matrix unit
  testlerinde (tests/unit/test_pipeline_routes_matrix.py) deterministik kilitlenir. İkisi
  birlikte = eval direksiyonu: niyet → bu harness, kapsam → route-matrix testleri.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# Gate referansı VERSİYONLANIR (evaluation/results/ gitignore'da; bu yol tracked).
_BASELINE_PATH = Path("evaluation/intent_baseline.json")

# detect() seviyesinde TF-IDF'in deterministik olarak ürettiği nihai tipler.
# out_of_scope KAPSAM kararıdır → konsolidasyon sonrası L1 kapısına taşınır (yukarıdaki nota bak).
_DETECT_TYPES = ("smalltalk", "info_request", "action_request", "out_of_scope")


def _load_eval_set() -> List[Tuple[str, str]]:
    """Tek kaynak etiketli set (scripts/evaluate_intent_router.EVAL), KAPSAM örnekleri hariç.

    out_of_scope artık detect()'in işi değil (L1 safety gate'in) → offline detect() metriğinden
    çıkarılır. Bkz. modül başı DÜRÜSTLÜK NOTU. Kapsam regresyonu route-matrix testlerinde."""
    from scripts.evaluate_intent_router import EVAL
    return [(t, g) for t, g in EVAL if g != "out_of_scope"]


def run_offline(eval_set: List[Tuple[str, str]] | None = None) -> Dict[str, object]:
    """TF-IDF detect()'i etiketli set üzerinde koştur (AĞSIZ, deterministik). Yapısal sonuç döndür."""
    from llm.pipelines.layers.hybrid_intent_detector import HybridIntentDetector

    eval_set = eval_set or _load_eval_set()
    det = HybridIntentDetector(use_ml=True, debug=False, use_embedding_router=False)
    det.detect("ssh nedir")  # warm-up (ilk-çağrı sapması ölçüme girmesin)

    correct = 0
    per_cat_total: Dict[str, int] = defaultdict(int)
    per_cat_correct: Dict[str, int] = defaultdict(int)
    confusion: Dict[str, int] = defaultdict(int)
    per_example: Dict[str, Dict[str, object]] = {}

    for text, gold in eval_set:
        r = det.detect(text)
        ok = (r.type == gold)
        correct += int(ok)
        per_cat_total[gold] += 1
        per_cat_correct[gold] += int(ok)
        if not ok:
            confusion[f"{gold}->{r.type}"] += 1
        per_example[text] = {"gold": gold, "pred": r.type, "ok": ok, "method": r.method}

    n = len(eval_set)
    return {
        "backend": "tfidf",
        "n": n,
        "accuracy": round(correct / n, 4) if n else 0.0,
        "correct": correct,
        "per_category_accuracy": {
            cat: round(per_cat_correct[cat] / per_cat_total[cat], 4)
            for cat in sorted(per_cat_total)
        },
        "per_category_n": dict(sorted(per_cat_total.items())),
        "confusion": dict(sorted(confusion.items())),
        "per_example": per_example,
    }


def _print_summary(res: Dict[str, object]) -> None:
    print("=" * 72)
    print(f"INTENT EVAL (offline, TF-IDF) — {res['correct']}/{res['n']} = "
          f"{res['accuracy'] * 100:.1f}%")
    print("=" * 72)
    for cat, acc in res["per_category_accuracy"].items():  # type: ignore[index]
        n = res["per_category_n"][cat]  # type: ignore[index]
        print(f"  {cat:<16} {acc * 100:5.1f}%  (n={n})")
    misses = {t: e for t, e in res["per_example"].items() if not e["ok"]}  # type: ignore[union-attr]
    if misses:
        print("-" * 72)
        print("KAÇIRMALAR:")
        for t, e in misses.items():
            print(f"  [{e['method']}] \"{t}\"  gold={e['gold']}  pred={e['pred']}")
    print("=" * 72)


def _write_baseline(res: Dict[str, object], path: Path = _BASELINE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def check_against_baseline(res: Dict[str, object], path: Path = _BASELINE_PATH) -> int:
    """Mevcut sonucu donmuş baseline'a karşı kıyasla. Regresyon varsa 1, yoksa 0 döndür.

    REGRESYON = (genel doğruluk baseline'dan DÜŞÜK) VEYA (baseline'da DOĞRU olan bir örnek
    artık YANLIŞ). Yeni doğru örnek / yükselen doğruluk regresyon DEĞİLDİR (iyileşme serbest).
    """
    if not path.exists():
        print(f"[GATE] baseline yok ({path}) — önce `python -m evaluation.intent_eval` ile dondur.")
        return 1
    base = json.loads(path.read_text(encoding="utf-8"))

    failed = False
    if res["accuracy"] < base["accuracy"]:  # type: ignore[operator]
        print(f"[GATE] ✗ doğruluk düştü: {base['accuracy']:.4f} → {res['accuracy']:.4f}")
        failed = True

    base_ex: Dict[str, Dict] = base.get("per_example", {})
    cur_ex: Dict[str, Dict] = res["per_example"]  # type: ignore[assignment]
    regressions = [
        t for t, be in base_ex.items()
        if be.get("ok") and t in cur_ex and not cur_ex[t]["ok"]
    ]
    if regressions:
        failed = True
        print(f"[GATE] ✗ {len(regressions)} örnek DOĞRU→YANLIŞ oldu:")
        for t in regressions:
            print(f"    \"{t}\"  baseline={base_ex[t]['pred']}  şimdi={cur_ex[t]['pred']} "
                  f"(gold={cur_ex[t]['gold']})")

    if not failed:
        improved = res["accuracy"] - base["accuracy"]  # type: ignore[operator]
        msg = f"(+{improved:.4f} iyileşme)" if improved > 0 else "(eşit)"
        print(f"[GATE] ✓ regresyon yok — doğruluk {res['accuracy']:.4f} {msg}")
    return 1 if failed else 0


def main() -> None:
    from evaluation import force_utf8_output
    force_utf8_output()

    ap = argparse.ArgumentParser(description="Offline TF-IDF intent eval kapısı")
    ap.add_argument("--check", action="store_true",
                    help="baseline'a karşı kıyasla; regresyon varsa exit 1")
    args = ap.parse_args()

    res = run_offline()
    _print_summary(res)

    if args.check:
        sys.exit(check_against_baseline(res))
    else:
        out = _write_baseline(res)
        print(f"Baseline donduruldu: {out}")


if __name__ == "__main__":
    main()
