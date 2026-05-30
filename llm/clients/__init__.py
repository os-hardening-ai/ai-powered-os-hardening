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


# Sağlayıcı adı → (small, large) çifti kuran fonksiyon
_PROVIDER_BUILDERS: Dict[str, Callable[[], Tuple[LLMCallable, LLMCallable]]] = {
    "groq": _get_groq_clients,
    "openai": _get_openai_clients,
    "ollama": _get_ollama_clients,
    "novita": _get_novita_clients,
}

# Birincil sağlayıcı başarısız olursa denenecek varsayılan sıra. Anahtarı/erişimi
# olmayan sağlayıcılar otomatik atlanır (lazy build hatası → skip).
_DEFAULT_FALLBACK_ORDER: List[str] = ["groq", "novita", "openai", "ollama"]


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
    ) -> None:
        self.role = role
        self.providers = providers
        self._cache = cache

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
        last_exc: Optional[Exception] = None
        attempted: List[str] = []
        for provider in self.providers:
            client = self._client(provider)
            if client is None:
                continue
            attempted.append(provider)
            try:
                return client(prompt)
            except Exception as exc:
                last_exc = exc
                logger.warning("[FallbackLLM] '%s' çağrısı başarısız, sıradakine geçiliyor: %s", provider, exc)
        raise RuntimeError(
            f"Tüm LLM sağlayıcıları başarısız oldu (denenen: {attempted or self.providers}). "
            f"Son hata: {last_exc}"
        )


def get_llm_clients(enable_fallback: bool = True) -> Tuple[LLMCallable, LLMCallable]:
    """
    LLM_PROVIDER birincil; başarısız olursa diğer sağlayıcılara düşen (small, large) döndürür.

    Args:
        enable_fallback: False ise yalnızca birincil sağlayıcı (eski davranış,
                         örn. değerlendirme/ablation'da tek modeli sabitlemek için).

    Dönüş:
        (llm_small, llm_large)  # her ikisi de Callable[[str], str]
    """
    provider = (LLM_PROVIDER or "groq").lower()
    if provider not in _PROVIDER_BUILDERS:
        raise ValueError(
            f"Desteklenmeyen LLM_PROVIDER: '{provider}'\n"
            f"Geçerli değerler: {', '.join(_PROVIDER_BUILDERS)}"
        )

    if not enable_fallback:
        return _PROVIDER_BUILDERS[provider]()

    # Birincil önce, sonra varsayılan sıradaki diğerleri (tekrarsız)
    order = [provider] + [p for p in _DEFAULT_FALLBACK_ORDER if p != provider]
    shared_cache: Dict[str, Optional[Tuple[LLMCallable, LLMCallable]]] = {}
    small = FallbackLLM("small", order, shared_cache)
    large = FallbackLLM("large", order, shared_cache)
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