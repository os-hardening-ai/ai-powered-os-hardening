from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]

_OS_PATTERNS: dict[str, list[str]] = {
    "ubuntu_24_04": ["ubuntu 24.04", "ubuntu 24", "ubuntu24"],
    "ubuntu_22_04": ["ubuntu 22.04", "ubuntu 22", "ubuntu22"],
    "windows_server_2025": ["windows server 2025", "win server 2025", "ws2025", "windows 2025"],
    "windows_11": ["windows 11", "win11", "windows11"],
    "windows_server_2022": ["windows server 2022", "win server 2022", "ws2022"],
    "centos": ["centos", "rhel", "red hat"],
    "debian": ["debian"],
}

_ROLE_PATTERNS: dict[str, list[str]] = {
    "sysadmin": ["sysadmin", "sistem yönetici", "system admin", "sunucu yönet"],
    "developer": ["developer", "geliştirici", "yazılımcı", "devops"],
    "auditor": ["auditor", "denetçi", "compliance", "pentest"],
    "soc": ["soc", "security analyst", "güvenlik analisti"],
}


@dataclass
class InferredFilters:
    os_type: Optional[str] = None
    role: Optional[str] = None
    confidence: float = 0.0
    source: str = "none"  # "pattern" | "llm" | "none"


class FilterAgent:
    """
    Infers metadata filters (OS type, role) from user query.
    Pattern matching first (<1ms, $0); LLM fallback for ambiguous queries.
    """

    def __init__(self, llm_fn: LLMCallable) -> None:
        self._llm = llm_fn

    def infer(self, query: str) -> InferredFilters:
        result = _pattern_infer(query)
        if result.os_type is not None:
            return result
        try:
            return self._llm_infer(query)
        except Exception as exc:
            logger.warning("[FilterAgent] LLM inference failed: %s", exc)
            return result

    def _llm_infer(self, query: str) -> InferredFilters:
        prompt = (
            "Extract OS type and user role from this OS security question.\n"
            "Supported os_type values: ubuntu_24_04, ubuntu_22_04, windows_server_2025, "
            "windows_11, centos, debian, null\n"
            "Supported role values: sysadmin, developer, auditor, soc, null\n"
            'Return ONLY JSON: {"os_type": "...", "role": "...", "confidence": 0.0-1.0}\n\n'
            f"Question: {query}"
        )
        resp = self._llm(prompt)
        match = re.search(r"\{.*?\}", resp, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group())
                os_type = obj.get("os_type") or None
                if os_type in ("null", ""):
                    os_type = None
                role = obj.get("role") or None
                if role in ("null", ""):
                    role = None
                return InferredFilters(
                    os_type=os_type,
                    role=role,
                    confidence=float(obj.get("confidence", 0.5)),
                    source="llm",
                )
            except (json.JSONDecodeError, ValueError):
                pass
        return InferredFilters(confidence=0.0, source="none")


def _pattern_infer(query: str) -> InferredFilters:
    q_lower = query.lower()
    os_type: Optional[str] = None
    role: Optional[str] = None

    for os_key, patterns in _OS_PATTERNS.items():
        if any(p in q_lower for p in patterns):
            os_type = os_key
            break

    for role_key, patterns in _ROLE_PATTERNS.items():
        if any(p in q_lower for p in patterns):
            role = role_key
            break

    if os_type is not None:
        return InferredFilters(os_type=os_type, role=role, confidence=0.95, source="pattern")
    return InferredFilters(role=role, confidence=0.0, source="none")
