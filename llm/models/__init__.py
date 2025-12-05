# models/__init__.py
from __future__ import annotations

from typing import Callable, Tuple

# Relative import - llm.config yerine parent package'dan config import et
from ..config import LLM_PROVIDER

LLMCallable = Callable[[str], str]


def _get_hf_clients() -> Tuple[LLMCallable, LLMCallable]:
    """Hugging Face client'larını local import ile al."""
    from .huggingface_client import get_small_hf_llm, get_large_hf_llm

    small = get_small_hf_llm()
    large = get_large_hf_llm()
    return small, large


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


def get_llm_clients() -> Tuple[LLMCallable, LLMCallable]:
    """
    Konfigürasyondaki LLM_PROVIDER değerine göre küçük ve büyük modeli döndürür.

    Dönüş:
        (llm_small, llm_large)  # her ikisi de Callable[[str], str]
    """
    provider = (LLM_PROVIDER or "huggingface").lower()

    if provider == "openai":
        return _get_openai_clients()
    elif provider == "groq":
        return _get_groq_clients()
    elif provider == "huggingface":
        return _get_hf_clients()
    else:
        raise ValueError(
            f"Desteklenmeyen LLM_PROVIDER: '{provider}'\n"
            f"Geçerli değerler: 'openai', 'groq', 'huggingface'"
        )


# WARNING: Module-level initialization sorunları yaşanmaması için
# llm_small ve llm_large'ı doğrudan kullanmak yerine get_llm_clients()
# fonksiyonunu kullanın. Ancak backward compatibility için hala export ediyoruz.

# Module seviyesinde export et - ancak dikkatli kullanılmalı
try:
    llm_small, llm_large = get_llm_clients()
except Exception as e:
    # Import-time hata olursa warningtümizle ama crash etmeyelim
    import warnings
    warnings.warn(
        f"LLM clients initialization failed: {e}\n"
        f"Use get_llm_clients() directly in your code instead of importing llm_small/llm_large.",
        RuntimeWarning,
    )
    # Dummy callable for type checker
    llm_small = lambda x: ""  # type: ignore[assignment]
    llm_large = lambda x: ""  # type: ignore[assignment]


__all__ = ["get_llm_clients", "llm_small", "llm_large"]