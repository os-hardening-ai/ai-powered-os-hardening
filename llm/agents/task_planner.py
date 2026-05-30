"""
İP-6 — Görev Planlayıcı (Task Planner)

Öneri formu: "LLM tabanlı görev planlayıcı ... önerileri önem/bağımlılık
sırasına göre maddeleştirir."

Tasarım — LLM + RuleEngine hibrit:
  1. security_level → ilgili CIS Level kuralları (aday havuzu) RuleEngine'den.
  2. LLM, kullanıcı hedefine uygun kuralları SEÇER ve önceliklendirir
     (priority + rationale + risk).  → açıklanabilirlik
  3. RuleEngine seçilen kuralları DETERMINISTIK sıraya dizer (CIS bölüm no)
     ve çakışmaları (aynı config dosyası / kernel modülü) tespit eder.
  4. Sonuç: sıralı, gerekçeli, çakışma-uyarılı bir HardeningPlan.

LLM verilmezse (llm_fn=None) ya da LLM hata verirse, plan tamamen
RuleEngine'den deterministik olarak üretilir (graceful degradation).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from domain.rule_engine.rule_engine import RuleEngine, RuleConflict

logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]

# security_level → değerlendirilecek CIS Level'ları
_LEVEL_MAP: Dict[str, List[int]] = {
    "minimal": [1],
    "balanced": [1],
    "strict": [1, 2],
}

# Aday havuzu / prompt boyutu sınırı (token kontrolü)
_MAX_CANDIDATES = 60


@dataclass
class PlanItem:
    rule_id: str
    title: str
    order: int                       # uygulama sırası (1'den başlar)
    priority: int = 3                # 1=en yüksek .. 5=en düşük (LLM)
    rationale: str = ""              # neden bu kural? (LLM)
    risk: str = "medium"             # low/medium/high (LLM)
    zt_principle: str = ""           # kural metadata'sından
    nist_ref: str = ""               # kural metadata'sından


@dataclass
class HardeningPlan:
    goal: str
    os_target: str
    security_level: str
    items: List[PlanItem] = field(default_factory=list)
    conflicts: List[RuleConflict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "os_target": self.os_target,
            "security_level": self.security_level,
            "summary": self.summary,
            "items": [item.__dict__ for item in self.items],
            "conflicts": [c.__dict__ for c in self.conflicts],
            "warnings": self.warnings,
        }


class TaskPlanner:
    """
    İP-6 Görev Planlayıcı.

    Kullanım:
        engine = RuleEngine("data/rules/ubuntu_24_04_rules.yaml")
        planner = TaskPlanner(llm_fn=groq_small, rule_engine=engine)
        plan = planner.plan("SSH ve parola politikasını sıkılaştır",
                            os_target="ubuntu_24_04", security_level="strict")
    """

    def __init__(
        self,
        rule_engine: RuleEngine,
        llm_fn: Optional[LLMCallable] = None,
        debug: bool = False,
    ) -> None:
        self.rule_engine = rule_engine
        self.llm = llm_fn
        self.debug = debug

    # ── public API ────────────────────────────────────────────────────────────

    def plan(
        self,
        goal: str,
        os_target: str = "ubuntu_24_04",
        security_level: str = "balanced",
    ) -> HardeningPlan:
        candidates = self._candidate_rules(security_level)
        if not candidates:
            logger.warning("[TaskPlanner] Aday kural bulunamadı (level=%s)", security_level)
            return HardeningPlan(
                goal=goal, os_target=os_target, security_level=security_level,
                summary="Bu güvenlik seviyesi için uygun kural bulunamadı.",
            )

        # 1) LLM ile seçim + önceliklendirme (varsa)
        selections = self._llm_select(goal, candidates) if self.llm else {}

        # 2) Seçilen kural id'leri (LLM boşsa → tüm adaylar)
        if selections:
            selected_ids = [rid for rid in selections if self.rule_engine.get_rule(rid)]
        else:
            selected_ids = [r["id"] for r in candidates]

        if not selected_ids:
            selected_ids = [r["id"] for r in candidates]

        # 3) RuleEngine: deterministik sıra + çakışma tespiti
        exec_plan = self.rule_engine.get_execution_plan(selected_ids)

        # 4) PlanItem listesi (uygulama sırasına göre, metadata + LLM zenginleştirmesi)
        items: List[PlanItem] = []
        for order, rid in enumerate(exec_plan.ordered_rules, start=1):
            rule = self.rule_engine.get_rule(rid) or {}
            sel = selections.get(rid, {})
            items.append(PlanItem(
                rule_id=rid,
                title=rule.get("title", ""),
                order=order,
                priority=int(sel.get("priority", 3)),
                rationale=str(sel.get("rationale", "")).strip(),
                risk=str(sel.get("risk", rule.get("impact", "medium"))).lower(),
                zt_principle=str(rule.get("zt_principle", "")),
                nist_ref=str(rule.get("nist_ref", "")),
            ))

        summary = (
            f"{os_target} için '{goal}' hedefiyle {len(items)} kural seçildi "
            f"({security_level} seviye). {len(exec_plan.conflicts)} olası çakışma tespit edildi."
        )

        return HardeningPlan(
            goal=goal,
            os_target=os_target,
            security_level=security_level,
            items=items,
            conflicts=exec_plan.conflicts,
            warnings=exec_plan.warnings,
            summary=summary,
        )

    # ── internal helpers ────────────────────────────────────────────────────────

    def _candidate_rules(self, security_level: str) -> List[dict]:
        levels = _LEVEL_MAP.get(security_level, [1])
        seen: Dict[str, dict] = {}
        for lvl in levels:
            for rule in self.rule_engine.list_rules(level=lvl):
                seen[rule["id"]] = rule
        candidates = list(seen.values())
        return candidates[:_MAX_CANDIDATES]

    def _llm_select(self, goal: str, candidates: List[dict]) -> Dict[str, dict]:
        """LLM'e adayları verir; hedefe uygun seçim + önceliklendirme JSON'u alır."""
        catalog = "\n".join(
            f"- {r['id']}: {r.get('title', '')}" for r in candidates
        )
        prompt = (
            "Sen bir güvenlik sıkılaştırma uzmanısın. Kullanıcının hedefi için "
            "aşağıdaki CIS kurallarından UYGUN olanları seç ve önceliklendir.\n\n"
            f"HEDEF: {goal}\n\n"
            f"ADAY KURALLAR:\n{catalog}\n\n"
            "Sadece geçerli JSON dizisi döndür (markdown yok). Her öğe:\n"
            '{"rule_id": "<id>", "priority": 1-5, "risk": "low|medium|high", '
            '"rationale": "tek cümle gerekçe"}\n'
            "priority 1 = en kritik/önce uygulanmalı. Yalnızca hedefle ilgili kuralları dahil et."
        )
        try:
            raw = self.llm(prompt)  # type: ignore[misc]
            items = _parse_json_array(raw)
            result: Dict[str, dict] = {}
            for it in items:
                rid = str(it.get("rule_id", "")).strip()
                if rid:
                    result[rid] = it
            if self.debug:
                logger.info("[TaskPlanner] LLM %d kural seçti", len(result))
            return result
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("[TaskPlanner] LLM seçimi başarısız, deterministik fallback: %s", exc)
            return {}


def _parse_json_array(text: str) -> List[dict]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group())
        return [d for d in data if isinstance(d, dict)]
    except (json.JSONDecodeError, TypeError):
        return []
