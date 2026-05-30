from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, List

logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]


@dataclass
class QueryPlan:
    original: str
    subqueries: List[str] = field(default_factory=list)
    hyde_passages: List[str] = field(default_factory=list)
    stepback: List[str] = field(default_factory=list)

    def all_queries(self) -> List[str]:
        """All queries including original — used for fan-out retrieval."""
        return [self.original] + self.subqueries + self.hyde_passages + self.stepback

    def extra_queries(self) -> List[str]:
        """Expanded queries only (without original)."""
        return self.subqueries + self.hyde_passages + self.stepback


class QueryPlanner:
    """
    Decomposes a user query into multiple retrieval strategies:

    - Subqueries  : breaks a compound question into focused atomic queries
    - HyDE        : generates a hypothetical answer passage whose embedding
                    aligns better with stored CIS chunks (dense retrieval boost)
    - Stepback    : generalises the query to retrieve broader context

    Uses the existing sync LLM callable (llm_small is recommended — fast + cheap).
    All LLM calls are best-effort: failures are logged and silently skipped.
    """

    def __init__(
        self,
        llm_fn: LLMCallable,
        enable_subqueries: bool = True,
        enable_hyde: bool = True,
        enable_stepback: bool = True,
        max_subqueries: int = 2,
    ) -> None:
        self._llm = llm_fn
        self.enable_subqueries = enable_subqueries
        self.enable_hyde = enable_hyde
        self.enable_stepback = enable_stepback
        self.max_subqueries = max_subqueries

    def plan(self, query: str) -> QueryPlan:
        from concurrent.futures import ThreadPoolExecutor
        plan = QueryPlan(original=query)

        tasks: dict = {}
        with ThreadPoolExecutor(max_workers=3) as pool:
            if self.enable_subqueries:
                tasks["subqueries"] = pool.submit(self._decompose, query)
            if self.enable_hyde:
                tasks["hyde"] = pool.submit(self._generate_hyde, query)
            if self.enable_stepback:
                tasks["stepback"] = pool.submit(self._stepback, query)

        if "subqueries" in tasks:
            try:
                plan.subqueries = tasks["subqueries"].result()
            except Exception as exc:
                logger.warning("[QueryPlanner] subquery decomposition failed: %s", exc)

        if "hyde" in tasks:
            try:
                plan.hyde_passages = tasks["hyde"].result()
            except Exception as exc:
                logger.warning("[QueryPlanner] HyDE generation failed: %s", exc)

        if "stepback" in tasks:
            try:
                plan.stepback = tasks["stepback"].result()
            except Exception as exc:
                logger.warning("[QueryPlanner] stepback failed: %s", exc)

        logger.debug(
            "[QueryPlanner] query='%s' → subs=%d hyde=%d stepback=%d",
            query[:60],
            len(plan.subqueries),
            len(plan.hyde_passages),
            len(plan.stepback),
        )
        return plan

    # ── private helpers ──────────────────────────────────────────────────────

    def _decompose(self, query: str) -> List[str]:
        prompt = (
            f"Break this OS security question into {self.max_subqueries} focused sub-questions.\n"
            f"Return ONLY a JSON array of strings — no markdown, no explanation.\n"
            f"Question: {query}"
        )
        resp = self._llm(prompt)
        return _parse_json_list(resp, self.max_subqueries)

    def _generate_hyde(self, query: str) -> List[str]:
        prompt = (
            "Write one short hypothetical answer passage (3-4 sentences) that would "
            "answer this OS hardening question as if quoting a CIS Benchmark.\n"
            "Return ONLY a JSON array containing one string — no markdown.\n"
            f"Question: {query}"
        )
        resp = self._llm(prompt)
        return _parse_json_list(resp, 1)

    def _stepback(self, query: str) -> List[str]:
        prompt = (
            "Rewrite this question as a broader, more general question to retrieve "
            "additional context. Return ONLY the question text, nothing else.\n"
            f"Question: {query}"
        )
        resp = self._llm(prompt)
        text = resp.strip().strip('"\'')
        return [text] if len(text) > 10 else []


def _parse_json_list(text: str, max_items: int) -> List[str]:
    try:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            items = json.loads(match.group())
            return [str(x) for x in items if isinstance(x, str)][:max_items]
    except Exception:
        pass
    return []
