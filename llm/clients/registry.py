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
    FREE = "free"             # Tamamen ücretsiz, limitsiz (yerel) — Ollama
    FREE_TIER = "free_tier"   # Ücretsiz ama kotalı/rate-limit — Groq, HuggingFace
    CHEAP_PAID = "cheap_paid" # Düşük ücretli, kullandıkça-öde (kotasız) — Novita
    PAID = "paid"             # Pahalı — OpenAI gpt-4o vb.


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
    # CHEAP_PAID — düşük ücretli, kotasız. Ücretsizler bittiğinde 429'a karşı
    # güvenlik ağı olarak istenirse zincire alınır (kullanıcı: "düşük ücretler de ok").
    "novita": ProviderSpec(
        "novita", "llm.clients.novita_llm_client:get_small_novita_llm,get_large_novita_llm",
        Cost.CHEAP_PAID, free_priority=800,
        notes="Düşük ücretli + kotasız — 429 güvenlik ağı (include_cheap ile)",
    ),
    # PAID — pahalı; yalnızca açıkça primary seçilirse.
    "openai": ProviderSpec(
        "openai", "llm.clients.openai_client:get_small_openai_llm,get_large_openai_llm",
        Cost.PAID, free_priority=910, notes="Pahalı — yalnızca açıkça istenirse",
    ),
}


def get_spec(name: str) -> ProviderSpec:
    key = (name or "").lower()
    if key not in _REGISTRY:
        raise ValueError(f"Bilinmeyen sağlayıcı: {name!r}. Geçerli: {', '.join(_REGISTRY)}")
    return _REGISTRY[key]


def all_specs() -> Dict[str, ProviderSpec]:
    return dict(_REGISTRY)


def free_first_order(include_cheap: bool = False, include_paid: bool = False) -> List[str]:
    """Sağlayıcıları free_priority sırasında döndürür.

    Varsayılan: yalnızca FREE/FREE_TIER (ücretsiz-first).
    include_cheap=True: CHEAP_PAID (Novita) de en sona eklenir → 429 güvenlik ağı.
    include_paid=True : pahalı PAID (OpenAI) de eklenir.
    """
    def _ok(s: ProviderSpec) -> bool:
        if s.cost in (Cost.FREE, Cost.FREE_TIER):
            return True
        if s.cost is Cost.CHEAP_PAID:
            return include_cheap or include_paid
        return include_paid  # Cost.PAID
    specs = sorted((s for s in _REGISTRY.values() if _ok(s)), key=lambda s: s.free_priority)
    return [s.name for s in specs]


def build_order(
    primary: str | None = None,
    include_cheap: bool = False,
    include_paid: bool = False,
) -> List[str]:
    """Fallback sırası: varsa `primary` önce, ardından ücretsiz-first kalan sıra (tekrarsız)."""
    order = free_first_order(include_cheap=include_cheap, include_paid=include_paid)
    if primary:
        primary = primary.lower()
        if primary not in _REGISTRY:
            raise ValueError(f"Bilinmeyen primary sağlayıcı: {primary!r}")
        # primary listede yoksa (örn. cheap/paid ama flag kapalı) yine başa eklenir.
        order = [primary] + [p for p in order if p != primary]
    return order
