from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

_logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]


@dataclass
class RAGASResult:
    question: str
    answer: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    overall: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "faithfulness": round(self.faithfulness, 3),
            "answer_relevancy": round(self.answer_relevancy, 3),
            "context_precision": round(self.context_precision, 3),
            "context_recall": round(self.context_recall, 3),
            "overall": round(self.overall, 3),
        }


@dataclass
class RAGASReport:
    samples: List[RAGASResult] = field(default_factory=list)

    def averages(self) -> Dict[str, float]:
        if not self.samples:
            return {}
        keys = ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "overall"]
        n = len(self.samples)
        return {k: round(sum(getattr(s, k) for s in self.samples) / n, 3) for k in keys}

    def print_summary(self) -> None:
        avgs = self.averages()
        print(f"\n{'='*55}")
        print("RAGAS EVALUATION SUMMARY")
        print(f"{'='*55}")
        print(f"  Samples              : {len(self.samples)}")
        for metric, val in avgs.items():
            bar = "█" * int(val * 20)
            print(f"  {metric:<22}: {val:.3f}  {bar}")
        print(f"{'='*55}\n")


class RAGASEvaluator:
    """
    LLM-as-judge RAGAS-style evaluation for the RAG pipeline.

    Metrics:
      - faithfulness      : every claim in the answer is grounded in the context
      - answer_relevancy  : the answer actually addresses the question
      - context_precision : the retrieved chunks are relevant to the question
      - context_recall    : the context contains enough info to produce the answer

    Each metric is scored 0.0–1.0 by asking the LLM a targeted prompt.
    Scores are averaged into `overall`.

    Usage:
        evaluator = RAGASEvaluator(llm_fn=llm_small)
        report = evaluator.evaluate_batch(samples, progress=True)
        report.print_summary()
    """

    def __init__(self, llm_fn: LLMCallable) -> None:
        self._llm = llm_fn

    def evaluate_sample(
        self,
        question: str,
        answer: str,
        context_chunks: List[str],
        ground_truth: Optional[str] = None,
    ) -> RAGASResult:
        ctx = "\n\n".join(f"[{i+1}]: {c[:600]}" for i, c in enumerate(context_chunks[:5]))
        faithfulness = self._ask_score(self._prompt_faithfulness(question, answer, ctx))
        relevancy = self._ask_score(self._prompt_relevancy(question, answer))
        precision = self._ask_score(self._prompt_precision(question, ctx))
        recall = self._ask_score(self._prompt_recall(question, answer, ctx))
        overall = (faithfulness + relevancy + precision + recall) / 4.0
        return RAGASResult(
            question=question,
            answer=answer,
            faithfulness=faithfulness,
            answer_relevancy=relevancy,
            context_precision=precision,
            context_recall=recall,
            overall=overall,
        )

    def evaluate_batch(
        self,
        samples: List[Dict],
        progress: bool = False,
    ) -> RAGASReport:
        """
        Args:
            samples: [{"question": str, "answer": str, "context_chunks": List[str],
                       "ground_truth": str | None}]
            progress: Print progress to stdout.
        """
        report = RAGASReport()
        for i, s in enumerate(samples):
            if progress:
                print(f"[RAGAS] {i+1}/{len(samples)}: {s['question'][:60]}")
            try:
                r = self.evaluate_sample(
                    question=s["question"],
                    answer=s["answer"],
                    context_chunks=s.get("context_chunks", []),
                    ground_truth=s.get("ground_truth"),
                )
                report.samples.append(r)
            except Exception as exc:
                _logger.warning("[RAGAS] sample %d failed: %s", i, exc)
        return report

    # ── private helpers ───────────────────────────────────────────────────────

    def _ask_score(self, prompt: str) -> float:
        try:
            raw = self._llm(prompt).strip()
            m = re.search(r"\b(1\.0|0\.\d{1,3}|[01])\b", raw)
            if m:
                return min(1.0, max(0.0, float(m.group())))
            lower = raw.lower()
            if any(w in lower for w in ("yes", "fully", "completely", "all", "evet")):
                return 1.0
            if any(w in lower for w in ("no", "none", "not", "hayır", "hiç")):
                return 0.0
        except Exception as exc:
            _logger.warning("[RAGAS] score parse error: %s", exc)
        return 0.5

    def _prompt_faithfulness(self, q: str, a: str, ctx: str) -> str:
        return (
            "Rate 0.0–1.0: What fraction of the factual claims in ANSWER are "
            "directly supported by CONTEXT? (1.0=fully grounded, 0.0=hallucinated)\n"
            f"QUESTION: {q[:300]}\nCONTEXT:\n{ctx[:1500]}\nANSWER: {a[:600]}\n"
            "Reply with a single number only."
        )

    def _prompt_relevancy(self, q: str, a: str) -> str:
        return (
            "Rate 0.0–1.0: How well does ANSWER address all aspects of QUESTION? "
            "(1.0=fully relevant, 0.0=off-topic)\n"
            f"QUESTION: {q[:300]}\nANSWER: {a[:600]}\n"
            "Reply with a single number only."
        )

    def _prompt_precision(self, q: str, ctx: str) -> str:
        return (
            "Rate 0.0–1.0: What fraction of the retrieved CONTEXT chunks are "
            "relevant to answering QUESTION? (1.0=all relevant, 0.0=none relevant)\n"
            f"QUESTION: {q[:300]}\nCONTEXT:\n{ctx[:1500]}\n"
            "Reply with a single number only."
        )

    def _prompt_recall(self, q: str, a: str, ctx: str) -> str:
        return (
            "Rate 0.0–1.0: Does the CONTEXT provide enough information to produce "
            "the ANSWER? (1.0=fully sufficient, 0.0=cannot derive answer from context)\n"
            f"QUESTION: {q[:300]}\nCONTEXT:\n{ctx[:1500]}\nANSWER: {a[:600]}\n"
            "Reply with a single number only."
        )
