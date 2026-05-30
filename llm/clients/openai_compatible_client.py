# llm/clients/openai_compatible_client.py
"""
Generic OpenAI-uyumlu LLM client — TEK client, ÇOK sağlayıcı.

Cerebras, SambaNova, DeepInfra, Novita, OpenRouter, Together, Fireworks, Mistral,
Gemini (OpenAI-uyumlu uç) ve Groq'un `/openai/v1` ucu — hepsi aynı OpenAI Chat
Completions sözleşmesini konuşur. Bu yüzden her biri için ayrı dosya yerine
**base_url + model** değişimiyle çalışan tek client yeterli (novita_llm_client deseni
genelleştirildi). Hatalar `base.py` taksonomisine çevrilir → fallback handler tutarlı
karar verir (429/auth/timeout/model-unavailable).

Sağlayıcı ön-ayarları `PROVIDER_PRESETS`'te; `build_from_preset("cerebras")` env'den
anahtarı okuyup hazır client döndürür. Model adları deprecation ile değişebildiği için
her sağlayıcı `<PROVIDER>_MODEL` / `<PROVIDER>_BASE_URL` env'leriyle override edilebilir.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

from openai import OpenAI

from llm.clients import token_tracker
from llm.clients.base import AuthError, ModelUnavailableError, classify_error
from llm.core.config import MAX_TOKENS, MAX_RETRIES, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class OpenAICompatibleClient:
    """Herhangi bir OpenAI-uyumlu sağlayıcı için çağrılabilir LLM: ``client(prompt) -> str``."""

    def __init__(
        self,
        *,
        provider: str,
        model_name: str,
        api_key: str,
        base_url: str,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        if not api_key:
            # Anahtar yoksa kurulurken AuthError → registry/fallback bu sağlayıcıyı atlar.
            raise AuthError(f"{provider}: API anahtarı tanımlı değil", provider)

        self.provider = provider
        self.model_name = model_name
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = int(max_tokens if max_tokens is not None else MAX_TOKENS)
        # 429/5xx: SDK retry (exp backoff + Retry-After) + timeout (asılı socket sınırı)
        self.timeout = float(timeout if timeout is not None else REQUEST_TIMEOUT)
        self.max_retries = int(max_retries if max_retries is not None else MAX_RETRIES)
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        logger.info(
            "[OK] %s LLM - Model: %s (base=%s, timeout=%ss, retries=%s)",
            provider, model_name, base_url, self.timeout, self.max_retries,
        )

    def __call__(self, prompt: str) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            content = resp.choices[0].message.content
            if not content:
                raise ModelUnavailableError(f"{self.provider}: boş content döndü", self.provider)
            if getattr(resp, "usage", None):
                token_tracker.add(resp.usage.total_tokens)
            return content.strip()
        except Exception as exc:  # ham SDK hatasını ortak taksonomiye çevir
            raise classify_error(exc, self.provider)


# ── Sağlayıcı ön-ayarları ────────────────────────────────────────────────────────
# base_url + makul varsayılan model + env anahtar adı. Model adları DEĞİŞEBİLİR
# (deprecation) → `<PROVIDER>_MODEL` env'i ile geçersiz kıl. Hepsi OpenAI-uyumlu.
PROVIDER_PRESETS: Dict[str, Dict[str, str]] = {
    "cerebras":  {"base_url": "https://api.cerebras.ai/v1",
                  "model": "gpt-oss-120b",                              "key_env": "CEREBRAS_API_KEY"},
    "sambanova": {"base_url": "https://api.sambanova.ai/v1",
                  "model": "gpt-oss-120b",                              "key_env": "SAMBANOVA_API_KEY"},
    "deepinfra": {"base_url": "https://api.deepinfra.com/v1/openai",
                  "model": "meta-llama/Llama-3.3-70B-Instruct",         "key_env": "DEEPINFRA_API_KEY"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1",
                   "model": "meta-llama/llama-3.3-70b-instruct",        "key_env": "OPENROUTER_API_KEY"},
    "together":  {"base_url": "https://api.together.xyz/v1",
                  "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",   "key_env": "TOGETHER_API_KEY"},
    "fireworks": {"base_url": "https://api.fireworks.ai/inference/v1",
                  "model": "accounts/fireworks/models/llama-v3p3-70b-instruct", "key_env": "FIREWORKS_API_KEY"},
    "mistral":   {"base_url": "https://api.mistral.ai/v1",
                  "model": "mistral-small-latest",                      "key_env": "MISTRAL_API_KEY"},
    "gemini":    {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                  "model": "gemini-2.5-flash",                          "key_env": "GEMINI_API_KEY"},
    "groq":      {"base_url": "https://api.groq.com/openai/v1",
                  "model": "llama-3.3-70b-versatile",                   "key_env": "GROQ_API_KEY"},
    "novita":    {"base_url": "https://api.novita.ai/openai",
                  "model": "meta-llama/llama-3.1-8b-instruct",          "key_env": "NOVITA_API_KEY"},
}


def preset_api_key(provider: str) -> str:
    """Sağlayıcının env anahtarını oku ('' ise yok)."""
    p = PROVIDER_PRESETS[provider]
    return os.environ.get(p["key_env"], "") or ""


def build_from_preset(
    provider: str,
    *,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
) -> OpenAICompatibleClient:
    """Ön-ayardan client kur. Model/base_url env ile override edilebilir.

    Anahtar yoksa AuthError fırlatır (çağıran taraf yakalayıp sağlayıcıyı atlayabilir).
    """
    if provider not in PROVIDER_PRESETS:
        raise ValueError(f"Bilinmeyen sağlayıcı: {provider} (geçerli: {', '.join(PROVIDER_PRESETS)})")
    p = PROVIDER_PRESETS[provider]
    up = provider.upper()
    return OpenAICompatibleClient(
        provider=provider,
        model_name=model or os.environ.get(f"{up}_MODEL") or p["model"],
        api_key=os.environ.get(p["key_env"], "") or "",
        base_url=os.environ.get(f"{up}_BASE_URL") or p["base_url"],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=max_retries,
    )


# ── (small, large) factory'leri — registry/builders bunları kullanır ─────────────
# small = sınıflandırma/doğrulama (SMALL_MODEL_TEMPERATURE), large = üretim
# (LARGE_MODEL_TEMPERATURE). Cerebras'ta tek hızlı model (gpt-oss-120b) olduğundan
# small=large modeli, yalnızca temperature ayrışır.
#
# FAIL-FAST: zincir client'larında max_retries=0. FallbackLLM zaten sağlayıcılar
# arası retry katmanıdır; SDK'nın provider-İÇİ retry'ı (429'da Retry-After ile 30-60s
# backoff) fallback'i geciktiriyordu (H3 testinde rate-limited cerebras 56-63s'ye
# çıkarıyordu). 0 retry → 429/hata anında bir sonraki HIZLI sağlayıcıya (sambanova) düşer.
_CHAIN_RETRIES = 0


def get_small_cerebras_llm() -> OpenAICompatibleClient:
    from llm.core.config import SMALL_MODEL_TEMPERATURE
    # NOT: Cerebras'ta llama3.1-8b ($0.10) UI'da görünüyor ama API id'si canlı testte
    # erişilemez döndü → small DA gpt-oss-120b (kanıtlı 1.36s; free tier'da maliyet $0).
    # Daha ucuz small isteniyorsa CEREBRAS_SMALL_MODEL ile doğru API id verilmeli.
    model = os.environ.get("CEREBRAS_SMALL_MODEL", "gpt-oss-120b")
    return build_from_preset("cerebras", model=model, temperature=SMALL_MODEL_TEMPERATURE, max_retries=_CHAIN_RETRIES)


def get_large_cerebras_llm() -> OpenAICompatibleClient:
    from llm.core.config import LARGE_MODEL_TEMPERATURE
    # large = gpt-oss-120b ($0.35/$0.75, frontier reasoning MoE) — üretim
    model = os.environ.get("CEREBRAS_LARGE_MODEL", "gpt-oss-120b")
    return build_from_preset("cerebras", model=model, temperature=LARGE_MODEL_TEMPERATURE, max_retries=_CHAIN_RETRIES)


def get_small_sambanova_llm() -> OpenAICompatibleClient:
    from llm.core.config import SMALL_MODEL_TEMPERATURE
    return build_from_preset("sambanova", temperature=SMALL_MODEL_TEMPERATURE, max_retries=_CHAIN_RETRIES)


def get_large_sambanova_llm() -> OpenAICompatibleClient:
    from llm.core.config import LARGE_MODEL_TEMPERATURE
    return build_from_preset("sambanova", temperature=LARGE_MODEL_TEMPERATURE, max_retries=_CHAIN_RETRIES)
