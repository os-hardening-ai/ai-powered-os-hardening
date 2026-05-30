from __future__ import annotations

from openai import OpenAI

from llm.core.config import (
    CONFIG,
    SMALL_MODEL_TEMPERATURE,
    LARGE_MODEL_TEMPERATURE,
    MAX_TOKENS,
)
from llm.clients import token_tracker


class NovitaLLMClient:
    """
    Novita.ai üzerinde OpenAI-uyumlu LLM client.

    Modeller: Qwen3.5-35B-A3B (small), Qwen3.5-122B-A10B (large)
    Base URL: https://api.novita.ai/openai
    """

    # Karakter başına yaklaşık token sayısı (Türkçe/İngilizce karışık için)
    _CHARS_PER_TOKEN = 4
    # Model context limitinden güvenli tampon
    _SAFETY_BUFFER = 256

    def __init__(
        self,
        model_name: str,
        api_key: str,
        temperature: float = 0.3,
        max_tokens: int = 8192,
        base_url: str = "https://api.novita.ai/openai",
        context_limit: int = 16384,
    ) -> None:
        if not api_key:
            raise RuntimeError(
                "NOVITA_API_KEY tanımlı değil. .env dosyanı kontrol et."
            )

        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_limit = context_limit
        self._client = OpenAI(api_key=api_key, base_url=base_url)

        print(f"[OK] Novita LLM - Model: {model_name}")

    def _safe_max_tokens(self, prompt: str) -> int:
        """Input boyutuna göre context sınırını aşmayan max_tokens hesaplar."""
        estimated_input = len(prompt) // self._CHARS_PER_TOKEN
        available = self.context_limit - estimated_input - self._SAFETY_BUFFER
        return max(256, min(self.max_tokens, available))

    def __call__(self, prompt: str) -> str:
        """Modele prompt gönder ve cevap al."""
        try:
            actual_max_tokens = self._safe_max_tokens(prompt)
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=actual_max_tokens,
            )

            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("Novita LLM API boş content döndürdü")

            if response.usage:
                token_tracker.add(response.usage.total_tokens)

            return content.strip()

        except Exception as e:
            error_msg = str(e)

            if "rate_limit" in error_msg.lower() or "429" in error_msg:
                raise RuntimeError(
                    "Novita rate limit aşıldı. Bir süre bekleyip tekrar dene."
                ) from e

            if "401" in error_msg or "unauthorized" in error_msg.lower():
                raise RuntimeError(
                    "Novita API key geçersiz. NOVITA_API_KEY değerini kontrol et."
                ) from e

            raise RuntimeError(f"Novita LLM hatası: {error_msg}") from e


def get_small_novita_llm() -> NovitaLLMClient:
    """Küçük/hızlı Novita model instance'ı."""
    import os
    api_key = os.getenv("NOVITA_API_KEY", "")
    return NovitaLLMClient(
        model_name=CONFIG.novita_small_model,
        api_key=api_key,
        temperature=SMALL_MODEL_TEMPERATURE,
        max_tokens=MAX_TOKENS,
        context_limit=16384,
    )


def get_large_novita_llm() -> NovitaLLMClient:
    """Büyük/güçlü Novita model instance'ı."""
    import os
    api_key = os.getenv("NOVITA_API_KEY", "")
    return NovitaLLMClient(
        model_name=CONFIG.novita_large_model,
        api_key=api_key,
        temperature=LARGE_MODEL_TEMPERATURE,
        max_tokens=MAX_TOKENS,
        context_limit=16384,
    )
