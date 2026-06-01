"""
İP-7 — Multi-step Reasoning / Tool-Use Ajanı (HardeningAgent)

Öneri formu: "Ajanın çok-adımlı akıl yürütme (multi-step reasoning) ... self-verify
modülü devreye alınır."

Ajan, bir sıkılaştırma hedefini birden çok ARACI sırayla kullanarak çözer:

    1. PLAN      → TaskPlanner (İP-6): hedefe uygun kuralları seç + sırala
    2. COLLECT   → RuleEngine: seçilen kuralların tam tanımlarını topla
    3. GENERATE  → ArtifactGenerator: uygulanabilir script üret (bash/ps/ansible)
    4. VERIFY    → OutputValidator: tehlikeli komut / kalite self-verify
    5. REFINE    → güvensizse tehlikeli kuralı çıkar ve YENİDEN üret (gözlem→
                   akıl yürütme→yeniden eylem), en fazla `max_refine` kez

Her adım bir AgentStep olarak kaydedilir → açıklanabilir, denetlenebilir iz.
Tüm araçlar (rule_engine, artifact_generator, validator) deterministik çalışır;
LLM yalnızca planlama (İP-6) ve opsiyonel özet için kullanılır.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from domain.rule_engine.rule_engine import RuleEngine
from domain.artifact_generator.generator import ArtifactGenerator, Artifact
from llm.pipelines.layers.output_validator import OutputValidator
from llm.agents.task_planner import TaskPlanner, HardeningPlan

logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]


@dataclass
class AgentStep:
    """Tek bir akıl yürütme/araç adımı (denetim izi)."""
    name: str            # plan | collect | generate | verify | refine | summarize
    tool: str            # kullanılan aracın adı
    detail: str          # insan-okunur özet
    ok: bool = True


@dataclass
class AgentResult:
    success: bool
    goal: str
    os_target: str
    fmt: str
    plan: Optional[HardeningPlan] = None
    artifact: Optional[Artifact] = None
    issues: List[str] = field(default_factory=list)
    steps: List[AgentStep] = field(default_factory=list)
    summary: str = ""


class HardeningAgent:
    """
    İP-7 çok-adımlı tool-use ajanı.

    Kullanım:
        agent = HardeningAgent(rule_engine=engine, llm_fn=groq_small)
        result = agent.run("SSH'i sıkılaştır", os_target="ubuntu_24_04",
                           security_level="strict", fmt="bash")
        print(result.artifact.content)
        for s in result.steps: print(s.name, s.detail)
    """

    def __init__(
        self,
        rule_engine: RuleEngine,
        llm_fn: Optional[LLMCallable] = None,
        artifact_generator: Optional[ArtifactGenerator] = None,
        task_planner: Optional[TaskPlanner] = None,
        max_refine: int = 1,
        debug: bool = False,
    ) -> None:
        self.rule_engine = rule_engine
        self.llm = llm_fn
        self.artifact_generator = artifact_generator or ArtifactGenerator()
        self.planner = task_planner or TaskPlanner(rule_engine=rule_engine, llm_fn=llm_fn, debug=debug)
        # Regex-only validator (no LLM needed for the safety self-verify gate)
        self.validator = OutputValidator(use_llm_validation=False, debug=debug)
        self.max_refine = max_refine
        self.debug = debug
        self._danger_re = [re.compile(p, re.IGNORECASE) for p in OutputValidator.DANGEROUS_COMMANDS]

    def run(
        self,
        goal: str,
        os_target: str = "ubuntu_24_04",
        security_level: str = "balanced",
        fmt: str = "bash",
    ) -> AgentResult:
        steps: List[AgentStep] = []

        # ── Step 1: PLAN (tool: TaskPlanner / İP-6) ──
        plan = self.planner.plan(goal, os_target=os_target, security_level=security_level)
        steps.append(AgentStep(
            "plan", "TaskPlanner",
            f"{len(plan.items)} kural seçildi, {len(plan.conflicts)} olası çakışma",
            ok=bool(plan.items),
        ))
        if not plan.items:
            return AgentResult(
                success=False, goal=goal, os_target=os_target, fmt=fmt,
                plan=plan, steps=steps,
                summary="Hedef için uygulanabilir kural bulunamadı.",
            )

        selected_ids = [item.rule_id for item in plan.items]

        # ── Steps 2-5: COLLECT → GENERATE → VERIFY → (REFINE) döngüsü ──
        artifact: Optional[Artifact] = None
        validation = None
        for attempt in range(self.max_refine + 1):
            # Step 2: COLLECT (tool: RuleEngine)
            rules = [r for r in (self.rule_engine.get_rule(rid) for rid in selected_ids) if r]
            if attempt == 0:
                steps.append(AgentStep("collect", "RuleEngine", f"{len(rules)} kural tanımı toplandı"))

            # Step 3: GENERATE (tool: ArtifactGenerator)
            artifact = self.artifact_generator.generate(rules, fmt, os_target, security_level)
            steps.append(AgentStep(
                "generate", "ArtifactGenerator",
                f"{artifact.rule_count} kural → {fmt} script ({len(artifact.content)} karakter)",
                ok=artifact.rule_count > 0,
            ))

            # Step 4: VERIFY (tool: OutputValidator — tehlikeli komut self-verify)
            # intent=info_request: kod-bloğu zorunluluğunu atlar, tehlikeli komut +
            # uzunluk kontrollerini uygular (artifact ham script, markdown değil).
            validation = self.validator.validate(artifact.content, intent="info_request")
            steps.append(AgentStep(
                "verify", "OutputValidator",
                "güvenli" if validation.is_valid else f"{len(validation.issues)} sorun: {validation.issues[:2]}",
                ok=validation.is_valid,
            ))

            if validation.is_valid:
                break

            # Step 5: REFINE — gözlem→akıl yürütme→yeniden eylem
            if attempt < self.max_refine:
                dangerous_ids = self._find_dangerous_rules(selected_ids)
                if not dangerous_ids:
                    break  # sorun tehlikeli komuttan değil → refine fayda etmez
                selected_ids = [rid for rid in selected_ids if rid not in dangerous_ids]
                steps.append(AgentStep(
                    "refine", "HardeningAgent",
                    f"Tehlikeli komut içeren {len(dangerous_ids)} kural çıkarıldı, yeniden üretiliyor: {sorted(dangerous_ids)}",
                ))
                if not selected_ids:
                    break

        success = bool(artifact and artifact.rule_count > 0 and validation and validation.is_valid)
        summary = self._summarize(goal, plan, artifact, success)
        steps.append(AgentStep("summarize", "LLM" if self.llm else "template", summary[:80], ok=True))

        return AgentResult(
            success=success,
            goal=goal,
            os_target=os_target,
            fmt=fmt,
            plan=plan,
            artifact=artifact,
            issues=list(validation.issues) if validation else [],
            steps=steps,
            summary=summary,
        )

    # ── internal tools ──────────────────────────────────────────────────────────

    def _find_dangerous_rules(self, rule_ids: List[str]) -> set[str]:
        """Remediation içeriği tehlikeli komut barındıran kuralları bul."""
        bad: set[str] = set()
        for rid in rule_ids:
            rule = self.rule_engine.get_rule(rid) or {}
            script = (
                rule.get("remediation_script_content")
                or rule.get("remediation_command")
                or ""
            )
            if any(rx.search(script) for rx in self._danger_re):
                bad.add(rid)
        return bad

    def _summarize(self, goal: str, plan: HardeningPlan, artifact: Optional[Artifact], success: bool) -> str:
        # GERÇEK final kural sayısı = üretilen artifact'ınki (refine'da tehlikeli kural
        # çıkarılmış olabilir → plan.items'tan farklı). Özet plan'ı değil ÜRETİLENİ yansıtır.
        final_count = artifact.rule_count if artifact else len(plan.items)
        removed = len(plan.items) - final_count
        removed_note = f" ({removed} kural güvenlik nedeniyle çıkarıldı)" if removed > 0 else ""
        base = (
            f"'{goal}' hedefi için {final_count} kurallı bir {artifact.format if artifact else '?'} "
            f"sıkılaştırma planı üretildi{removed_note} ve "
            f"{'doğrulandı' if success else 'doğrulama uyarıları içeriyor'}."
        )
        if not self.llm:
            return base
        try:
            prompt = (
                "Aşağıdaki sıkılaştırma planını 1-2 cümleyle, yöneticiye uygun dilde özetle. "
                "Sadece özet metni döndür.\n\n"
                f"Hedef: {goal}\nOS: {plan.os_target}\nSeviye: {plan.security_level}\n"
                f"Üretilen kural sayısı: {final_count}{removed_note}\n"
                f"Çakışma: {len(plan.conflicts)}\n"
                f"Doğrulama: {'başarılı' if success else 'uyarılı'}"
            )
            out = self.llm(prompt).strip()
            return out or base
        except Exception:  # pragma: no cover - defensive
            return base
