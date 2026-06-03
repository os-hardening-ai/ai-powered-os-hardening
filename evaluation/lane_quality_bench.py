"""
LANE KALİTE (faithfulness) KIYASI — 10 model, 3'er 3'er PARALEL.

cerebras gpt-oss-120b (primary) + OpenRouter ücretli adaylar. RAG bağlamı bir kez çekilir.
Judge = NOVITA (kotasız → temiz skor). Modeller 3'erli batch'lerde eşzamanlı (ThreadPoolExecutor).
Çıktı: faithfulness/relevancy/latency/err — lane sıralaması için.
"""
from __future__ import annotations
import json, os, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

QUESTIONS = [
    ("SSH için PermitRootLogin nasıl devre dışı bırakılır", "ubuntu_24_04"),
    ("Parola minimum uzunluğu ve karmaşıklığı nasıl zorunlu kılınır", "ubuntu_24_04"),
    ("auditd ile zaman değişikliklerini izleyen kural nasıl eklenir", "ubuntu_24_04"),
    ("UFW ile varsayılan deny politikası nasıl ayarlanır", "ubuntu_24_04"),
    ("Windows 11'de SMBv1 nasıl devre dışı bırakılır", "windows_11"),
]

# adaylar: (etiket, "DIRECT:cerebras"|"DIRECT:sambanova"|openrouter_model_id)
MODELS = [
    ("cerebras:gpt-oss-120b", "DIRECT:cerebras"),
    ("sambanova:gpt-oss-120b", "DIRECT:sambanova"),
    ("or:deepseek-v4-flash", "deepseek/deepseek-v4-flash"),
    ("or:gemini-2.5-flash-lite", "google/gemini-2.5-flash-lite"),
    ("or:gemini-2.5-flash", "google/gemini-2.5-flash"),
    ("or:gemini-3.1-flash-lite", "google/gemini-3.1-flash-lite"),
    ("or:llama-3.3-70b", "meta-llama/llama-3.3-70b-instruct"),
    ("or:qwen3-next-80b", "qwen/qwen3-next-80b-a3b-instruct"),
    ("or:deepseek-chat", "deepseek/deepseek-chat"),
    ("or:glm-4.5-air", "z-ai/glm-4.5-air"),
    ("or:hy3-preview", "tencent/hy3-preview"),
]


def _client(model_id):
    if model_id == "DIRECT:cerebras":
        from llm.clients.openai_compatible_client import get_large_cerebras_llm
        return get_large_cerebras_llm()
    if model_id == "DIRECT:sambanova":
        from llm.clients.openai_compatible_client import get_large_sambanova_llm
        return get_large_sambanova_llm()
    from llm.clients.openai_compatible_client import OpenAICompatibleClient
    return OpenAICompatibleClient(provider="openrouter", model_name=model_id,
        api_key=os.environ.get("OPENROUTER_API_KEY", ""), base_url="https://openrouter.ai/api/v1",
        temperature=0.3, timeout=45.0, max_retries=1)


def _run_model(label, model_id, ctxs, grounding, judge):
    try:
        llm = _client(model_id)
    except Exception as e:
        return label, {"faithfulness": None, "errors": len(ctxs), "setup_error": str(e)[:60]}
    f, r, lat, errs = [], [], [], 0
    for q, ctx in ctxs:
        prompt = (f"SORU: '{q}' için kısa, teknik sıkılaştırma önerisi yaz.\n\n"
                  f"CIS BENCHMARK REFERANSLARI:\n{ctx}\n{grounding}\n\nYANIT:")
        try:
            t = time.perf_counter(); ans = llm(prompt); lat.append(time.perf_counter() - t)
            sc = judge.evaluate_sample(q, ans, [ctx])
            f.append(sc.faithfulness); r.append(sc.answer_relevancy)
        except Exception:
            errs += 1
        time.sleep(1)
    n = max(len(f), 1)
    res = {"faithfulness": round(sum(f)/n, 3) if f else None,
           "relevancy": round(sum(r)/len(r), 3) if r else None,
           "avg_latency_s": round(sum(lat)/max(len(lat), 1), 2) if lat else None,
           "errors": errs, "n_ok": len(f)}
    print(f"  [bitti] {label:<30} faith={res['faithfulness']} rel={res['relevancy']} "
          f"lat={res['avg_latency_s']}s err={errs}", flush=True)
    return label, res


def main():
    from evaluation import force_utf8_output; force_utf8_output()
    import logging; logging.disable(logging.CRITICAL)
    from llm.prompts.simple_prompts import GROUNDING_DIRECTIVE
    from evaluation.ragas_evaluator import RAGASEvaluator
    from llm.clients.novita_llm_client import get_small_novita_llm
    from llm.rag.integration import RAGContextBuilder

    judge = RAGASEvaluator(llm_fn=get_small_novita_llm())
    print("Bağlamlar çekiliyor...")
    ctxs = []
    for q, osv in QUESTIONS:
        try:
            rag = RAGContextBuilder(top_k=5, min_score=0.4, os_version=osv)
            _c, ch = rag.retrieve_balanced(q)
            ctxs.append((q, "\n\n".join(c.get("text", "") for c in ch)))
        except Exception:
            ctxs.append((q, ""))

    print(f"{len(MODELS)} model, 3'er paralel batch, {len(QUESTIONS)} soru/model\n")
    results = {}
    # 3'erli batch'ler — eşzamanlı
    for i in range(0, len(MODELS), 3):
        batch = MODELS[i:i+3]
        print(f">>> batch {i//3+1}: {[b[0] for b in batch]}", flush=True)
        with ThreadPoolExecutor(max_workers=3) as ex:
            futs = [ex.submit(_run_model, lbl, mid, ctxs, GROUNDING_DIRECTIVE, judge) for lbl, mid in batch]
            for fu in futs:
                label, res = fu.result()
                results[label] = res

    print("\n" + "=" * 70 + "\nKALİTE SIRALAMA (faithfulness↓):")
    ok = {k: v for k, v in results.items() if v.get("faithfulness") is not None}
    for label, v in sorted(ok.items(), key=lambda kv: -(kv[1]["faithfulness"] or 0)):
        print(f"  {v['faithfulness']:.3f} faith · {v['relevancy']} rel · {v['avg_latency_s']:>5}s · err={v['errors']} · {label}")
    bad = {k: v for k, v in results.items() if k not in ok}
    for label, v in bad.items():
        print(f"  SORUN: {label} (err={v['errors']}, {v.get('setup_error','')})")
    Path("evaluation/results").mkdir(parents=True, exist_ok=True)
    Path("evaluation/results/lane_quality_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSonuç: evaluation/results/lane_quality_results.json")


if __name__ == "__main__":
    main()
