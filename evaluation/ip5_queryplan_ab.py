"""
İP-5 ÇÖZÜM KANITI — query-planning (multi-query) groundedness'i yükseltiyor mu?

Geniş/çok-alanlı sorgularda (BROAD_QUESTIONS) iki retrieval modunu A/B kıyaslar:
  A) retrieve_balanced  — tek sorgu, top_k chunk (mevcut İP-5 eval yolu)
  B) retrieve_multi      — QueryPlanner ile alt-sorgulara böl + birleşik retrieve (production complex yolu)
Her ikisinde aynı LLM (cerebras) + GROUNDING_DIRECTIVE üretir; judge=Novita (kotasız) faithfulness.

Hipotez: B (query-planning) > A → İP-5 geniş-sorgu çözümü = multi-query.
Çalıştırma:  python -m evaluation.ip5_queryplan_ab
"""
from __future__ import annotations
import json, time
from pathlib import Path


def main():
    from evaluation import force_utf8_output; force_utf8_output()
    import logging; logging.disable(logging.CRITICAL)
    from evaluation.eval_dataset import BROAD_QUESTIONS
    from evaluation.ragas_evaluator import RAGASEvaluator
    from llm.clients.novita_llm_client import get_small_novita_llm
    from llm.clients.openai_compatible_client import OpenAICompatibleClient
    from llm.rag.integration import RAGContextBuilder
    from llm.prompts.simple_prompts import GROUNDING_DIRECTIVE
    from rag.query.query_planner import QueryPlanner
    import os as _os

    judge = RAGASEvaluator(llm_fn=get_small_novita_llm())
    # Üretim modeli KOTASIZ (gemini/OpenRouter, $5 kredi) — cerebras rate-limit'i ölçümü bozmasın.
    # Retrieval-modu (balanced vs multi) DEĞİŞKENİ izole edilir; gen modeli sabit.
    gen = OpenAICompatibleClient(provider="openrouter", model_name="google/gemini-3.1-flash-lite",
        api_key=_os.environ.get("OPENROUTER_API_KEY", ""), base_url="https://openrouter.ai/api/v1",
        temperature=0.3, timeout=45.0, max_retries=1)
    planner = QueryPlanner(llm_fn=get_small_novita_llm())

    def answer(ctx_txt, q):
        p = (f"SORU: '{q}' için kısa, teknik sıkılaştırma önerisi yaz.\n\n"
             f"CIS BENCHMARK REFERANSLARI:\n{ctx_txt}\n{GROUNDING_DIRECTIVE}\n\nYANIT:")
        return gen(p)

    rows = []
    for q, osv in BROAD_QUESTIONS:
        try:
            rag = RAGContextBuilder(top_k=5, min_score=0.4, os_version=osv)
            # A) balanced (tek sorgu)
            _c, ch_a = rag.retrieve_balanced(q)
            ctx_a = "\n\n".join(c.get("text", "") for c in ch_a)
            fa = judge.evaluate_sample(q, answer(ctx_a, q), [ctx_a]).faithfulness
            time.sleep(2)
            # B) multi-query (query-planning)
            plan = planner.plan(q)
            _c2, ch_b = rag.retrieve_multi(plan.all_queries(), original_query=q)
            ctx_b = "\n\n".join(c.get("text", "") for c in ch_b)
            fb = judge.evaluate_sample(q, answer(ctx_b, q), [ctx_b]).faithfulness
            rows.append((q, fa, len(ch_a), fb, len(ch_b)))
            print(f"  balanced={fa:.2f}({len(ch_a)}ch)  multi={fb:.2f}({len(ch_b)}ch)  {q[:38]}", flush=True)
            time.sleep(2)
        except Exception as e:
            print(f"  HATA {q[:38]}: {str(e)[:50]}", flush=True)
    if rows:
        a = sum(r[1] for r in rows) / len(rows)
        b = sum(r[3] for r in rows) / len(rows)
        print(f"\n=== GENİŞ SORGU groundedness: balanced {a:.3f} → multi-query {b:.3f} (Δ {b-a:+.3f}) ===")
        Path("evaluation/results").mkdir(parents=True, exist_ok=True)
        Path("evaluation/results/ip5_queryplan_ab.json").write_text(json.dumps(
            {"balanced_avg": round(a, 3), "multiquery_avg": round(b, 3), "delta": round(b - a, 3),
             "rows": [{"q": r[0], "balanced": r[1], "multi": r[3]} for r in rows]},
            ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
