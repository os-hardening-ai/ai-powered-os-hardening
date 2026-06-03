# models/groq_client.py
from __future__ import annotations
import logging
from typing import Optional
from groq import Groq
from llm.core.config import (
    GROQ_API_KEY,
    GROQ_SMALL_MODEL_NAME,
    GROQ_LARGE_MODEL_NAME,
    SMALL_MODEL_TEMPERATURE,
    LARGE_MODEL_TEMPERATURE,
    MAX_TOKENS,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
)
from llm.clients import token_tracker
from llm.clients.base import classify_error

logger = logging.getLogger(__name__)


class GroqClient:
    """
    Groq API client - Ultra hızlı ve ucuz LLM inference.

    Maliyet: $0.27/1M token (OpenAI'nin %90 ucuz)
    Hız: 500+ token/saniye (en hızlı API)
    Modeller: Llama 3.1, Mixtral, Gemma
    """

    def __init__(
        self,
        model_name: str,
        api_key: str,
        temperature: float = 0.3,
        max_tokens: int = 512,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY tanımlı değil. .env dosyanı kontrol et.\n"
                "Ücretsiz API key al: https://console.groq.com/keys"
            )

        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = float(timeout if timeout is not None else REQUEST_TIMEOUT)
        self.max_retries = int(max_retries if max_retries is not None else MAX_RETRIES)
        self.client = Groq(
            api_key=api_key,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        logger.info("[OK] Groq API - Model: %s (timeout=%ss, retries=%s)", model_name, self.timeout, self.max_retries)

    def _messages(self, prompt: str, system: Optional[str] = None) -> list:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    def __call__(self, prompt: str, system: Optional[str] = None) -> str:
        """Modele prompt gönder ve cevap al. system verilirse grounding direktifi olarak eklenir."""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=self._messages(prompt, system),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            content = response.choices[0].message.content

            if content is None:
                raise RuntimeError("Groq API boş content döndürdü")

            if response.usage:
                token_tracker.add(response.usage.total_tokens)

            return content.strip()

        except Exception as exc:
            raise classify_error(exc, "groq")

    def stream(self, prompt: str, system: Optional[str] = None):
        """GERÇEK token streaming — Groq SDK stream=True ile token delta'larını yield eder."""
        try:
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=self._messages(prompt, system),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )
            got = False
            for chunk in stream:
                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                content = getattr(delta, "content", None) if delta is not None else None
                if content:
                    got = True
                    yield content
            if not got:
                raise RuntimeError(f"Groq stream boş döndü (model={self.model_name})")
        except Exception as exc:
            raise classify_error(exc, "groq")


def get_small_groq_llm() -> GroqClient:
    """Küçük/hızlı Groq model instance'ı"""
    return GroqClient(
        model_name=GROQ_SMALL_MODEL_NAME,
        api_key=GROQ_API_KEY,
        temperature=SMALL_MODEL_TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )


def get_large_groq_llm() -> GroqClient:
    """Büyük/güçlü Groq model instance'ı"""
    return GroqClient(
        model_name=GROQ_LARGE_MODEL_NAME,
        api_key=GROQ_API_KEY,
        temperature=LARGE_MODEL_TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )