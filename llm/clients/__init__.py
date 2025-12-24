# models/__init__.py
from __future__ import annotations

from typing import Callable, Tuple

# Import from core.config
from llm.core.config import LLM_PROVIDER

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


def get_llm_clients() -> Tuple[LLMCallable, LLMCallable]:
    """
    Konfigürasyondaki LLM_PROVIDER değerine göre küçük ve büyük modeli döndürür.

    Dönüş:
        (llm_small, llm_large)  # her ikisi de Callable[[str], str]
    """
    provider = (LLM_PROVIDER or "groq").lower()

    if provider == "openai":
        return _get_openai_clients()
    elif provider == "groq":
        return _get_groq_clients()
    elif provider == "ollama":
        return _get_ollama_clients()
    elif provider == "huggingface":
        return _get_hf_clients()
    else:
        raise ValueError(
            f"Desteklenmeyen LLM_PROVIDER: '{provider}'\n"
            f"Geçerli değerler: 'groq' (FREE), 'ollama' (FREE Local), 'openai', 'huggingface'"
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


def get_llm_clients_with_fallback() -> Tuple[LLMCallable, LLMCallable]:
    """
    Get LLM clients with automatic provider fallback.

    Returns small and large models that automatically fallback to secondary
    providers if primary fails (Groq → OpenAI → Ollama).

    Returns:
        (llm_small, llm_large): Both support automatic fallback
    """
    from .fallback_handler import FallbackHandler

    handler = FallbackHandler()

    # Register providers in priority order
    try:
        handler.register_provider(
            name="groq",
            client_factory=lambda: _get_groq_clients()[0],  # small model
            priority=1,
            enabled=True
        )
    except:
        pass  # Groq not available

    try:
        handler.register_provider(
            name="openai",
            client_factory=lambda: _get_openai_clients()[0],  # small model
            priority=2,
            enabled=False  # Disabled by default (paid)
        )
    except:
        pass

    try:
        handler.register_provider(
            name="ollama",
            client_factory=lambda: _get_ollama_clients()[0],  # small model
            priority=3,
            enabled=True
        )
    except:
        pass

    # Create small model with fallback
    def llm_small_with_fallback(prompt: str) -> str:
        response, _ = handler.call_with_fallback(prompt, verbose=False)
        return response

    # Similar for large model
    handler_large = FallbackHandler()
    try:
        handler_large.register_provider("groq", lambda: _get_groq_clients()[1], 1)
    except:
        pass
    try:
        handler_large.register_provider("openai", lambda: _get_openai_clients()[1], 2, enabled=False)
    except:
        pass
    try:
        handler_large.register_provider("ollama", lambda: _get_ollama_clients()[1], 3)
    except:
        pass

    def llm_large_with_fallback(prompt: str) -> str:
        response, _ = handler_large.call_with_fallback(prompt, verbose=False)
        return response

    return llm_small_with_fallback, llm_large_with_fallback


__all__ = ["get_llm_clients", "get_llm_clients_with_fallback", "llm_small", "llm_large"]