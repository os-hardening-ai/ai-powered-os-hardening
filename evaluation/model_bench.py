"""
MODEL BENCHMARK — small/large lane adaylarını aynı sorularla kıyasla, en iyileri seç.

Her aday model İZOLE çalışır (fallback YOK — getter doğrudan tek modele bağlar). Adillik için
RAG bağlamı her soru için BİR KEZ çekilir ve TÜM modellere aynısı verilir. Ölçülen:
  - latency (p50/ort)        — hız
  - faithfulness, relevancy  — kalite (sabit judge ile RAGAS-tarzı)
  - errors                   — sağlayıcı hatası (ör. OpenRouter 402 kredi)

Çıktı: model × (latency, faithfulness, relevancy, hata) tablosu + keep/remove önerisi.
Çalıştırma:  python -m evaluation.model_bench
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, List, Tuple

# Adil + ucuz bir alt küme (dar + 1 geniş). RAG bağlamı paylaşılır.
BENCH_QUESTIONS: List[Tuple[str, str]] = [
    ("SSH için PermitRootLogin nasıl devre dışı bırakılır", "ubuntu_24_04"),
    ("Parola minimum uzunluğu ve karmaşıklığı nasıl zorunlu kılınır", "ubuntu_24_04"),
    ("auditd ile zaman değişikliklerini izleyen kural nasıl eklenir", "ubuntu_24_04"),
    ("UFW ile varsayılan deny politikası nasıl ayarlanır", "ubuntu_24_04"),
    ("Windows 11'de SMBv1 nasıl devre dışı bırakılır", "windows_11"),
    ("SSH sunucusunu kapsamlı şekilde sıkılaştır", "ubuntu_24_04"),
]


def _candidates() -> List[Tuple[str, Callable]]:
    """(etiket, () -> LLMCallable) — her biri TEK modele bağlı, fallback YOK."""
    from llm.clients.openai_compatible_client import (
        get_small_cerebras_llm, get_large_cerebras_llm,
        get_small_sambanova_llm, get_large_sambanova_llm,
        get_small_gemini_llm,
    )
    from llm.clients.novita_llm_client import get_small_novita_llm, get_large_novita_llm
    out = []
    for label, getter in [
        ("cerebras:gpt-oss-120b (small)", get_small_cerebras_llm),
        ("cerebras:gpt-oss-120b (large)", get_large_cerebras_llm),
        ("sambanova:gpt-oss-120b (small)", get_small_sambanova_llm),
        ("sambanova:gpt-oss-120b (large)", get_large_sambanova_llm),
        ("openrouter:gemini-3.1-flash-lite", get_small_gemini_llm),
        ("novita:llama-3.1-8b (small)", get_small_novita_llm),
        ("novita:deepseek-v3 (large)", get_large_novita_llm),
    ]:
        try:
            out.append((label, getter()))
        except Exception as exc:
            print(f"  [SKIP] {label}: kurulum hatası {exc}")
    return out


def _retrieve_context(question: str, os_version: str) -> str:
    from llm.rag.integration import RAGContextBuilder
    try:
        rag = RAGContextBuilder(top_k=5, min_score=0.4, os_version=os_version)
        _ctx, chunks = rag.retrieve_balanced(question)
        return "\n\n".join(c.get("text", "") for c in chunks)
    except Exception:
        return ""


def main() -> None:
    from evaluation import force_utf8_output
    force_utf8_output()
    import logging
    logging.basicConfig(level=logging.WARNING)

    from llm.prompts.simple_prompts import GROUNDING_DIRECTIVE
    from evaluation.ragas_evaluator import RAGASEvaluator
    from llm.clients.openai_compatible_client import get_small_cerebras_llm

    # Sabit judge — tutarlılık için TEK model (cerebras gpt-oss-120b).
    judge = RAGASEvaluator(llm_fn=get_small_cerebras_llm())

    # Bağlamları bir kez çek (tüm modeller aynı bağlamı görsün).
    print("Bağlamlar çekiliyor (her soru bir kez)...")
    ctxs = [(q, osv, _retrieve_context(q, osv)) for q, osv in BENCH_QUESTIONS]

    candidates = _candidates()
    print(f"\n{len(candidates)} aday model × {len(BENCH_QUESTIONS)} soru\n")

    results = {}
    for label, llm in candidates:
        lats, faiths, rels, errs = [], [], [], 0
        for q, osv, ctx in ctxs:
            prompt = (f"SORU: '{q}' için kısa, teknik bir sıkılaştırma önerisi yaz.\n\n"
                      f"CIS BENCHMARK REFERANSLARI:\n{ctx}\n{GROUNDING_DIRECTIVE}\n\nYANIT:") if ctx \
                else f"'{q}' için kısa öneri:"
            try:
                t = time.perf_counter()
                ans = llm(prompt)
                lats.append(time.perf_counter() - t)
                r = judge.evaluate_sample(q, ans, [ctx] if ctx else [])
                faiths.append(r.faithfulness)
                rels.append(r.answer_relevancy)
            except Exception as exc:
                errs += 1
                print(f"  [{label}] HATA: {str(exc)[:80]}")
        n = max(len(lats), 1)
        results[label] = {
            "avg_latency_s": round(sum(lats) / n, 2) if lats else None,
            "faithfulness": round(sum(faiths) / len(faiths), 3) if faiths else None,
            "relevancy": round(sum(rels) / len(rels), 3) if rels else None,
            "errors": errs, "n_ok": len(lats),
        }
        r = results[label]
        print(f"  {label:<38} lat={r['avg_latency_s']}s  faith={r['faithfulness']}  "
              f"rel={r['relevancy']}  err={errs}")

    out = Path("evaluation/results"); out.mkdir(parents=True, exist_ok=True)
    (out / "model_bench_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSonuç: {out/'model_bench_results.json'}")

    # Basit öneri: hata yok + faithfulness en yüksek + makul latency.
    ok = {k: v for k, v in results.items() if v["errors"] == 0 and v["faithfulness"] is not None}
    if ok:
        best = sorted(ok.items(), key=lambda kv: (-kv[1]["faithfulness"], kv[1]["avg_latency_s"]))
        print("\n=== ÖNERİ (faithfulness↓ sonra latency↑) ===")
        for label, v in best:
            print(f"  TUT: {label}  (faith {v['faithfulness']}, {v['avg_latency_s']}s)")
    bad = {k: v for k, v in results.items() if v["errors"] > 0 or v["faithfulness"] is None}
    for label, v in bad.items():
        print(f"  ÇIKAR/SORUN: {label}  (err={v['errors']}, n_ok={v['n_ok']})")


if __name__ == "__main__":
    main()
