from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, List, Tuple

logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]


@dataclass
class ClaimCheck:
    claim: str
    supported: bool
    reason: str = ""


@dataclass
class VerificationResult:
    is_valid: bool
    confidence: float          # 0.0 – 1.0  (fraction of claims that are supported)
    claims: List[ClaimCheck] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)


class ClaimVerifier:
    """
    Verifies LLM-generated answer claims against the retrieved chunks.

    Each atomic claim in the answer is checked: "Is this directly supported
    by the retrieved context?"  If too many claims are unsupported the result
    is marked invalid and the caller can add a low-confidence disclaimer.

    Critical for OS hardening answers — a wrong command can take a server
    offline or introduce a security regression.

    Uses the existing sync LLM callable (llm_small is fine — judgment task).
    All calls are best-effort: on parse failures the claim is marked supported
    (conservative — avoids false negatives).
    """

    def __init__(
        self,
        llm_fn: LLMCallable,
        min_confidence: float = 0.6,
        max_claims: int = 6,
        max_chunk_chars: int = 600,
        max_context_chars: int = 4000,
    ) -> None:
        self._llm = llm_fn
        self.min_confidence = min_confidence
        self.max_claims = max_claims
        # Doğrulama bağlamı pencereleri (token/maliyet sınırı). Üretim makul sınırlı;
        # değerlendirme (İP-5) TAM bağlama karşı doğrulamak için bunları büyütür.
        # Eski sabit 2000 kr ~3 chunk'ı gösteriyordu → uzaktaki desteklenen iddialar
        # sahte "desteklenmiyor" sayılıyordu (groundedness yapay düşüktü).
        self.max_chunk_chars = max_chunk_chars
        self.max_context_chars = max_context_chars

    def verify(self, answer: str, chunks: List[dict]) -> VerificationResult:
        """
        Args:
            answer: The LLM-generated answer text to verify.
            chunks: Retrieved context chunks [{"id", "text", "metadata"}].

        Returns:
            VerificationResult with is_valid flag and per-claim details.
        """
        if not chunks:
            return VerificationResult(is_valid=True, confidence=1.0)

        claims = self._extract_claims(answer)
        if not claims:
            return VerificationResult(is_valid=True, confidence=1.0)

        context = "\n\n".join(
            f"[{i + 1}] {c.get('text', '')[:self.max_chunk_chars]}"
            for i, c in enumerate(chunks)
        )

        # Her iddia bağımsız olarak aynı context'e karşı denetlenir → I/O-bound
        # LLM çağrılarını paralelleştir (sıralı 1+N yerine ~tek çağrı süresi).
        to_check = claims[: self.max_claims]
        if len(to_check) <= 1:
            results = [self._check_claim(c, context) for c in to_check]
        else:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(self.max_claims, len(to_check))) as pool:
                results = list(pool.map(lambda c: self._check_claim(c, context), to_check))
        checked: List[ClaimCheck] = [
            ClaimCheck(claim=claim, supported=supported, reason=reason)
            for claim, (supported, reason) in zip(to_check, results)
        ]

        unsupported = [c.claim for c in checked if not c.supported]
        confidence = 1.0 - len(unsupported) / max(len(checked), 1)

        logger.debug(
            "[ClaimVerifier] %d/%d claims supported — confidence=%.2f",
            len(checked) - len(unsupported),
            len(checked),
            confidence,
        )

        return VerificationResult(
            is_valid=confidence >= self.min_confidence,
            confidence=confidence,
            claims=checked,
            unsupported=unsupported,
        )

    # ── private helpers ──────────────────────────────────────────────────────

    def _extract_claims(self, answer: str) -> List[str]:
        # Atıf işaretlerini ([1], [2]...) çıkar: yoksa "1", "3" gibi anlamsız parçalar
        # "iddia" olarak çıkıyor ve bağlama karşı denetlenince hep "desteklenmiyor" sayılıyor.
        cleaned = re.sub(r"\[\s*\d+\s*\]", " ", answer)
        prompt = (
            f"Extract up to {self.max_claims} atomic factual claims from this answer.\n"
            "Each claim MUST be a COMPLETE standalone sentence stating ONE verifiable fact "
            "(a directive, config key/value, command, or CIS recommendation). "
            "Do NOT return bare fragments, numbers, paths, or citation markers on their own.\n"
            "Return ONLY a JSON array of strings — no markdown, no explanation.\n\n"
            f"Answer:\n{cleaned[:1500]}"
        )
        try:
            resp = self._llm(prompt)
            items = _parse_json_list(resp, self.max_claims)
            return _filter_claims(items)
        except Exception as exc:
            logger.warning("[ClaimVerifier] claim extraction failed: %s", exc)
            return []

    def _check_claim(self, claim: str, context: str) -> Tuple[bool, str]:
        prompt = (
            "Is this claim DIRECTLY supported by the context below?\n"
            'Answer with JSON only: {"supported": true/false, "reason": "one sentence"}\n\n'
            f"Claim: {claim}\n\n"
            f"Context (truncated):\n{context[:self.max_context_chars]}"
        )
        try:
            resp = self._llm(prompt)
            match = re.search(r"\{.*?\}", resp, re.DOTALL)
            if match:
                obj = json.loads(match.group())
                return bool(obj.get("supported", True)), str(obj.get("reason", ""))
        except Exception as exc:
            logger.warning("[ClaimVerifier] claim check failed: %s", exc)
        # Conservative fallback — treat as supported to avoid false negatives
        return True, "parse_error"


def _filter_claims(items: List[str]) -> List[str]:
    """Doğrulanamaz 'iddia'ları ele: çok kısa, salt sayı/noktalama, tek kelime parça.

    Teşhiste extraction'ın "/etc", "CIS Benchmark", "1", "3" gibi parçalar ürettiği
    görüldü; bunları bağlama karşı denetlemek anlamsız (hep 'desteklenmiyor' → yapay
    düşük groundedness). Gerçek iddia = çok kelimeli, anlamlı uzunlukta cümle.
    """
    out: List[str] = []
    for c in items:
        s = str(c).strip()
        if len(s) < 15:                      # "/etc", "1", "CIS" gibi parçalar
            continue
        if " " not in s:                      # tek kelime → iddia değil
            continue
        if re.fullmatch(r"[\d\W]+", s):       # salt sayı/noktalama
            continue
        out.append(s)
    return out


def _parse_json_list(text: str, max_items: int) -> List[str]:
    try:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            items = json.loads(match.group())
            return [str(x) for x in items if isinstance(x, str)][:max_items]
    except Exception:
        pass
    return []
