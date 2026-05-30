# llm/clients/novita_llm_client.py
from __future__ import annotations
from openai import OpenAI
from llm.core.config import (
    NOVITA_API_KEY,
    NOVITA_BASE_URL,
    NOVITA_SMALL_MODEL_NAME,
    NOVITA_LARGE_MODEL_NAME,
    SMALL_MODEL_TEMPERATURE,
    LARGE_MODEL_TEMPERATURE,
    MAX_TOKENS,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
)


class NovitaLLMClient:
    """
    Novita AI LLM client (OpenAI-compatible API).

    Novita: GPU cloud + LLM inference. Pay-per-use, OpenAI uyumlu.
    """

    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 512,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        if not api_key:
            raise RuntimeError("NOVITA_API_KEY tanımlı değil")

        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        # 429/5xx: SDK retry (exp backoff + Retry-After) + timeout (asılı socket sınırı)
        self.timeout = float(timeout if timeout is not None else REQUEST_TIMEOUT)
        self.max_retries = int(max_retries if max_retries is not None else MAX_RETRIES)
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url or NOVITA_BASE_URL,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        print(f"[OK] Novita LLM - Model: {model_name} (timeout={self.timeout}s, retries={self.max_retries})")

    def __call__(self, prompt: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("Novita API boş content döndürdü")
            return content.strip()
        except Exception as e:
            error_msg = str(e)
            if "rate_limit" in error_msg.lower() or "429" in error_msg:
                raise RuntimeError("⚠️  Novita rate limit aşıldı") from e
            raise RuntimeError(f"Novita API hatası: {error_msg}") from e


def get_small_novita_llm() -> NovitaLLMClient:
    return NovitaLLMClient(
        model_name=NOVITA_SMALL_MODEL_NAME,
        api_key=NOVITA_API_KEY,
        base_url=NOVITA_BASE_URL,
        temperature=SMALL_MODEL_TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )


def get_large_novita_llm() -> NovitaLLMClient:
    return NovitaLLMClient(
        model_name=NOVITA_LARGE_MODEL_NAME,
        api_key=NOVITA_API_KEY,
        base_url=NOVITA_BASE_URL,
        temperature=LARGE_MODEL_TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
