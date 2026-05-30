from __future__ import annotations
import asyncio
import threading
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from api.errors import APIError, ErrorCode, raise_internal_error

router = APIRouter()

_OS_RULES_PATHS: dict[str, Path] = {
    "ubuntu_24_04": Path("data/rules/ubuntu_24_04_rules.yaml"),
    "ubuntu_22_04": Path("data/rules/ubuntu_24_04_rules.yaml"),  # same benchmark
    "windows_11": Path("data/rules/windows_11_desktop_rules.yaml"),
    "windows_server_2025": Path("data/rules/windows_server_2025_rules.yaml"),
}

_rule_engines: dict[str, object] = {}
_artifact_gen = None
_init_lock = threading.Lock()


def _get_rule_engine(os_key: str = "ubuntu_24_04"):
    path = _OS_RULES_PATHS.get(os_key)
    if path is None or not path.exists():
        return None
    if os_key not in _rule_engines:
        with _init_lock:
            if os_key not in _rule_engines:
                from domain.rule_engine.rule_engine import RuleEngine
                _rule_engines[os_key] = RuleEngine(path)
    return _rule_engines[os_key]


def _get_artifact_gen():
    global _artifact_gen
    if _artifact_gen is None:
        with _init_lock:
            if _artifact_gen is None:  # double-checked locking
                from domain.artifact_generator.generator import ArtifactGenerator
                _artifact_gen = ArtifactGenerator()
    return _artifact_gen


# ── Schemas ──────────────────────────────────────────────────────────────────

class RulePlanRequest(BaseModel):
    rule_ids: List[str] = Field(
        ..., min_length=1, max_length=100,
        description="CIS rule IDs (e.g. ['1.1.1.1', '5.2.1'])",
        examples=[["1.1.1.1", "1.1.1.2", "5.2.1"]],
    )


class ConflictResponse(BaseModel):
    rule_a: str
    rule_b: str
    conflict_type: str
    resource: str
    description: str


class ExecutionPlanResponse(BaseModel):
    ordered_rules: List[str]
    conflicts: List[ConflictResponse]
    warnings: List[str]
    rule_count: int


class ArtifactRequest(BaseModel):
    rule_ids: List[str] = Field(
        ..., min_length=1, max_length=50,
        description="CIS rule IDs to include in the artifact",
        examples=[["1.1.1.1", "1.1.1.2", "5.2.1"]],
    )
    format: Literal["bash", "powershell", "ansible", "reg", "gpo"] = Field(
        "bash",
        description="Output format: bash | powershell | ansible | reg | gpo",
    )
    os_target: str = Field(
        "ubuntu_24_04",
        max_length=50,
        description="Target OS identifier",
        examples=["ubuntu_24_04"],
    )
    security_level: Literal["minimal", "balanced", "strict"] = "balanced"


class ArtifactResponse(BaseModel):
    format: str
    content: str
    rule_count: int
    os_target: str
    warnings: List[str]


class RuleListResponse(BaseModel):
    rules: List[dict]
    total: int
    offset: int
    limit: int


# ── Rule Engine Endpoints ─────────────────────────────────────────────────────

@router.post("/rules/plan", response_model=ExecutionPlanResponse, tags=["domain"])
async def get_execution_plan(body: RulePlanRequest):
    """
    Compute an ordered execution plan for the given CIS rule IDs.
    Rules are sorted by section number. Conflicts (same config file or kernel module)
    are reported with warnings.
    """
    try:
        engine = _get_rule_engine("ubuntu_24_04")
        plan = engine.get_execution_plan(body.rule_ids)
        return ExecutionPlanResponse(
            ordered_rules=plan.ordered_rules,
            conflicts=[ConflictResponse(**vars(c)) for c in plan.conflicts],
            warnings=plan.warnings,
            rule_count=len(plan.ordered_rules),
        )
    except APIError:
        raise
    except Exception as exc:
        raise_internal_error("rules_plan", exc, error_code=ErrorCode.PIPELINE_ERROR)


@router.post("/rules/conflicts", response_model=List[ConflictResponse], tags=["domain"])
async def detect_conflicts(body: RulePlanRequest):
    """
    Detect conflicts between the given rule IDs.
    A conflict exists when two rules write to the same config file or manage the same kernel module.
    """
    try:
        engine = _get_rule_engine("ubuntu_24_04")
        conflicts = engine.detect_conflicts(body.rule_ids)
        return [ConflictResponse(**vars(c)) for c in conflicts]
    except APIError:
        raise
    except Exception as exc:
        raise_internal_error("rules_conflicts", exc, error_code=ErrorCode.PIPELINE_ERROR)


@router.get("/rules/categories", response_model=List[str], tags=["domain"])
async def list_rule_categories(
    os: Optional[str] = Query(None, description="OS identifier"),
) -> List[str]:
    """Return all unique category names for the given OS."""
    try:
        os_key = os or "ubuntu_24_04"
        engine = _get_rule_engine(os_key)
        if engine is None:
            return []
        rules = engine.list_rules()
        return sorted({r["category"] for r in rules if r.get("category")})
    except APIError:
        raise
    except Exception as exc:
        raise_internal_error("rules_categories", exc, error_code=ErrorCode.PIPELINE_ERROR)


@router.get("/rules", response_model=RuleListResponse, tags=["domain"])
async def list_rules(
    level: Optional[int] = Query(None, description="CIS level filter (1 or 2)"),
    category: Optional[str] = Query(None, description="Category name substring filter"),
    auto_remediate: Optional[bool] = Query(None, description="Filter by auto_remediate flag"),
    os: Optional[str] = Query(None, description="OS: ubuntu_24_04 | ubuntu_22_04 | windows_11 | windows_server_2025"),
    limit: int = Query(50, ge=1, le=2000),
    offset: int = Query(0, ge=0),
):
    """List CIS rules for the given OS. Script content is stripped from list responses."""
    try:
        os_key = os or "ubuntu_24_04"
        engine = _get_rule_engine(os_key)
        if engine is None:
            return RuleListResponse(rules=[], total=0, offset=offset, limit=limit)

        rules = engine.list_rules(level=level, category=category, auto_remediate=auto_remediate)
        total = len(rules)
        page = rules[offset : offset + limit]
        _STRIP = {"audit_script_content", "remediation_script_content"}
        stripped = [{k: v for k, v in r.items() if k not in _STRIP} for r in page]
        return RuleListResponse(rules=stripped, total=total, offset=offset, limit=limit)
    except APIError:
        raise
    except Exception as exc:
        raise_internal_error("rules_list", exc, error_code=ErrorCode.PIPELINE_ERROR)


# ── Artifact Endpoints ────────────────────────────────────────────────────────

@router.post("/artifacts/generate", response_model=ArtifactResponse, tags=["domain"])
async def generate_artifact(body: ArtifactRequest):
    """
    Generate a hardening artifact (Bash / PowerShell / Ansible / REG / GPO)
    from CIS rule IDs. Scripts are derived directly from the CIS YAML rule database.
    """
    try:
        engine = _get_rule_engine(body.os_target or "ubuntu_24_04")
        gen = _get_artifact_gen()

        rules: List[dict] = []
        missing: List[str] = []
        for rid in body.rule_ids:
            rule = engine.get_rule(rid)
            if rule:
                rules.append(dict(rule))  # copy — generator pops fields in-place
            else:
                missing.append(rid)

        if not rules:
            raise APIError(
                status_code=404, error_code=ErrorCode.NOT_FOUND,
                message="None of the provided rule IDs were found",
                details={"missing": missing},
            )

        # Şablonlama + YAML işi — event loop'u bloklamamak için thread'e al.
        artifact = await asyncio.to_thread(
            gen.generate, rules, body.format, body.os_target, body.security_level
        )
        if missing:
            artifact.warnings.insert(0, f"Unknown rule IDs skipped: {missing}")

        return ArtifactResponse(
            format=artifact.format,
            content=artifact.content,
            rule_count=artifact.rule_count,
            os_target=artifact.os_target,
            warnings=artifact.warnings,
        )
    except APIError:
        raise
    except Exception as exc:
        raise_internal_error("artifact_generate", exc, error_code=ErrorCode.PIPELINE_ERROR)
