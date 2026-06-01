"""
OOS eşiği teşhisi: her değerlendirme örneğinin router'a en yüksek kosinüs benzerliği
(global_max) nedir? In-scope (güvenlik) örnekleri yüksek, konu-dışı örnekleri düşük
benzerlik veriyorsa, temiz bir ayıran eşik vardır. Eşik taraması ile en iyi değeri bulur.

Referans embedding'leri cache'ten yüklenir (yeniden embed YOK); yalnız 44 sorgu embed edilir.
"""
from __future__ import annotations
import numpy as np
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass

from scripts.evaluate_intent_router import EVAL
from llm.ml.embedding_router import EmbeddingIntentRouter, _l2_normalize

router = EmbeddingIntentRouter(debug=False)  # cache load

# Her sorgu için global_max (en yüksek tek-referans kosinüsü) + tahmin
client = router._client()
qvecs = _l2_normalize(np.asarray(client.embed_texts([t for t, _ in EVAL]), dtype=np.float32))

gmax = []
for (text, gold), qv in zip(EVAL, qvecs):
    sims = router._vectors @ qv
    gmax.append((text, gold, float(sims.max())))

# Gruplara göre global_max dağılımı
print("=" * 70)
print("global_max (en yüksek kosinüs) — gold tipe göre")
print("=" * 70)
groups = {}
for text, gold, g in gmax:
    groups.setdefault(gold, []).append(g)
for gold, vals in sorted(groups.items()):
    vals_s = sorted(vals)
    print(f"{gold:<16} n={len(vals):<3} min={min(vals):.3f}  med={vals_s[len(vals_s)//2]:.3f}  max={max(vals):.3f}")

# Konu-dışı örneklerin global_max'ları (eşik bunların üstünde olmalı)
print("\nout_of_scope örnekleri (global_max artan):")
for text, gold, g in sorted([x for x in gmax if x[1] == "out_of_scope"], key=lambda z: z[2]):
    print(f"  {g:.3f}  {text}")

print("\nin-scope (info/action) en DÜŞÜK global_max'lar (eşik bunların altında kalmalı):")
ins = sorted([x for x in gmax if x[1] in ("info_request", "action_request")], key=lambda z: z[2])
for text, gold, g in ins[:6]:
    print(f"  {g:.3f}  {text}  [{gold}]")

# Eşik taraması: yalnız OOS ayrımı için doğruluk (router seviyesinde, in-scope=oos değil)
print("\n" + "=" * 70)
print("OOS eşik taraması — router 'out_of_scope vs in-scope' ikili doğruluğu")
print("=" * 70)
best = None
for thr in [x / 100 for x in range(30, 61, 2)]:
    tp = sum(1 for _, gold, g in gmax if gold == "out_of_scope" and g < thr)   # doğru OOS
    fp = sum(1 for _, gold, g in gmax if gold != "out_of_scope" and g < thr)   # yanlış OOS (in-scope'u reddetti)
    n_oos = sum(1 for _, gold, _ in gmax if gold == "out_of_scope")
    n_in = sum(1 for _, gold, _ in gmax if gold != "out_of_scope")
    acc = (tp + (n_in - fp)) / (n_oos + n_in)
    flag = ""
    if best is None or acc > best[1]:
        best = (thr, acc); flag = ""
    print(f"  thr={thr:.2f}  OOS_recall={tp}/{n_oos}  in-scope_yanlış_red={fp}/{n_in}  ikili_acc={acc:.3f}")
print(f"\nEN İYİ eşik ≈ {best[0]:.2f} (ikili doğruluk {best[1]:.3f}); mevcut varsayılan = {router.oos_threshold:.2f}")
