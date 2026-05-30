"""
Sağlayıcı Benchmark — tüm OpenAI-uyumlu LLM sağlayıcılarını GERÇEK key'le kıyasla.

`.env`'e hangi `<PROVIDER>_API_KEY` eklersen onu test eder; anahtarı olmayanı ATLAR.
Her sağlayıcı için: erişilebilirlik + gerçek gecikme (P50/P95/avg) + hata sınıfı + örnek
çıktı. Sonuca göre primary/fallback ampirik seçilir (H3 < 5s kim tutuyor?).

Çalıştırma:
    OTEL_SDK_DISABLED=true python -m evaluation.provider_benchmark
Env:
    BENCH_N        sağlayıcı başına ölçüm çağrısı (varsayılan 5)
    BENCH_ONLY     virgülle sağlayıcı adları (örn. "cerebras,sambanova")
    BENCH_PROMPT   özel prompt (varsayılan: SSH sıkılaştırma sorusu)
    <PROVIDER>_MODEL / <PROVIDER>_BASE_URL ile model/uç override
Çıktı: evaluation/results/provider_benchmark.md + provider_benchmark.json

NOT: Gerçek API çağrısı → gecikme gerçekçi. Model adı yanlışsa (deprecation) hata
sınıfı 'model/servis erişilemez' olarak raporlanır → ilgili <PROVIDER>_MODEL'i düzelt.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from api.metrics import MetricsCollector
from llm.clients.openai_compatible_client import (
    PROVIDER_PRESETS,
    build_from_preset,
    preset_api_key,
)

logger = logging.getLogger(__name__)

_H3_TARGET_S = 5.0
DEFAULT_PROMPT = (
    "Ubuntu 24.04'te SSH sunucusunu CIS Benchmark'a göre nasıl sıkılaştırırım? "
    "Kısa, maddeli ve komutlu cevap ver."
)


@dataclass
class ProviderResult:
    provider: str
    model: str
    has_key: bool
    reachable: bool
    n: int = 0
    ok: int = 0
    p50_s: float = 0.0
    p95_s: float = 0.0
    avg_s: float = 0.0
    passed_h3: bool = False
    error: str = ""
    sample: str = ""


def _percentile(durs: List[float], q: float) -> float:
    return round(MetricsCollector._percentile(sorted(durs), q), 3) if durs else 0.0


def bench_provider(provider: str, n: int, prompt: str) -> ProviderResult:
    preset_model = PROVIDER_PRESETS[provider]["model"]
    if not preset_api_key(provider):
        return ProviderResult(provider, preset_model, has_key=False, reachable=False,
                              error="API key yok (atlandı)")
    try:
        client = build_from_preset(provider)
    except Exception as exc:
        return ProviderResult(provider, preset_model, has_key=True, reachable=False,
                              error=f"kurulum hatası: {str(exc)[:160]}")

    model = client.model_name
    # Isınma + erişilebilirlik denetimi (auth/model hatası burada yakalanır)
    try:
        first = client(prompt)
    except Exception as exc:
        return ProviderResult(provider, model, has_key=True, reachable=False,
                              error=f"{type(exc).__name__}: {str(exc)[:160]}")

    durs: List[float] = []
    ok = 0
    for _ in range(n):
        t0 = time.monotonic()
        try:
            client(prompt)
            ok += 1
        except Exception as exc:  # noqa: BLE001 - hata ölçümün parçası
            logger.warning("[Bench] %s çağrı hatası: %s", provider, str(exc)[:120])
        durs.append(time.monotonic() - t0)

    p95 = _percentile(durs, 0.95)
    return ProviderResult(
        provider=provider, model=model, has_key=True, reachable=ok > 0,
        n=n, ok=ok, p50_s=_percentile(durs, 0.50), p95_s=p95,
        avg_s=round(sum(durs) / len(durs), 3) if durs else 0.0,
        passed_h3=(p95 < _H3_TARGET_S and ok > 0),
        error="" if ok == n else f"{n - ok}/{n} çağrı başarısız",
        sample=" ".join(first.split())[:160],
    )


def _sort_key(r: ProviderResult):
    # Önce erişilebilirler (P95 artan), sonra erişilemezler, en sonda key'siz
    tier = 0 if r.reachable else (1 if r.has_key else 2)
    return (tier, r.p95_s if r.reachable else 0.0)


def to_markdown(results: List[ProviderResult]) -> str:
    rows = sorted(results, key=_sort_key)
    L = [
        "# Sağlayıcı Benchmark — Gerçek Gecikme Kıyaslaması",
        "",
        f"**Hedef:** H3 P95 < {_H3_TARGET_S:.0f} sn. Anahtarı olmayan sağlayıcı atlanır.",
        "",
        "| Sağlayıcı | Model | Key | Erişim | P50 (s) | P95 (s) | Ort | OK | H3 (<5s) | Not |",
        "|-----------|-------|:---:|:------:|--------:|--------:|----:|:--:|:--------:|-----|",
    ]
    for r in rows:
        key = "✓" if r.has_key else "—"
        reach = "✅" if r.reachable else "❌"
        h3 = "✅" if r.passed_h3 else ("❌" if r.reachable else "—")
        p50 = f"{r.p50_s:.2f}" if r.reachable else "—"
        p95 = f"**{r.p95_s:.2f}**" if r.reachable else "—"
        avg = f"{r.avg_s:.2f}" if r.reachable else "—"
        okn = f"{r.ok}/{r.n}" if r.reachable else "—"
        note = r.error or (r.sample[:60] + "…" if r.sample else "")
        L.append(f"| {r.provider} | `{r.model}` | {key} | {reach} | {p50} | {p95} | {avg} "
                 f"| {okn} | {h3} | {note} |")
    fast = [r for r in rows if r.passed_h3]
    L += [
        "",
        ("> **En hızlı (H3 geçen):** " + ", ".join(f"{r.provider} ({r.p95_s:.2f}s)" for r in fast[:3])
         if fast else "> **Uyarı:** Hiçbir sağlayıcı H3 (<5s) geçmedi — model/eşzamanlılık ayarına bak."),
        "> Gecikme gerçek API çağrısına bağlı; model adı yanlışsa `<PROVIDER>_MODEL` env'iyle düzelt.",
    ]
    return "\n".join(L)


def save_results(results: List[ProviderResult], out_dir: str | Path = "evaluation/results") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "provider_benchmark.md").write_text(to_markdown(results), encoding="utf-8")
    (out / "provider_benchmark.json").write_text(
        json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    from evaluation import force_utf8_output
    force_utf8_output()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    n = int(os.environ.get("BENCH_N", "5"))
    prompt = os.environ.get("BENCH_PROMPT", DEFAULT_PROMPT)
    only = os.environ.get("BENCH_ONLY")
    providers = list(PROVIDER_PRESETS)
    if only:
        wanted = {x.strip().lower() for x in only.split(",")}
        providers = [p for p in providers if p in wanted]

    results: List[ProviderResult] = []
    for p in providers:
        has = "✓key" if preset_api_key(p) else "key-yok→atla"
        logger.info("[Bench] %s (%s) ...", p, has)
        results.append(bench_provider(p, n, prompt))

    out = save_results(results)
    print("\n" + to_markdown(results))
    print(f"\nRapor: {out / 'provider_benchmark.md'} ve {out / 'provider_benchmark.json'}")


if __name__ == "__main__":
    main()
