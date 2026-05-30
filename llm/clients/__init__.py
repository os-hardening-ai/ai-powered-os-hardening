# models/__init__.py
from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Tuple

# Import from core.config
from llm.core.config import LLM_PROVIDER

logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]


def _get_openai_clients() -> Tuple[LLMCallable, LLMCallable]:
    """OpenAI client'larını local import ile al."""
    from .openai_client import get_small_openai_llm, get_large_openai_llm

    small = get_small_openai_llm()
    large = get_large_openai_llm()
    return small, large


def _get_groq_clients() -> Tuple[LLMCallable, LLMCallable]:
    """Groq client'larını local import ile al."""
    from .groq_client import get_small_groq_llm, get_large_groq_llm

    small = get_small_groq_llm()
    large = get_large_groq_llm()
    return small, large


def _get_novita_clients() -> Tuple[LLMCallable, LLMCallable]:
    """Novita client'larını local import ile al."""
    from .novita_llm_client import get_small_novita_llm, get_large_novita_llm

    small = get_small_novita_llm()
    large = get_large_novita_llm()
    return small, large


def _get_ollama_clients() -> Tuple[LLMCallable, LLMCallable]:
    """Ollama client'larını local import ile al."""
    from .ollama_client import get_small_ollama_llm, get_large_ollama_llm
    from llm.core.config import CONFIG

    small = get_small_ollama_llm(
        model_name=CONFIG.ollama_small_model,
        base_url=CONFIG.ollama_base_url,
        temperature=CONFIG.small_model_temperature,
        max_tokens=CONFIG.max_tokens,
    )
    large = get_large_ollama_llm(
        model_name=CONFIG.ollama_large_model,
        base_url=CONFIG.ollama_base_url,
        temperature=CONFIG.large_model_temperature,
        max_tokens=CONFIG.max_tokens,
    )
    return small, large


def _get_huggingface_clients() -> Tuple[LLMCallable, LLMCallable]:
    """HuggingFace client'larını local import ile al (ücretsiz tier — DEPRECATED, bkz. registry)."""
    from .huggingface_client import get_small_hf_llm, get_large_hf_llm

    return get_small_hf_llm(), get_large_hf_llm()


def _get_cerebras_clients() -> Tuple[LLMCallable, LLMCallable]:
    """Cerebras (gpt-oss-120b) — generic OpenAI-uyumlu client (en hızlı + ücretsiz 1M/gün)."""
    from .openai_compatible_client import get_small_cerebras_llm, get_large_cerebras_llm

    return get_small_cerebras_llm(), get_large_cerebras_llm()


def _get_sambanova_clients() -> Tuple[LLMCallable, LLMCallable]:
    """SambaNova (gpt-oss-120b) — generic OpenAI-uyumlu client (hızlı fallback)."""
    from .openai_compatible_client import get_small_sambanova_llm, get_large_sambanova_llm

    return get_small_sambanova_llm(), get_large_sambanova_llm()


def _get_gemini_clients() -> Tuple[LLMCallable, LLMCallable]:
    """Gemini 3.1 Flash Lite (OpenRouter üzerinden) — hızlı + 1M context fallback."""
    from .openai_compatible_client import get_small_gemini_llm, get_large_gemini_llm

    return get_small_gemini_llm(), get_large_gemini_llm()


# Sağlayıcı adı → (small, large) çifti kuran fonksiyon.
# Not: builder'lar burada tutulur (ollama özel kwargs gerektirir); registry yalnızca
# SIRA + maliyet metaverisi için kullanılır (ücretsiz-first politikası tek yerde).
_PROVIDER_BUILDERS: Dict[str, Callable[[], Tuple[LLMCallable, LLMCallable]]] = {
    "cerebras": _get_cerebras_clients,
    "sambanova": _get_sambanova_clients,
    "gemini": _get_gemini_clients,
    "novita": _get_novita_clients,
    # Aşağıdakiler registry'de deprecated (varsayılan zincirde DEĞİL); yalnızca açıkça
    # LLM_PROVIDER=<x> seçilirse kullanılır. Kullanıcı kararı: groq (riskli/flaky),
    # ollama (GPU yok), huggingface (bozuk) → otomatik akıştan çıkarıldı.
    "groq": _get_groq_clients,
    "ollama": _get_ollama_clients,
    "huggingface": _get_huggingface_clients,
    "openai": _get_openai_clients,
}


class FallbackLLM:
    """
    Birden çok sağlayıcıyı sırayla deneyen Callable[[str], str].

    Sağlayıcılar TEMBEL (lazy) kurulur: eksik API anahtarı olan bir sağlayıcı
    yalnızca o sağlayıcıya sıra geldiğinde atlanır, başlangıçta çökme olmaz.
    Bir çağrı hata verirse (429/timeout/5xx) sıradaki sağlayıcıya geçilir;
    hepsi başarısız olursa anlamlı bir hata yükseltilir (sessiz "" DÖNMEZ).

    small/large iki sarmalayıcı aynı `cache`'i paylaşır → her sağlayıcı en fazla
    bir kez kurulur.
    """

    def __init__(
        self,
        role: str,                      # "small" | "large"
        providers: List[str],
        cache: Dict[str, Optional[Tuple[LLMCallable, LLMCallable]]],
        stats: Optional[dict] = None,
    ) -> None:
        self.role = role
        self.providers = providers
        self._cache = cache
        # Gözlemlenebilirlik: hangi sağlayıcı kaç kez servis etti, kaç fallback oldu.
        # small/large paylaşımlı stats dict alabilir (get_llm_clients öyle verir).
        self.stats = stats if stats is not None else {
            "total_calls": 0, "fallback_count": 0, "failures": 0, "by_provider": {},
        }

    def _client(self, provider: str) -> Optional[LLMCallable]:
        if provider not in self._cache:
            try:
                self._cache[provider] = _PROVIDER_BUILDERS[provider]()
                logger.info("[FallbackLLM] provider '%s' hazır", provider)
            except Exception as exc:
                logger.warning("[FallbackLLM] provider '%s' kullanılamıyor (atlanıyor): %s", provider, exc)
                self._cache[provider] = None
        built = self._cache[provider]
        if built is None:
            return None
        return built[0] if self.role == "small" else built[1]

    def __call__(self, prompt: str) -> str:
        from llm.clients.base import classify_error

        self.stats["total_calls"] += 1
        last_exc: Optional[Exception] = None
        attempted: List[str] = []
        for idx, provider in enumerate(self.providers):
            client = self._client(provider)
            if client is None:
                continue
            attempted.append(provider)
            try:
                result = client(prompt)
                self.stats["by_provider"][provider] = self.stats["by_provider"].get(provider, 0) + 1
                if idx > 0:  # birincil değil → fallback gerçekleşti
                    self.stats["fallback_count"] += 1
                    logger.info("[FallbackLLM] '%s' ile kurtarıldı (fallback)", provider)
                return result
            except Exception as exc:
                last_exc = classify_error(exc, provider)
                logger.warning(
                    "[FallbackLLM] '%s' başarısız (%s), sıradakine geçiliyor: %s",
                    provider, type(last_exc).__name__, last_exc,
                )
        self.stats["failures"] += 1
        raise RuntimeError(
            f"Tüm LLM sağlayıcıları başarısız oldu (denenen: {attempted or self.providers}). "
            f"Son hata: {last_exc}"
        )

    def get_stats(self) -> dict:
        total = self.stats["total_calls"]
        rate = (self.stats["fallback_count"] / total) if total else 0.0
        return {**self.stats, "fallback_rate": round(rate, 4)}


def get_llm_clients(enable_fallback: bool = True) -> Tuple[LLMCallable, LLMCallable]:
    """
    LLM_PROVIDER birincil; başarısız olursa diğer sağlayıcılara düşen (small, large) döndürür.

    Args:
        enable_fallback: False ise yalnızca birincil sağlayıcı (eski davranış,
                         örn. değerlendirme/ablation'da tek modeli sabitlemek için).

    Dönüş:
        (llm_small, llm_large)  # her ikisi de Callable[[str], str]
    """
    import os
    from llm.clients.registry import build_order, get_spec, Cost

    provider = (LLM_PROVIDER or "groq").lower()
    if provider not in _PROVIDER_BUILDERS:
        raise ValueError(
            f"Desteklenmeyen LLM_PROVIDER: '{provider}'\n"
            f"Geçerli değerler: {', '.join(_PROVIDER_BUILDERS)}"
        )

    if not enable_fallback:
        return _PROVIDER_BUILDERS[provider]()

    # Sıra registry'den. Varsayılan: ücretsiz-first (groq → huggingface → ollama).
    # LLM_INCLUDE_CHEAP=1 → düşük ücretli kotasız Novita 429 güvenlik ağı olarak sona
    # eklenir (kullanıcı "düşük ücretler de ok" dedi). LLM_INCLUDE_PAID=1 → pahalı dahil.
    # Birincil sağlayıcı cheap/paid ise (açık tercih) yine başa alınır.
    _truthy = ("1", "true", "yes", "on")
    include_cheap = os.environ.get("LLM_INCLUDE_CHEAP", "").lower() in _truthy
    include_paid = os.environ.get("LLM_INCLUDE_PAID", "").lower() in _truthy
    primary_cost = get_spec(provider).cost
    if primary_cost is Cost.CHEAP_PAID:
        include_cheap = True
    if primary_cost is Cost.PAID:
        include_paid = True
    order = build_order(primary=provider, include_cheap=include_cheap, include_paid=include_paid)
    shared_cache: Dict[str, Optional[Tuple[LLMCallable, LLMCallable]]] = {}
    shared_stats = {"total_calls": 0, "fallback_count": 0, "failures": 0, "by_provider": {}}
    small = FallbackLLM("small", order, shared_cache, shared_stats)
    large = FallbackLLM("large", order, shared_cache, shared_stats)
    return small, large


# WARNING: Module-level initialization sorunları yaşanmaması için
# llm_small ve llm_large'ı doğrudan kullanmak yerine get_llm_clients()
# fonksiyonunu kullanın. Ancak backward compatibility için hala export ediyoruz.

# Module seviyesinde export et - ancak dikkatli kullanılmalı
try:
    llm_small, llm_large = get_llm_clients()
except Exception as e:
    # Import-time hata olursa warning ver ama crash etme.
    import warnings
    warnings.warn(
        f"LLM clients initialization failed: {e}\n"
        f"Use get_llm_clients() directly in your code instead of importing llm_small/llm_large.",
        RuntimeWarning,
    )

    # Dummy: SESSİZCE "" DÖNME — bu, hatayı yutup aşağı akışta boş/yanlış
    # cevaplara yol açıyordu. Bunun yerine çağrıldığında anlamlı hata yükselt.
    def _unavailable_llm(_prompt: str) -> str:  # type: ignore[misc]
        raise RuntimeError(
            "LLM clients kullanılamıyor (başlatma başarısız). "
            "get_llm_clients() ile doğrudan başlatmayı deneyin ve .env/anahtarları kontrol edin."
        )

    llm_small = _unavailable_llm  # type: ignore[assignment]
    llm_large = _unavailable_llm  # type: ignore[assignment]


__all__ = ["get_llm_clients", "llm_small", "llm_large"]