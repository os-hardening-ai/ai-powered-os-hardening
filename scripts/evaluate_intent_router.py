"""
Embedding router vs TF-IDF ML — DOĞRULUK + GECİKME karşılaştırması (gerçek Novita).

Amaç: "embedding router TF-IDF'ten daha iyi mi ve hız sorunu yaratıyor mu?" sorusunu
ETİKETLİ bir değerlendirme seti üzerinde ÖLÇEREK yanıtlamak. Karşılaştırma son-kullanıcı
davranışını yansıtsın diye HybridIntentDetector.detect() seviyesinde yapılır (pattern hızlı
yolu + ML backend birlikte). Ayrıca yalnız-ML predict() gecikmesi de ölçülür.

Çalıştırma:  python scripts/benchmark_intent_router.py
Gerekli:     NOVITA_API_KEY (.env)  — embedding router gerçek embed çağrısı yapar.
"""
from __future__ import annotations

import time
import statistics as st
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ── Etiketli değerlendirme seti (final tip: smalltalk / info_request / action_request / out_of_scope)
# CSV'den BAĞIMSIZ elle yazıldı; özellikle "beklenmedik" (argo, typo, karışık) vakalar dahil.
EVAL = [
    # — smalltalk (selam/veda/teşekkür/argo) —
    ("naber", "smalltalk"),
    ("nbr", "smalltalk"),
    ("n'aber", "smalltalk"),
    ("naptın", "smalltalk"),
    ("slm kanka", "smalltalk"),
    ("selamün aleyküm", "smalltalk"),
    ("merhabalar", "smalltalk"),
    ("iyi akşamlar", "smalltalk"),
    ("eyvallah görüşürüz", "smalltalk"),
    ("çok teşekkür ederim", "smalltalk"),
    ("sağ ol dostum", "smalltalk"),
    ("nasılsın bugün", "smalltalk"),
    ("kendine iyi bak", "smalltalk"),
    ("bb", "smalltalk"),

    # — info_request (güvenlik bilgi) —
    ("ssh root login nedir", "info_request"),
    ("PermitRootLogin ne işe yarar", "info_request"),
    ("ufw nedir nasıl çalışır", "info_request"),
    ("cis benchmark nedir", "info_request"),
    ("parola politikası neden önemli", "info_request"),
    ("fail2ban ne yapar", "info_request"),
    ("selinux ne işe yarar açıkla", "info_request"),
    ("auditd loglarını nasıl okurum", "info_request"),
    ("ssh portunu değiştirmek güvenli mi", "info_request"),
    ("zero trust mimarisi nedir", "info_request"),

    # — action_request (güvenlik eylem/üretim) —
    ("ssh root login'i kapat", "action_request"),
    ("ufw firewall'ı yapılandır", "action_request"),
    ("parola politikasını sıkılaştır", "action_request"),
    ("cramfs modülünü devre dışı bırak", "action_request"),
    ("ssh için ansible playbook yaz", "action_request"),
    ("bana bir hardening scripti üret", "action_request"),
    ("PermitRootLogin no yap ve servisi yeniden başlat", "action_request"),
    ("selinux'u enforcing moduna al", "action_request"),
    ("ubuntu 22.04 sunucuyu sıkılaştır", "action_request"),
    ("audit kurallarını uygula", "action_request"),

    # — karışık: greeting + güvenlik (smalltalk OLMAMALI) —
    ("merhaba ssh nasıl sıkılaştırılır", "info_request"),
    ("selam ufw kuralı ekler misin", "action_request"),
    ("iyi günler root login'i devre dışı bırak", "action_request"),

    # — out_of_scope (konu dışı) —
    ("hava durumu nasıl", "out_of_scope"),
    ("2+2 kaç eder", "out_of_scope"),
    ("film öner", "out_of_scope"),
    ("en yakın pizzacı nerede", "out_of_scope"),
    ("bana bir şiir yaz", "out_of_scope"),
    ("dolar kaç tl", "out_of_scope"),
    ("kapital kimin kitabı", "out_of_scope"),
]


def build_detector(backend: str):
    from llm.pipelines.layers.hybrid_intent_detector import HybridIntentDetector
    return HybridIntentDetector(
        use_ml=True, debug=False,
        use_embedding_router=(backend == "embedding"),
    )


def run_backend(backend: str):
    t0 = time.perf_counter()
    det = build_detector(backend)
    init_s = time.perf_counter() - t0  # embedding: cache kurma/yükleme dahil (tek seferlik)

    # Warm-up (cache/HTTP bağlantısı ısınsın, ilk-çağrı sapması ölçüme girmesin)
    det.detect("ssh nedir")

    rows, lat = [], []
    correct = 0
    confus = defaultdict(int)
    for text, gold in EVAL:
        t = time.perf_counter()
        r = det.detect(text)
        dt = (time.perf_counter() - t) * 1000.0  # ms
        lat.append(dt)
        ok = (r.type == gold)
        correct += int(ok)
        if not ok:
            confus[(gold, r.type)] += 1
        rows.append((text, gold, r.type, r.method, ok, dt))

    return {
        "backend": backend,
        "init_s": init_s,
        "acc": correct / len(EVAL),
        "rows": rows,
        "lat": lat,
        "confus": confus,
    }


def pct(v):
    return f"{v*100:.1f}%"


def lat_stats(lat):
    s = sorted(lat)
    p50 = s[len(s)//2]
    p95 = s[int(len(s)*0.95)] if len(s) > 1 else s[-1]
    return st.mean(lat), p50, p95, max(lat)


def main():
    print("=" * 78)
    print(f"Intent backend benchmark — {len(EVAL)} etiketli örnek (detect() seviyesi)")
    print("=" * 78)

    results = {}
    for backend in ("tfidf", "embedding"):
        print(f"\n>>> backend={backend} kuruluyor/çalışıyor ...")
        results[backend] = run_backend(backend)

    # Özet tablo
    print("\n" + "=" * 78)
    print(f"{'BACKEND':<12}{'DOĞRULUK':<12}{'ort ms':<10}{'p50 ms':<10}{'p95 ms':<10}{'init s':<10}")
    print("-" * 78)
    for b in ("tfidf", "embedding"):
        r = results[b]
        mean, p50, p95, mx = lat_stats(r["lat"])
        print(f"{b:<12}{pct(r['acc']):<12}{mean:<10.1f}{p50:<10.1f}{p95:<10.1f}{r['init_s']:<10.2f}")

    # Nerede ayrışıyorlar? (yan yana)
    print("\n" + "=" * 78)
    print("PER-ÖRNEK (yalnız en az bir backend'in YANLIŞ olduğu satırlar)")
    print("-" * 78)
    tf = {row[0]: row for row in results["tfidf"]["rows"]}
    em = {row[0]: row for row in results["embedding"]["rows"]}
    print(f"{'GİRDİ':<42}{'GOLD':<15}{'TF-IDF':<15}{'EMBED':<15}")
    for text, gold in EVAL:
        a = tf[text]; b = em[text]
        if not a[4] or not b[4]:
            ta = a[2] + ("" if a[4] else " ✗")
            tb = b[2] + ("" if b[4] else " ✗")
            print(f"{text[:40]:<42}{gold:<15}{ta:<15}{tb:<15}")

    # Kazanan
    print("\n" + "=" * 78)
    at, ae = results["tfidf"]["acc"], results["embedding"]["acc"]
    mt = lat_stats(results["tfidf"]["lat"])[0]
    me = lat_stats(results["embedding"]["lat"])[0]
    print(f"DOĞRULUK: TF-IDF {pct(at)}  vs  EMBEDDING {pct(ae)}  → "
          f"{'EMBEDDING daha iyi' if ae>at else ('BERABERE' if ae==at else 'TF-IDF daha iyi')}")
    print(f"GECİKME : TF-IDF {mt:.1f}ms vs EMBEDDING {me:.1f}ms (ort/sorgu) — fark {me-mt:+.1f}ms")
    print("=" * 78)


if __name__ == "__main__":
    main()
