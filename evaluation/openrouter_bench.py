"""
OPENROUTER MODEL BENCHMARK — OpenRouter'daki (ücretsiz) modelleri aynı sorularla kıyasla.

Önceki model_bench cerebras/sambanova'yı 429 ile bozmuştu (judge da cerebras'tı → çöp skor).
Bu sürüm DÜZELTİR: judge = NOVITA (kotasız), generation = OpenRouter :free modelleri (kredi
gerekmez), throttle'lı. Adillik: RAG bağlamı her soru için BİR KEZ çekilir, tüm modellere aynısı.

Çalıştırma:  python -m evaluation.openrouter_bench
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import List, Tuple

# OpenRouter ÜCRETSIZ adaylar (canlı katalogdan seçildi, kredi gerekmez). small + large karışık.
OR_MODELS: List[str] = [
    "openai/gpt-oss-120b:free",                  # cerebras/sambanova'daki modelin OR-free hali
    "openai/gpt-oss-20b:free",                   # küçük/hızlı varyant
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",     # küçük/hızlı
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-nano-9b-v2:free",           # küçük/hızlı
    "z-ai/glm-4.5-air:free",
]

BENCH_QUESTIONS: List[Tuple[str, str]] = [
    ("SSH için PermitRootLogin nasıl devre dışı bırakılır", "ubuntu_24_04"),
    ("Parola minimum uzunluğu ve karmaşıklığı nasıl zorunlu kılınır", "ubuntu_24_04"),
    ("auditd ile zaman değişikliklerini izleyen kural nasıl eklenir", "ubuntu_24_04"),
    ("UFW ile varsayılan deny politikası nasıl ayarlanır", "ubuntu_24_04"),
    ("Windows 11'de SMBv1 nasıl devre dışı bırakılır", "windows_11"),
    ("SSH sunucusunu kapsamlı şekilde sıkılaştır", "ubuntu_24_04"),
]


def _or_client(model_id: str):
    from llm.clients.openai_compatible_client import OpenAICompatibleClient
    return OpenAICompatibleClient(
        provider="openrouter", model_name=model_id,
        api_key=os.environ.get("OPENROUTER_API_KEY", "") or "",
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=0.3, timeout=60.0, max_retries=2,
    )


def _retrieve(question: str, os_version: str) -> str:
    from llm.rag.integration import RAGContextBuilder
    try:
        rag = RAGContextBuilder(top_k=5, min_score=0.4, os_version=os_version)
        _c, chunks = rag.retrieve_balanced(question)
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
    from llm.clients.novita_llm_client import get_small_novita_llm

    judge = RAGASEvaluator(llm_fn=get_small_novita_llm())   # KOTASIZ judge (429 confound yok)
    throttle = float(os.environ.get("OR_THROTTLE_S", "2.0"))

    print("Bağlamlar çekiliyor...")
    ctxs = [(q, osv, _retrieve(q, osv)) for q, osv in BENCH_QUESTIONS]
    print(f"{len(OR_MODELS)} OpenRouter modeli × {len(BENCH_QUESTIONS)} soru\n")

    results = {}
    for mid in OR_MODELS:
        try:
            llm = _or_client(mid)
        except Exception as exc:
            results[mid] = {"error": f"kurulum: {exc}", "n_ok": 0}
            print(f"  [SKIP] {mid}: {exc}"); continue
        lats, faiths, rels, errs, errmsg = [], [], [], 0, ""
        for q, osv, ctx in ctxs:
            prompt = (f"SORU: '{q}' için kısa, teknik bir sıkılaştırma önerisi yaz.\n\n"
                      f"CIS BENCHMARK REFERANSLARI:\n{ctx}\n{GROUNDING_DIRECTIVE}\n\nYANIT:") if ctx \
                else f"'{q}' için kısa öneri:"
            try:
                t = time.perf_counter(); ans = llm(prompt); lats.append(time.perf_counter() - t)
                r = judge.evaluate_sample(q, ans, [ctx] if ctx else [])
                faiths.append(r.faithfulness); rels.append(r.answer_relevancy)
            except Exception as exc:
                errs += 1; errmsg = str(exc)[:70]
            if throttle:
                time.sleep(throttle)
        n = max(len(lats), 1)
        results[mid] = {
            "avg_latency_s": round(sum(lats) / n, 2) if lats else None,
            "faithfulness": round(sum(faiths) / len(faiths), 3) if faiths else None,
            "relevancy": round(sum(rels) / len(rels), 3) if rels else None,
            "errors": errs, "n_ok": len(lats), "last_error": errmsg,
        }
        r = results[mid]
        print(f"  {mid:<46} lat={r['avg_latency_s']}s faith={r['faithfulness']} "
              f"rel={r['relevancy']} ok={r['n_ok']}/{len(ctxs)} {('['+errmsg+']') if errs else ''}", flush=True)

    out = Path("evaluation/results"); out.mkdir(parents=True, exist_ok=True)
    (out / "openrouter_bench_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = {k: v for k, v in results.items() if v.get("n_ok", 0) >= len(ctxs) - 1 and v.get("faithfulness")}
    print("\n=== SIRALAMA (faithfulness↓, sonra latency↑) ===")
    for mid, v in sorted(ok.items(), key=lambda kv: (-kv[1]["faithfulness"], kv[1]["avg_latency_s"] or 1e9)):
        print(f"  {v['faithfulness']:.3f} faith · {v['avg_latency_s']}s · rel {v['relevancy']} · {mid}")
    bad = {k: v for k, v in results.items() if k not in ok}
    for mid, v in bad.items():
        print(f"  SORUN: {mid} (ok={v.get('n_ok',0)}, {v.get('last_error') or v.get('error','')})")
    print(f"\nSonuç: {out/'openrouter_bench_results.json'}")


if __name__ == "__main__":
    main()
