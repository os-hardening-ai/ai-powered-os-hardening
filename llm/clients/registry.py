"""
Sağlayıcı kayıt defteri (registry) — tek yerde sağlayıcı metaverisi + ücretsiz-first sıra.

Amaç: "hangi sağlayıcılar var, hangisi ücretsiz, fallback sırası ne olmalı?" sorusunu
tek otorite olarak yanıtlamak. `FallbackLLM` ve `get_llm_clients()` bu defteri kullanır.

Maliyet politikası (proje kararı): yalnızca ÜCRETSIZ / ÜCRETSIZ-TIER sağlayıcılar
varsayılan zincire girer. PAID sağlayıcılar (novita, openai) kayıtlıdır ama varsayılan
ücretsiz-first sıraya DAHIL EDİLMEZ — yalnızca açıkça istenirse kullanılır.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Tuple

LLMCallable = Callable[[str], str]
ProviderBuilder = Callable[[], Tuple[LLMCallable, LLMCallable]]  # () -> (small, large)


class Cost(Enum):
    FREE = "free"            # Tamamen ücretsiz, limitsiz (yerel) — Ollama
    FREE_TIER = "free_tier"  # Ücretsiz ama kotalı/rate-limit — Groq, HuggingFace
    PAID = "paid"            # Ücretli — Novita, OpenAI


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    builder_path: str        # "llm.clients.groq_client:get_small_groq_llm,get_large_groq_llm"
    cost: Cost
    # Ücretsiz-first sırada düşük = önce. Sadece FREE/FREE_TIER için anlamlı.
    free_priority: int = 100
    notes: str = ""

    def build(self) -> Tuple[LLMCallable, LLMCallable]:
        mod_path, getters = self.builder_path.split(":")
        small_getter, large_getter = getters.split(",")
        mod = __import__(mod_path, fromlist=[small_getter, large_getter])
        return getattr(mod, small_getter)(), getattr(mod, large_getter)()


# ── Kayıt defteri ─────────────────────────────────────────────────────────────
# free_priority: Groq önce (en hızlı ücretsiz-tier), sonra HuggingFace (ücretsiz-tier),
# sonra Ollama (yerel/limitsiz ama kurulum + yavaş olabilir → ağ sağlayıcıları düşünce son).

_REGISTRY: Dict[str, ProviderSpec] = {
    "groq": ProviderSpec(
        "groq", "llm.clients.groq_client:get_small_groq_llm,get_large_groq_llm",
        Cost.FREE_TIER, free_priority=10, notes="Hızlı, ücretsiz tier (rate-limit'li)",
    ),
    "huggingface": ProviderSpec(
        "huggingface", "llm.clients.huggingface_client:get_small_hf_llm,get_large_hf_llm",
        Cost.FREE_TIER, free_priority=20, notes="Ücretsiz Inference API (HF_API_KEY gerekir)",
    ),
    "ollama": ProviderSpec(
        "ollama", "llm.clients.ollama_client:get_small_ollama_llm,get_large_ollama_llm",
        Cost.FREE, free_priority=30, notes="Yerel, limitsiz, offline (kurulum gerekir)",
    ),
    # PAID — kayıtlı ama ücretsiz-first sıraya girmez.
    "novita": ProviderSpec(
        "novita", "llm.clients.novita_llm_client:get_small_novita_llm,get_large_novita_llm",
        Cost.PAID, free_priority=900, notes="ÜCRETLI — yalnızca açıkça istenirse",
    ),
    "openai": ProviderSpec(
        "openai", "llm.clients.openai_client:get_small_openai_llm,get_large_openai_llm",
        Cost.PAID, free_priority=910, notes="ÜCRETLI — yalnızca açıkça istenirse",
    ),
}


def get_spec(name: str) -> ProviderSpec:
    key = (name or "").lower()
    if key not in _REGISTRY:
        raise ValueError(f"Bilinmeyen sağlayıcı: {name!r}. Geçerli: {', '.join(_REGISTRY)}")
    return _REGISTRY[key]


def all_specs() -> Dict[str, ProviderSpec]:
    return dict(_REGISTRY)


def free_first_order(include_paid: bool = False) -> List[str]:
    """Ücretsiz/ücretsiz-tier sağlayıcıları free_priority sırasında döndürür.

    include_paid=True ise PAID sağlayıcılar da en sona eklenir (açık tercih).
    """
    specs = [s for s in _REGISTRY.values() if include_paid or s.cost is not Cost.PAID]
    specs.sort(key=lambda s: s.free_priority)
    return [s.name for s in specs]


def build_order(primary: str | None = None, include_paid: bool = False) -> List[str]:
    """Fallback sırası: varsa `primary` önce, ardından ücretsiz-first kalan sıra (tekrarsız)."""
    order = free_first_order(include_paid=include_paid)
    if primary:
        primary = primary.lower()
        # primary PAID olsa bile kullanıcı açıkça seçtiyse başa koy
        order = [primary] + [p for p in order if p != primary]
        if primary not in _REGISTRY:
            raise ValueError(f"Bilinmeyen primary sağlayıcı: {primary!r}")
    return order
