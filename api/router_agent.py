"""
Agentic AI endpoints — İP-6 (Görev Planlayıcı) ve İP-7 (multi-step ajan).

POST /api/agent/plan    → TaskPlanner: hedefe uygun kuralları seç+sırala (plan)
POST /api/agent/harden  → HardeningAgent: plan→script üret→self-verify (uçtan uca)

LLM erişilemezse her iki uç da deterministik (RuleEngine + ArtifactGenerator)
çalışmaya devam eder.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.errors import APIError, ErrorCode

router = APIRouter()

_UBUNTU_RULES_PATH = Path("data/rules/ubuntu_24_04_rules.yaml")

# Lazy singletons
_rule_engine = None
_small_llm: Optional[object] = None
_small_llm_resolved = False


def _get_rule_engine():
    global _rule_engine
    if _rule_engine is None:
        from domain.rule_engine.rule_engine import RuleEngine
        if not _UBUNTU_RULES_PATH.exists():
            raise APIError(
                status_code=503,
                error_code=ErrorCode.SERVICE_UNAVAILABLE,
                message="Rules YAML not found — ensure data/rules/ubuntu_24_04_rules.yaml exists",
                details={"path": str(_UBUNTU_RULES_PATH)},
            )
        _rule_engine = RuleEngine(_UBUNTU_RULES_PATH)
    return _rule_engine


def _get_small_llm():
    """Best-effort small LLM callable; None if providers unavailable (→ deterministic)."""
    global _small_llm, _small_llm_resolved
    if not _small_llm_resolved:
        _small_llm_resolved = True
        try:
            from llm.clients import get_llm_clients
            small, _large = get_llm_clients()
            _small_llm = small
        except Exception:
            _small_llm = None
    return _small_llm


# ── Schemas ──────────────────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    goal: str = Field(..., min_length=1, max_length=500,
                      examples=["SSH ve parola politikasını sıkılaştır"])
    os_target: str = Field("ubuntu_24_04", max_length=50)
    security_level: Literal["minimal", "balanced", "strict"] = "balanced"


class PlanItemResponse(BaseModel):
    rule_id: str
    title: str
    order: int
    priority: int
    rationale: str
    risk: str
    zt_principle: str
    nist_ref: str


class ConflictResponse(BaseModel):
    rule_a: str
    rule_b: str
    conflict_type: str
    resource: str
    description: str


class PlanResponse(BaseModel):
    goal: str
    os_target: str
    security_level: str
    summary: str
    items: List[PlanItemResponse]
    conflicts: List[ConflictResponse]
    warnings: List[str]


class HardenRequest(PlanRequest):
    format: Literal["bash", "powershell", "ansible", "reg", "gpo"] = "bash"


class AgentStepResponse(BaseModel):
    name: str
    tool: str
    detail: str
    ok: bool


class HardenResponse(BaseModel):
    success: bool
    goal: str
    os_target: str
    format: str
    summary: str
    rule_count: int
    artifact_content: str
    issues: List[str]
    steps: List[AgentStepResponse]
    plan: PlanResponse


def _plan_to_response(plan) -> PlanResponse:
    return PlanResponse(
        goal=plan.goal,
        os_target=plan.os_target,
        security_level=plan.security_level,
        summary=plan.summary,
        items=[PlanItemResponse(**vars(i)) for i in plan.items],
        conflicts=[ConflictResponse(**vars(c)) for c in plan.conflicts],
        warnings=plan.warnings,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/agent/plan", response_model=PlanResponse, tags=["agents"])
async def agent_plan(body: PlanRequest):
    """İP-6 — Görev Planlayıcı: hedefe uygun CIS kurallarını seç + sırala + çakışma tespiti."""
    try:
        from llm.agents.task_planner import TaskPlanner
        planner = TaskPlanner(rule_engine=_get_rule_engine(), llm_fn=_get_small_llm())
        plan = planner.plan(body.goal, os_target=body.os_target, security_level=body.security_level)
        return _plan_to_response(plan)
    except APIError:
        raise
    except Exception as exc:
        raise APIError(
            status_code=500, error_code=ErrorCode.PIPELINE_ERROR,
            message=f"Task planner failed: {exc}", details={},
        )


@router.post("/agent/harden", response_model=HardenResponse, tags=["agents"])
async def agent_harden(body: HardenRequest):
    """İP-7 — Multi-step ajan: plan → script üret → self-verify → (gerekirse) refine."""
    try:
        from llm.agents.hardening_agent import HardeningAgent
        agent = HardeningAgent(rule_engine=_get_rule_engine(), llm_fn=_get_small_llm())
        res = agent.run(
            body.goal, os_target=body.os_target,
            security_level=body.security_level, fmt=body.format,
        )
        return HardenResponse(
            success=res.success,
            goal=res.goal,
            os_target=res.os_target,
            format=res.fmt,
            summary=res.summary,
            rule_count=res.artifact.rule_count if res.artifact else 0,
            artifact_content=res.artifact.content if res.artifact else "",
            issues=res.issues,
            steps=[AgentStepResponse(**vars(s)) for s in res.steps],
            plan=_plan_to_response(res.plan) if res.plan else PlanResponse(
                goal=res.goal, os_target=res.os_target, security_level=body.security_level,
                summary="", items=[], conflicts=[], warnings=[],
            ),
        )
    except APIError:
        raise
    except Exception as exc:
        raise APIError(
            status_code=500, error_code=ErrorCode.PIPELINE_ERROR,
            message=f"Hardening agent failed: {exc}", details={},
        )
