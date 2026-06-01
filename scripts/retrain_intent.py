#!/usr/bin/env python
"""
Intent ML modelini güçlendir: augment JSON'ı mevcut dataset'e ekle (dedup) → retrain → kaydet.

Kullanım:
  python scripts/retrain_intent.py <augment.json>

<augment.json>: workflow çıktısı; {"result":[{"intent":..,"examples":[..]}]} VEYA düz [{...}] formatı.
Mevcut data/intent_training_dataset.csv'ye eklenir, tekrarlar (normalize text) atılır,
MLIntentDetector.train() ile yeniden eğitilir, llm/ml/models/*.joblib güncellenir.
"""

import io
import json
import sys
from pathlib import Path

import pandas as pd

try:  # Windows konsolu (cp1254) Türkçe/→ karakterlerinde patlamasın
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CSV = "data/intent_training_dataset.csv"


def main() -> int:
    # MOD 1: augment.json verildi → mevcut CSV'ye ekle (dedup). MOD 2: arg yok →
    # doğrudan MEVCUT CSV'den yeniden eğit (veri zaten CSV'de, ör. expand_intent_dataset.py).
    if len(sys.argv) >= 2:
        with io.open(sys.argv[1], encoding="utf-8") as f:
            d = json.load(f)
        result = d["result"] if isinstance(d, dict) and "result" in d else d
        rows = []
        for item in result:
            intent = item["intent"]
            for ex in item.get("examples", []):
                t = (ex or "").strip()
                if t:
                    rows.append({"text": t, "intent": intent})
        aug = pd.DataFrame(rows)
        print(f"AUGMENT: {len(aug)} örnek | {dict(aug['intent'].value_counts())}")
        base = pd.read_csv(CSV)[["text", "intent"]]
        print(f"BASE: {len(base)}")
        combined = pd.concat([base, aug], ignore_index=True)
        combined["_n"] = combined["text"].astype(str).str.strip().str.lower()
        before = len(combined)
        combined = combined.drop_duplicates(subset=["_n"]).drop(columns=["_n"]).reset_index(drop=True)
        print(f"MERGED+DEDUP: {len(combined)} (atılan tekrar: {before - len(combined)})")
        combined.to_csv(CSV, index=False)
        print(f"CSV güncellendi: {CSV}")
    else:
        print("Augment JSON verilmedi → MEVCUT CSV'den yeniden eğitiliyor.")
        combined = pd.read_csv(CSV)[["text", "intent"]]

    print(f"DIST: {dict(combined['intent'].value_counts())}")

    from llm.ml.intent_detector import MLIntentDetector
    det = MLIntentDetector()
    metrics = det.train(CSV)
    det.save_models()
    clean = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in metrics.items()}
    print(f"\n=== METRİKLER ===\n{clean}")
    print("→ llm/ml/models/intent_model.joblib + intent_vectorizer.joblib güncellendi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
