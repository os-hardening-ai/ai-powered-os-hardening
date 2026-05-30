# models/openai_client.py
from __future__ import annotations

from typing import Any

try:
    from openai import OpenAI  # openai>=1.0.0 (new API)
    NEW_API_AVAILABLE = True
except ImportError:
    NEW_API_AVAILABLE = False
    OpenAI = None  # type: ignore[assignment,misc]

from llm.core.config import (
    OPENAI_API_KEY,
    OPENAI_SMALL_MODEL_NAME,
    OPENAI_LARGE_MODEL_NAME,
    SMALL_MODEL_TEMPERATURE,
    LARGE_MODEL_TEMPERATURE,
    MAX_TOKENS,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
)
from llm.clients import token_tracker


class OpenAIClient:
    """
    OpenAI ChatCompletion üzerinden çalışan client.

    openai>=1.0.0 için yeni API kullanır (OpenAI client instance).

    Pipeline entegrasyonu için:
      - __call__(prompt: str) -> str
    arayüzünü destekler.
    """

    def __init__(
        self,
        model_name: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        if not OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY tanımlı değil. Lütfen .env veya ortam değişkeni ile ayarla."
            )

        if not NEW_API_AVAILABLE:
            raise RuntimeError(
                "openai>=1.0.0 paketi yüklü değil. Lütfen 'pip install openai>=1.0.0' çalıştırın."
            )

        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        # 429/5xx: SDK retry (exp backoff + Retry-After) + timeout (asılı socket sınırı)
        self.timeout = float(timeout if timeout is not None else REQUEST_TIMEOUT)
        self.max_retries = int(max_retries if max_retries is not None else MAX_RETRIES)
        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

    def __call__(self, prompt: str) -> str:
        """
        Chat completion isteği yapar.
        Sistem mesajı eklemiyoruz; pipeline prompt'un tamamı tek user mesajında.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            content = response.choices[0].message.content

            if content is None:
                raise RuntimeError("OpenAI API boş content döndürdü")

            if response.usage:
                token_tracker.add(response.usage.total_tokens)

            return content

        except Exception as exc:
            raise RuntimeError(
                f"OpenAI API çağrısı başarısız: {str(exc)}\n"
                f"Model: {self.model_name}"
            ) from exc


def get_small_openai_llm() -> OpenAIClient:
    return OpenAIClient(
        model_name=OPENAI_SMALL_MODEL_NAME,
        temperature=SMALL_MODEL_TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )


def get_large_openai_llm() -> OpenAIClient:
    return OpenAIClient(
        model_name=OPENAI_LARGE_MODEL_NAME,
        temperature=LARGE_MODEL_TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
