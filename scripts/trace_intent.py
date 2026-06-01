#!/usr/bin/env python
"""
Intent katman-katman trace aracı — bir mesaj her katmana NASIL girip NASIL çıkıyor görmek için.

Kullanım:
  PYTHONIOENCODING=utf-8 python scripts/trace_intent.py
  PYTHONIOENCODING=utf-8 python scripts/trace_intent.py "naber" "ssh nasıl güvenli"

Network/LLM GEREKMEZ — yalnız Layer-2 (intent) iç adımlarını izler:
  L2.1 smalltalk pattern → L2.2 out-of-scope keyword → L2.3 ML → FINAL → L3 routing kararı.
"""

import re
import sys
from pathlib import Path

# Repo kökünü sys.path'e ekle (scripts/ klasöründen çalıştırılınca 'llm' bulunsun)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm.pipelines.layers.hybrid_intent_detector import HybridIntentDetector

DEFAULT_INPUTS = [
    "naber", "n'aber", "ne haber", "merhaba", "selam", "nasılsın", "teşekkürler",
    "görüşürüz", "ssh root login nasıl devre dışı bırakılır", "ufw nasıl açılır",
    "hava durumu nasıl", "2+2 kaç eder", "asdfgh", "parolamı unuttum",
]

ROUTE = {
    "smalltalk": "L3A kalıp-cevap (RAG yok)",
    "out_of_scope": "kibar red (RAG yok)",
    "info_request": "L3B RAG + LLM",
    "action_request": "L3C RAG + LLM + script",
}


def _pattern_step(q: str):
    ql = q.strip().lower()
    for subtype, pats in HybridIntentDetector.SMALLTALK_PATTERNS.items():
        for p in pats:
            if re.search(p, ql, re.IGNORECASE):
                return subtype
    return None


def _oos_step(q: str):
    ql = q.strip().lower()
    return [k for k in HybridIntentDetector.OUT_OF_SCOPE_KEYWORDS if k in ql]


def main() -> int:
    inputs = sys.argv[1:] or DEFAULT_INPUTS
    det = HybridIntentDetector(use_ml=True, debug=False)
    ml = getattr(det, "ml_detector", None)

    for q in inputs:
        print("=" * 72)
        print(f"INPUT: {q!r}")
        s1 = _pattern_step(q)
        print(f"  [L2.1 smalltalk pattern] -> {s1 or 'eşleşme yok'}")
        s2 = _oos_step(q)
        print(f"  [L2.2 out-of-scope kw  ] -> {s2 or 'eşleşme yok'}")
        if ml is not None:
            try:
                mlr = ml.predict(q)
                probs = sorted((mlr.probabilities or {}).items(), key=lambda x: -x[1])[:3]
                probs_s = ", ".join(f"{k}={v:.2f}" for k, v in probs)
                print(f"  [L2.3 ML predict       ] -> {mlr.type} (conf={mlr.confidence:.3f}) | top: {probs_s}")
            except Exception as exc:  # noqa: BLE001
                print(f"  [L2.3 ML predict       ] -> HATA: {exc}")
        final = det.detect(q)
        print(f"  [FINAL intent          ] -> type={final.type} subtype={final.subtype} "
              f"conf={final.confidence:.3f} method={final.method}")
        print(f"  [L3 routing kararı     ] -> {ROUTE.get(final.type, 'L3B (default) RAG + LLM')}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
