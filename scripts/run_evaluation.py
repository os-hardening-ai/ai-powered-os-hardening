"""
CLI script — RAGAS evaluation + Ablation study.

Usage:
    python scripts/run_evaluation.py --mode ragas
    python scripts/run_evaluation.py --mode ablation
    python scripts/run_evaluation.py --mode both
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _get_llm():
    from llm.clients import get_llm_clients
    llm_small, _ = get_llm_clients()
    return llm_small


def run_ablation() -> None:
    print("[Ablation] Initialising...")
    from evaluation.ablation_study import AblationStudy
    llm = _get_llm()
    study = AblationStudy(llm_fn=llm)
    reports = study.run()
    AblationStudy.print_report(reports)

    # Save JSON results
    out = [
        {"config": r.config_name, "summary": r.summary(),
         "samples": [vars(s) for s in r.samples]}
        for r in reports
    ]
    Path("logs/ablation_results.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("[Ablation] Results saved to logs/ablation_results.json")


def run_ragas() -> None:
    print("[RAGAS] Running evaluation on sample questions...")
    from evaluation.ragas_evaluator import RAGASEvaluator
    from llm.rag.integration import RAGContextBuilder
    from rag.query.query_planner import QueryPlanner

    llm = _get_llm()
    evaluator = RAGASEvaluator(llm_fn=llm)
    rag = RAGContextBuilder(top_k=5, min_score=0.5, use_hybrid=True, use_mmr=True)
    planner = QueryPlanner(llm_fn=llm)

    questions = [
        "Ubuntu 24.04'te SSH sıkılaştırma nasıl yapılır?",
        "CIS Benchmark Level 1 kernel modülü kuralları nelerdir?",
        "PAM parola politikası nasıl ayarlanır?",
        "Audit logging nasıl etkinleştirilir?",
        "UFW güvenlik duvarı yapılandırması nasıl yapılır?",
    ]

    samples = []
    for q in questions:
        print(f"  RAG retrieval: {q[:55]}...")
        plan = planner.plan(q)
        _, raw = rag.retrieve_multi(plan.all_queries(), original_query=q)
        context_chunks = [r.get("text", "") for r in raw]
        # Use a placeholder answer (real eval would use actual pipeline output)
        answer_placeholder = (
            "Bu soruyu cevaplamak için CIS Benchmark yönergeleri kullanılmaktadır."
        )
        samples.append({
            "question": q,
            "answer": answer_placeholder,
            "context_chunks": context_chunks,
        })

    report = evaluator.evaluate_batch(samples, progress=True)
    report.print_summary()

    out = {
        "averages": report.averages(),
        "samples": [{"question": s.question, **s.to_dict()} for s in report.samples],
    }
    Path("logs/ragas_results.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("[RAGAS] Results saved to logs/ragas_results.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAGAS or Ablation evaluation")
    parser.add_argument(
        "--mode", choices=["ragas", "ablation", "both"], default="both",
        help="Which evaluation to run",
    )
    args = parser.parse_args()

    Path("logs").mkdir(exist_ok=True)

    if args.mode in ("ablation", "both"):
        run_ablation()
    if args.mode in ("ragas", "both"):
        run_ragas()


if __name__ == "__main__":
    main()
