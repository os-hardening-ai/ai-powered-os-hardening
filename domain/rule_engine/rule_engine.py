from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

_logger = logging.getLogger(__name__)


@dataclass
class RuleConflict:
    rule_a: str
    rule_b: str
    conflict_type: str  # "config_file" | "kernel_module"
    resource: str
    description: str


@dataclass
class ExecutionPlan:
    ordered_rules: List[str]
    conflicts: List[RuleConflict]
    warnings: List[str]


class RuleEngine:
    """
    Loads CIS rules from a YAML file and provides:
      - Conflict detection  — config_file and kernel_module overlap between rules
      - Dependency ordering — topological sort by CIS section number
      - Execution plans     — ordered list + conflict warnings
    """

    def __init__(self, rules_path: str | Path) -> None:
        self._path = Path(rules_path)
        self._rules: Dict[str, dict] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for rule in data.get("rules", []):
            self._rules[rule["id"]] = rule
        self._loaded = True
        _logger.info("[RuleEngine] Loaded %d rules from %s", len(self._rules), self._path.name)

    def detect_conflicts(self, rule_ids: List[str]) -> List[RuleConflict]:
        """Find rules that write to the same config files or manage the same kernel module."""
        self._ensure_loaded()
        conflicts: List[RuleConflict] = []
        selected = [self._rules[rid] for rid in rule_ids if rid in self._rules]

        # Config file overlap
        config_map: Dict[str, List[str]] = {}
        for rule in selected:
            for cf in rule.get("config_files", []):
                config_map.setdefault(str(cf), []).append(rule["id"])

        for resource, rids in config_map.items():
            for i in range(len(rids)):
                for j in range(i + 1, len(rids)):
                    conflicts.append(RuleConflict(
                        rule_a=rids[i], rule_b=rids[j],
                        conflict_type="config_file", resource=resource,
                        description=f"Both rules modify '{resource}'",
                    ))

        # Kernel module overlap
        mod_map: Dict[str, List[str]] = {}
        for rule in selected:
            mod = rule.get("kernel_module")
            if mod:
                mod_map.setdefault(str(mod), []).append(rule["id"])

        for mod, rids in mod_map.items():
            if len(rids) > 1:
                for i in range(len(rids)):
                    for j in range(i + 1, len(rids)):
                        conflicts.append(RuleConflict(
                            rule_a=rids[i], rule_b=rids[j],
                            conflict_type="kernel_module", resource=mod,
                            description=(
                                f"Both rules manage kernel module '{mod}' — "
                                "verify they are not contradictory"
                            ),
                        ))

        return conflicts

    def resolve_order(self, rule_ids: List[str]) -> List[str]:
        """Sort rules by CIS section number (topological order via numeric key)."""
        self._ensure_loaded()

        def _section_key(rid: str) -> Tuple[int, ...]:
            rule = self._rules.get(rid, {})
            parts = re.findall(r"\d+", rule.get("id", rid))
            return tuple(int(p) for p in parts)

        valid = [rid for rid in rule_ids if rid in self._rules]
        missing = [rid for rid in rule_ids if rid not in self._rules]
        if missing:
            _logger.warning("[RuleEngine] Unknown rule IDs: %s", missing)
        return sorted(valid, key=_section_key)

    def get_execution_plan(self, rule_ids: List[str]) -> ExecutionPlan:
        """Return ordered rules + detected conflicts + human-readable warnings."""
        self._ensure_loaded()
        ordered = self.resolve_order(rule_ids)
        conflicts = self.detect_conflicts(rule_ids)
        warnings = [
            f"Rules {c.rule_a} and {c.rule_b} both modify '{c.resource}' "
            f"({c.conflict_type}) — review order before applying"
            for c in conflicts
        ]
        return ExecutionPlan(ordered_rules=ordered, conflicts=conflicts, warnings=warnings)

    def get_rule(self, rule_id: str) -> Optional[dict]:
        self._ensure_loaded()
        return self._rules.get(rule_id)

    def list_rules(
        self,
        level: Optional[int] = None,
        category: Optional[str] = None,
        auto_remediate: Optional[bool] = None,
    ) -> List[dict]:
        self._ensure_loaded()
        rules = list(self._rules.values())
        if level is not None:
            rules = [r for r in rules if r.get("level") == level]
        if category:
            rules = [r for r in rules if category.lower() in r.get("category", "").lower()]
        if auto_remediate is not None:
            rules = [r for r in rules if r.get("auto_remediate") == auto_remediate]
        return rules
