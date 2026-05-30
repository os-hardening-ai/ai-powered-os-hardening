"""
H3 Hipotez Kanıtı — P95 Gecikme Yük Testi

Öneri formu H3: "Vektör veritabanı ile harmanlanan ön işleme ve chunking stratejileri,
1.000+ kural/öneri dokümanı içinde P95 cevap süresini < 5 sn seviyesinde tutacaktır."

Bu script FastAPI uygulamasını in-process TestClient ile ayağa kaldırır, agent ve chat
uçlarına eşzamanlı (concurrent) istek atar, her isteğin gecikmesini ölçer ve
P50/P95/P99 dağılımını çıkarır. Percentile hesabı api/metrics.py'den yeniden kullanılır.

Çalıştırma (kotasız sağlayıcı önerilir):
    LLM_PROVIDER=novita LOAD_N=20 LOAD_CONCURRENCY=4 python -m evaluation.load_test

Çıktı: evaluation/results/load_test_report.md + load_test_results.json

NOT: Gerçek LLM çağrısı yapılır → gecikme gerçekçidir. Eşzamanlılık yüksekse sağlayıcı
throttle/kota yiyebilir; örneklem küçükse rapor bunu dürüstçe belirtir.
"""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# api/metrics.py'deki percentile mantığını yeniden kullan (yeniden yazma yok)
from api.metrics import MetricsCollector

_P95_TARGET_S = 5.0  # H3 hedefi


@dataclass
class EndpointSpec:
    name: str
    method: str
    path: str
    payload: dict


# Yük atılacak uçlar — formdaki kritik akışlar
ENDPOINTS: List[EndpointSpec] = [
    EndpointSpec("agent_plan", "POST", "/api/agent/plan",
                 {"goal": "SSH ve parola politikasını sıkılaştır",
                  "os_target": "ubuntu_24_04", "security_level": "balanced"}),
    EndpointSpec("agent_harden", "POST", "/api/agent/harden",
                 {"goal": "SSH sıkılaştır", "os_target": "ubuntu_24_04",
                  "security_level": "balanced", "format": "bash"}),
    EndpointSpec("chat_rag", "POST", "/api/chat",
                 {"question": "Ubuntu 24.04 SSH nasıl sıkılaştırılır?",
                  "use_rag": True, "timeout": 60}),
]


@dataclass
class EndpointResult:
    name: str
    n: int
    ok: int
    errors: int
    p50_s: float
    p95_s: float
    p99_s: float
    avg_s: float
    max_s: float
    passed_h3: bool          # P95 < 5sn
    durations_s: List[float] = field(default_factory=list)


@dataclass
class LoadReport:
    concurrency: int
    results: List[EndpointResult] = field(default_factory=list)

    def summary(self) -> Dict[str, object]:
        return {
            "concurrency": self.concurrency,
            "p95_target_s": _P95_TARGET_S,
            "endpoints": {
                r.name: {"n": r.n, "ok": r.ok, "errors": r.errors,
                         "p50_s": r.p50_s, "p95_s": r.p95_s, "p99_s": r.p99_s,
                         "avg_s": r.avg_s, "max_s": r.max_s, "passed_h3": r.passed_h3}
                for r in self.results
            },
        }


def _percentile(durations: List[float], q: float) -> float:
    """api/metrics._percentile'ı kullan (tutarlı percentile tanımı)."""
    return round(MetricsCollector._percentile(sorted(durations), q), 3)


def _build_client():
    """In-process TestClient. Auth bypass (dev modu) + OTel kapalı (gerçek latency)."""
    os.environ.pop("API_KEY", None)            # auth dev-modda açık (require_api_key bypass)
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")  # Jaeger yoksa span-export gecikmesini önle
    from fastapi.testclient import TestClient
    from main import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _warmup(client, specs: List[EndpointSpec]) -> None:
    """Her uca 1 ısınma isteği — lazy singleton init yarışını ölçümden önce çöz."""
    for spec in specs:
        try:
            client.request(spec.method, spec.path, json=spec.payload)
        except Exception:
            pass


def run_endpoint(client, spec: EndpointSpec, n: int, concurrency: int) -> EndpointResult:
    durations: List[float] = []
    statuses: List[int] = []

    def _one(_i: int):
        t0 = time.monotonic()
        try:
            r = client.request(spec.method, spec.path, json=spec.payload)
            dt = time.monotonic() - t0
            return dt, r.status_code
        except Exception as exc:
            logger.warning("[Load] %s istek hatası: %s", spec.name, exc)
            return time.monotonic() - t0, 0

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for dt, st in pool.map(_one, range(n)):
            durations.append(dt)
            statuses.append(st)

    ok = sum(1 for s in statuses if 200 <= s < 300)
    p95 = _percentile(durations, 0.95)
    return EndpointResult(
        name=spec.name, n=n, ok=ok, errors=n - ok,
        p50_s=_percentile(durations, 0.50), p95_s=p95, p99_s=_percentile(durations, 0.99),
        avg_s=round(sum(durations) / len(durations), 3) if durations else 0.0,
        max_s=round(max(durations), 3) if durations else 0.0,
        passed_h3=p95 < _P95_TARGET_S and ok > 0,
        durations_s=[round(d, 3) for d in durations],
    )


def to_markdown(rep: LoadReport) -> str:
    L = [
        "# H3 — P95 Gecikme Yük Testi",
        "",
        f"**Hipotez (H3):** P95 cevap süresi < {_P95_TARGET_S:.0f} sn.",
        f"**Yöntem:** In-process FastAPI (TestClient), eşzamanlılık={rep.concurrency}, "
        "gerçek LLM çağrısı. Percentile: `api/metrics.MetricsCollector._percentile` (index tabanlı).",
        "",
        "| Uç | n | OK | Hata | P50 (s) | P95 (s) | P99 (s) | Ort | Maks | H3 (<5s) |",
        "|----|--:|---:|----:|--------:|--------:|--------:|----:|----:|:--------:|",
    ]
    for r in rep.results:
        mark = "✅" if r.passed_h3 else "❌"
        L.append(f"| {r.name} | {r.n} | {r.ok} | {r.errors} | {r.p50_s:.2f} | "
                 f"**{r.p95_s:.2f}** | {r.p99_s:.2f} | {r.avg_s:.2f} | {r.max_s:.2f} | {mark} |")
    L += [
        "",
        "> **Not:** Gecikme gerçek LLM (sağlayıcı) çağrısına bağlıdır. Eşzamanlı istekler "
        "sağlayıcı tarafında kuyruğa girebilir; örneklem küçükse (n düşük) P95 gürültülü olabilir. "
        "Agent uçları RAG+LLM zinciri içerir; chat ucu tam 4-katman pipeline'dan geçer.",
    ]
    return "\n".join(L)


def save_results(rep: LoadReport, out_dir: str | Path = "evaluation/results") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "load_test_report.md").write_text(to_markdown(rep), encoding="utf-8")
    (out / "load_test_results.json").write_text(
        json.dumps(rep.summary(), ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def print_report(rep: LoadReport) -> None:
    print("\n" + "=" * 60)
    print(f"H3 P95 YUK TESTI (concurrency={rep.concurrency}, hedef <{_P95_TARGET_S:.0f}s)")
    print("=" * 60)
    for r in rep.results:
        mark = "[OK]" if r.passed_h3 else "[!!]"
        print(f"{mark} {r.name:14s} P95={r.p95_s:6.2f}s  P50={r.p50_s:5.2f}s  "
              f"ok={r.ok}/{r.n}")
    print("=" * 60)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    n = int(os.environ.get("LOAD_N", "20"))
    concurrency = int(os.environ.get("LOAD_CONCURRENCY", "4"))
    only = os.environ.get("LOAD_ONLY")  # virgülle ayrık uç adları (opsiyonel)

    specs = ENDPOINTS
    if only:
        wanted = {x.strip() for x in only.split(",")}
        specs = [s for s in ENDPOINTS if s.name in wanted]

    client = _build_client()
    _warmup(client, specs)  # init yarışını ölçümden önce çöz
    rep = LoadReport(concurrency=concurrency)
    for spec in specs:
        logger.info("[Load] %s × %d (concurrency=%d)...", spec.name, n, concurrency)
        rep.results.append(run_endpoint(client, spec, n, concurrency))

    out = save_results(rep)
    print(f"Rapor: {out / 'load_test_report.md'} ve {out / 'load_test_results.json'}")
    try:
        print_report(rep)
    except Exception as exc:  # pragma: no cover
        print(f"(konsol ozeti yazdirilamadi: {exc})")


if __name__ == "__main__":
    main()
