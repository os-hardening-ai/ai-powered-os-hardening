# llm/clients/huggingface_client.py
"""
HuggingFace Serverless Inference API client — ÜCRETSIZ tier.

chat_completion'ı dener, model onu desteklemiyorsa text_generation'a düşer.
Hatalar ortak taksonomiye (base.py) çevrilir → fallback handler tutarlı karar verir.

HF_API_KEY gerekir (ücretsiz alınır: https://huggingface.co/settings/tokens).
Anahtar yoksa client kurulurken AuthError verir → registry/fallback onu atlar.
"""

from __future__ import annotations

import logging
import threading

from llm.core.config import (
    HF_API_KEY,
    SMALL_MODEL_NAME,
    LARGE_MODEL_NAME,
    SMALL_MODEL_TEMPERATURE,
    LARGE_MODEL_TEMPERATURE,
    MAX_TOKENS,
    MAX_RETRIES,
)
from llm.clients.base import (
    AuthError,
    RateLimitError,
    ModelUnavailableError,
    classify_error,
)

logger = logging.getLogger(__name__)


class HuggingFaceClient:
    """HF Serverless Inference (provider='hf-inference'), ücretsiz tier."""

    def __init__(
        self,
        model_name: str,
        temperature: float = 0.3,
        max_tokens: int = 512,
        max_retries: int | None = None,
    ) -> None:
        if not HF_API_KEY:
            raise AuthError(
                "HF_API_KEY tanımlı değil (ücretsiz token: huggingface.co/settings/tokens)",
                "huggingface",
            )
        try:
            from huggingface_hub import InferenceClient
        except ImportError as exc:  # paket yoksa sağlayıcı kullanılamaz
            raise ModelUnavailableError(
                "huggingface_hub paketi kurulu değil", "huggingface", cause=exc
            )

        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = int(max_retries if max_retries is not None else MAX_RETRIES)
        self._lock = threading.Lock()
        self.client = InferenceClient(token=HF_API_KEY, provider="hf-inference")
        logger.info("[OK] HuggingFace - Model: %s", model_name)

    def __call__(self, prompt: str) -> str:
        try:
            return self._chat(prompt)
        except (AttributeError, KeyError, TypeError):
            # chat desteklenmiyorsa text generation'a düş
            try:
                return self._text(prompt)
            except Exception as exc:
                raise classify_error(exc, "huggingface")
        except Exception as exc:
            raise classify_error(exc, "huggingface")

    def _chat(self, prompt: str) -> str:
        with self._lock:
            resp = self.client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        content = resp.choices[0].message.content
        if not content:
            raise ModelUnavailableError("HF boş content döndürdü", "huggingface")
        return content.strip()

    def _text(self, prompt: str) -> str:
        with self._lock:
            resp = self.client.text_generation(
                prompt=prompt,
                model=self.model_name,
                temperature=self.temperature,
                max_new_tokens=self.max_tokens,
                return_full_text=False,
            )
        return resp.strip()


def get_small_hf_llm() -> HuggingFaceClient:
    return HuggingFaceClient(
        model_name=SMALL_MODEL_NAME,
        temperature=SMALL_MODEL_TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )


def get_large_hf_llm() -> HuggingFaceClient:
    return HuggingFaceClient(
        model_name=LARGE_MODEL_NAME,
        temperature=LARGE_MODEL_TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
