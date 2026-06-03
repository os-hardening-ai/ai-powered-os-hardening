"""
GROUNDING-LANE MODEL ARAŞTIRMASI — geniş sorgularda en iyi ground'layan modeli bul.

İP-5 A/B gösterdi: üretim modeli broad-grounding'de belirleyici (cerebras 0.00 vs gemini 0.76).
Bu bench grounding-lane adaylarını GENİŞ sorgularda (BROAD_QUESTIONS) faithfulness+relevancy ile
kıyaslar. Üretim = OpenRouter (kotasız, $5); judge = Novita (kotasız). retrieve_balanced (sabit).

Çalıştırma:  python -m evaluation.grounding_model_bench
"""
from __future__ import annotations
import json, os, time
from pathlib import Path

CANDIDATES = [
    ("gemini-3.1-flash-lite", "google/gemini-3.1-flash-lite"),
    ("gemini-2.5-flash-lite", "google/gemini-2.5-flash-lite"),
    ("qwen3-next-80b", "qwen/qwen3-next-80b-a3b-instruct"),
    ("deepseek-v4-flash", "deepseek/deepseek-v4-flash"),
]


def main():
    from evaluation import force_utf8_output; force_utf8_output()
    import logging; logging.disable(logging.CRITICAL)
    from evaluation.eval_dataset import BROAD_QUESTIONS
    from evaluation.ragas_evaluator import RAGASEvaluator
    from llm.clients.novita_llm_client import get_small_novita_llm
    from llm.clients.openai_compatible_client import OpenAICompatibleClient
    from llm.rag.integration import RAGContextBuilder
    from llm.prompts.simple_prompts import GROUNDING_DIRECTIVE

    judge = RAGASEvaluator(llm_fn=get_small_novita_llm())
    key = os.environ.get("OPENROUTER_API_KEY", "")

    # Bağlamları bir kez çek (adil — tüm modeller aynı bağlam)
    print("Geniş sorgu bağlamları çekiliyor...")
    ctxs = []
    for q, osv in BROAD_QUESTIONS:
        try:
            rag = RAGContextBuilder(top_k=5, min_score=0.4, os_version=osv)
            _c, ch = rag.retrieve_balanced(q)
            ctxs.append((q, "\n\n".join(c.get("text", "") for c in ch)))
        except Exception:
            ctxs.append((q, ""))

    results = {}
    for label, mid in CANDIDATES:
        try:
            llm = OpenAICompatibleClient(provider="openrouter", model_name=mid, api_key=key,
                base_url="https://openrouter.ai/api/v1", temperature=0.3, timeout=45.0, max_retries=1)
        except Exception as e:
            results[label] = {"faithfulness": None, "error": str(e)[:50]}; continue
        f, r, lat, errs = [], [], [], 0
        for q, ctx in ctxs:
            p = (f"SORU: '{q}' için kısa, teknik sıkılaştırma önerisi yaz.\n\n"
                 f"CIS BENCHMARK REFERANSLARI:\n{ctx}\n{GROUNDING_DIRECTIVE}\n\nYANIT:")
            try:
                t = time.perf_counter(); ans = llm(p); lat.append(time.perf_counter() - t)
                sc = judge.evaluate_sample(q, ans, [ctx])
                f.append(sc.faithfulness); r.append(sc.answer_relevancy)
            except Exception:
                errs += 1
            time.sleep(2)
        n = max(len(f), 1)
        results[label] = {"faithfulness": round(sum(f)/n, 3) if f else None,
                          "relevancy": round(sum(r)/len(r), 3) if r else None,
                          "avg_latency_s": round(sum(lat)/max(len(lat), 1), 2) if lat else None, "errors": errs}
        v = results[label]
        print(f"  {label:<24} faith={v['faithfulness']} rel={v['relevancy']} lat={v['avg_latency_s']}s err={errs}", flush=True)

    print("\n=== GROUNDING-LANE SIRALAMA (geniş sorgu faithfulness↓) ===")
    ok = {k: v for k, v in results.items() if v.get("faithfulness") is not None}
    for label, v in sorted(ok.items(), key=lambda kv: -(kv[1]["faithfulness"] or 0)):
        print(f"  {v['faithfulness']:.3f} faith · {v['relevancy']} rel · {v['avg_latency_s']}s · {label}")
    Path("evaluation/results").mkdir(parents=True, exist_ok=True)
    Path("evaluation/results/grounding_model_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
