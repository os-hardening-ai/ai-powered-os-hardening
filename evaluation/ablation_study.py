from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

_logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]

DEFAULT_QUESTIONS = [
    "Ubuntu 24.04'te SSH sıkılaştırma nasıl yapılır?",
    "CIS Benchmark Level 1 kernel modülü kuralları nelerdir?",
    "Dosya sistemi izinleri nasıl güvenli hale getirilir?",
    "UFW güvenlik duvarı yapılandırması nasıl yapılır?",
    "PAM parola politikası nasıl ayarlanır?",
    "Audit logging nasıl etkinleştirilir?",
    "Cron job güvenliği nasıl sağlanır?",
]


@dataclass
class AblationConfig:
    name: str
    use_hybrid: bool = False
    use_mmr: bool = False
    use_query_plan: bool = False
    top_k: int = 5
    min_score: float = 0.5

    @classmethod
    def baseline(cls) -> "AblationConfig":
        return cls("baseline")

    @classmethod
    def plus_hybrid(cls) -> "AblationConfig":
        return cls("+hybrid", use_hybrid=True)

    @classmethod
    def plus_mmr(cls) -> "AblationConfig":
        return cls("+mmr", use_mmr=True)

    @classmethod
    def plus_queryplan(cls) -> "AblationConfig":
        return cls("+queryplan", use_query_plan=True)

    @classmethod
    def full(cls) -> "AblationConfig":
        return cls("full", use_hybrid=True, use_mmr=True, use_query_plan=True)


@dataclass
class AblationSample:
    question: str
    config_name: str
    num_chunks: int
    max_score: float
    latency_s: float


@dataclass
class AblationReport:
    config_name: str
    samples: List[AblationSample] = field(default_factory=list)

    def summary(self) -> Dict[str, float]:
        if not self.samples:
            return {}
        n = len(self.samples)
        return {
            "avg_chunks": sum(s.num_chunks for s in self.samples) / n,
            "avg_max_score": sum(s.max_score for s in self.samples) / n,
            "avg_latency_s": sum(s.latency_s for s in self.samples) / n,
        }


class AblationStudy:
    """
    Ablation study comparing 5 RAG pipeline configurations.

    Configurations:
      baseline   — plain dense retrieval, no enhancements
      +hybrid    — +BM25 in-context hybrid scoring
      +mmr       — +MMR diversity reranking
      +queryplan — +query planning (subqueries + HyDE + stepback)
      full       — all enhancements enabled

    Measures: avg retrieved chunks, avg max relevance score, avg latency.

    Usage:
        study = AblationStudy(llm_fn=llm_small)
        reports = study.run(questions=my_questions)
        AblationStudy.print_report(reports)
    """

    CONFIGS = [
        AblationConfig.baseline(),
        AblationConfig.plus_hybrid(),
        AblationConfig.plus_mmr(),
        AblationConfig.plus_queryplan(),
        AblationConfig.full(),
    ]

    def __init__(self, llm_fn: LLMCallable) -> None:
        self._llm = llm_fn

    def _run_single(self, question: str, cfg: AblationConfig) -> AblationSample:
        from llm.rag.integration import RAGContextBuilder
        from rag.query.query_planner import QueryPlanner

        start = time.monotonic()
        try:
            rag = RAGContextBuilder(
                top_k=cfg.top_k,
                min_score=cfg.min_score,
                use_hybrid=cfg.use_hybrid,
                use_mmr=cfg.use_mmr,
            )
            if cfg.use_query_plan:
                planner = QueryPlanner(llm_fn=self._llm)
                plan = planner.plan(question)
                _, raw = rag.retrieve_multi(plan.all_queries(), original_query=question)
            else:
                _, raw = rag.retrieve_balanced(question)

            latency = time.monotonic() - start
            max_score = max((r.get("score", 0.0) for r in raw), default=0.0)
            return AblationSample(
                question=question, config_name=cfg.name,
                num_chunks=len(raw), max_score=max_score, latency_s=latency,
            )
        except Exception as exc:
            _logger.warning("[Ablation] %s / '%s' failed: %s", cfg.name, question[:40], exc)
            return AblationSample(
                question=question, config_name=cfg.name,
                num_chunks=0, max_score=0.0, latency_s=time.monotonic() - start,
            )

    def run(
        self,
        questions: Optional[List[str]] = None,
        configs: Optional[List[AblationConfig]] = None,
    ) -> List[AblationReport]:
        questions = questions or DEFAULT_QUESTIONS
        configs = configs or self.CONFIGS
        reports: Dict[str, AblationReport] = {c.name: AblationReport(c.name) for c in configs}

        for q in questions:
            _logger.info("[Ablation] Question: '%s'", q[:55])
            for cfg in configs:
                sample = self._run_single(q, cfg)
                reports[cfg.name].samples.append(sample)

        return list(reports.values())

    @staticmethod
    def print_report(reports: List[AblationReport]) -> None:
        print(f"\n{'='*65}")
        print("ABLATION STUDY RESULTS")
        print(f"{'='*65}")
        print(f"{'Config':<15} {'Avg Chunks':>11} {'Avg MaxScore':>13} {'Avg Latency':>12}")
        print("-" * 55)
        for r in reports:
            s = r.summary()
            if not s:
                continue
            print(
                f"{r.config_name:<15} {s['avg_chunks']:>11.1f} "
                f"{s['avg_max_score']:>13.3f} {s['avg_latency_s']:>11.2f}s"
            )
        print(f"{'='*65}\n")
