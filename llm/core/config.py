# llm/core/config.py
from __future__ import annotations

import os
from typing import Literal
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


LLMProvider = Literal["huggingface", "openai", "groq", "ollama", "novita"]


@dataclass(frozen=True)
class Config:
    """Model adlari/timeout config.json'dan, API anahtarlari .env'den."""

    llm_provider: LLMProvider
    hf_api_key: str
    hf_small_model: str
    hf_large_model: str
    openai_api_key: str
    openai_small_model: str
    openai_large_model: str
    groq_api_key: str
    groq_small_model: str
    groq_large_model: str
    ollama_base_url: str
    ollama_small_model: str
    ollama_large_model: str
    novita_small_model: str
    novita_large_model: str
    small_model_temperature: float
    large_model_temperature: float
    max_tokens: int
    enable_debug_logs: bool
    enable_judge_step: bool
    enable_correction_step: bool
    request_timeout: int
    max_retries: int

    def __post_init__(self) -> None:
        if not 0.0 <= self.small_model_temperature <= 2.0:
            raise ValueError(f"Invalid small_model_temperature: {self.small_model_temperature}")
        if not 0.0 <= self.large_model_temperature <= 2.0:
            raise ValueError(f"Invalid large_model_temperature: {self.large_model_temperature}")
        if self.max_tokens < 100:
            raise ValueError(f"max_tokens too low: {self.max_tokens}")
        if self.request_timeout < 10:
            raise ValueError(f"request_timeout too low: {self.request_timeout}s")
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("LLM_PROVIDER=openai but OPENAI_API_KEY is empty")
        if self.llm_provider == "groq" and not self.groq_api_key:
            raise ValueError("LLM_PROVIDER=groq but GROQ_API_KEY is empty")
        if self.llm_provider == "huggingface" and not self.hf_api_key:
            raise ValueError("LLM_PROVIDER=huggingface but HF_API_KEY is empty")
        if self.llm_provider == "novita" and not os.getenv("NOVITA_API_KEY"):
            raise ValueError("LLM_PROVIDER=novita but NOVITA_API_KEY is empty")

    def get_active_models(self) -> tuple[str, str]:
        if self.llm_provider == "openai":
            return (self.openai_small_model, self.openai_large_model)
        elif self.llm_provider == "groq":
            return (self.groq_small_model, self.groq_large_model)
        elif self.llm_provider == "ollama":
            return (self.ollama_small_model, self.ollama_large_model)
        elif self.llm_provider == "novita":
            return (self.novita_small_model, self.novita_large_model)
        return (self.hf_small_model, self.hf_large_model)

    def print_summary(self) -> None:
        if not self.enable_debug_logs:
            return
        small, large = self.get_active_models()
        print("\n" + "=" * 60)
        print("CONFIGURATION SUMMARY")
        print("=" * 60)
        print(f"  Provider:    {self.llm_provider.upper()}")
        print(f"  Small Model: {small}")
        print(f"  Large Model: {large}")
        print(f"  Max Tokens:  {self.max_tokens}")
        print(f"  Timeout:     {self.request_timeout}s")
        print(f"  Max Retries: {self.max_retries}")
        print("=" * 60 + "\n")


# Helpers

def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()

def _env_bool(key: str, default: bool = False) -> bool:
    return _env(key, str(default)).lower() in ("true", "1", "yes", "on")

def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default

def _env_float(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default

def _pmodel(providers: dict, provider: str, size: str, field: str, fallback: str) -> str:
    """config.json providers sozlugunden model bilgisi oku."""
    v = providers.get(provider, {}).get("models", {}).get(size, {}).get(field, fallback)
    return str(v)


# Config Loader

def load_config() -> Config:
    """
    Model/timeout degerlerini config.json'dan yukle.
    API anahtarlari yalnizca .env'den okunur.
    .env override her zaman gecerli.
    """
    try:
        from config.config_loader import get_config as _get
        _app = _get()
        llm_cfg = _app.llm
        pl_cfg = _app.pipeline
        providers = llm_cfg.providers
        json_provider = llm_cfg.default_provider
        json_timeout = llm_cfg.timeout
        json_retries = llm_cfg.max_retries
        json_debug = pl_cfg.enable_debug_logs
        json_judge = pl_cfg.enable_judge_step
        json_correction = pl_cfg.enable_correction_step
    except Exception:
        providers = {}
        json_provider = "groq"
        json_timeout = 60
        json_retries = 3
        json_debug = False
        json_judge = True
        json_correction = True

    provider_str = _env("LLM_PROVIDER", json_provider).lower()
    if provider_str not in ("huggingface", "openai", "groq", "ollama", "novita"):
        raise ValueError(f"Invalid LLM_PROVIDER: {provider_str!r}")
    provider: LLMProvider = provider_str  # type: ignore[assignment]

    groq_small   = _env("GROQ_SMALL_MODEL_NAME",   _pmodel(providers, "groq",   "small", "name", "llama-3.1-8b-instant"))
    groq_large   = _env("GROQ_LARGE_MODEL_NAME",   _pmodel(providers, "groq",   "large", "name", "llama-3.3-70b-versatile"))
    novita_small = _env("NOVITA_SMALL_MODEL_NAME", _pmodel(providers, "novita", "small", "name", "qwen/qwen3.5-35b-a3b"))
    novita_large = _env("NOVITA_LARGE_MODEL_NAME", _pmodel(providers, "novita", "large", "name", "qwen/qwen3.5-122b-a10b"))
    openai_small = _env("OPENAI_SMALL_MODEL_NAME", _pmodel(providers, "openai", "small", "name", "gpt-4o-mini"))
    openai_large = _env("OPENAI_LARGE_MODEL_NAME", _pmodel(providers, "openai", "large", "name", "gpt-4o"))
    ollama_small = _env("OLLAMA_SMALL_MODEL_NAME", _pmodel(providers, "ollama", "small", "name", "llama3.1:8b"))
    ollama_large = _env("OLLAMA_LARGE_MODEL_NAME", _pmodel(providers, "ollama", "large", "name", "llama3.1:70b"))

    json_small_temp = float(_pmodel(providers, provider_str, "small", "temperature", "0.3"))
    json_large_temp = float(_pmodel(providers, provider_str, "large", "temperature", "0.2"))
    json_max_tokens = int(  _pmodel(providers, provider_str, "small", "max_tokens",  "2048"))
    ollama_base_url = providers.get("ollama", {}).get("base_url", "http://localhost:11434")

    return Config(
        llm_provider=provider,
        hf_api_key=_env("HF_API_KEY"),
        hf_small_model=_env("SMALL_MODEL_NAME", "mistralai/Mistral-7B-Instruct-v0.2"),
        hf_large_model=_env("LARGE_MODEL_NAME", "mistralai/Mixtral-8x7B-Instruct-v0.1"),
        openai_api_key=_env("OPENAI_API_KEY"),
        openai_small_model=openai_small,
        openai_large_model=openai_large,
        groq_api_key=_env("GROQ_API_KEY"),
        groq_small_model=groq_small,
        groq_large_model=groq_large,
        novita_small_model=novita_small,
        novita_large_model=novita_large,
        ollama_base_url=_env("OLLAMA_BASE_URL", ollama_base_url),
        ollama_small_model=ollama_small,
        ollama_large_model=ollama_large,
        small_model_temperature=_env_float("SMALL_MODEL_TEMPERATURE", json_small_temp),
        large_model_temperature=_env_float("LARGE_MODEL_TEMPERATURE", json_large_temp),
        max_tokens=_env_int("MAX_TOKENS", json_max_tokens),
        enable_debug_logs=_env_bool("ENABLE_DEBUG_LOGS", json_debug),
        enable_judge_step=_env_bool("ENABLE_JUDGE_STEP", json_judge),
        enable_correction_step=_env_bool("ENABLE_CORRECTION_STEP", json_correction),
        request_timeout=_env_int("REQUEST_TIMEOUT", json_timeout),
        max_retries=_env_int("MAX_RETRIES", json_retries),
    )


# Global Instance

try:
    CONFIG = load_config()
except Exception as e:
    import sys
    sys.stderr.write(f"Config loading failed: {e}\n")
    raise


# Backward Compatibility

LLM_PROVIDER = CONFIG.llm_provider

HF_API_KEY           = CONFIG.hf_api_key
SMALL_MODEL_NAME     = CONFIG.hf_small_model
LARGE_MODEL_NAME     = CONFIG.hf_large_model

OPENAI_API_KEY           = CONFIG.openai_api_key
OPENAI_SMALL_MODEL_NAME  = CONFIG.openai_small_model
OPENAI_LARGE_MODEL_NAME  = CONFIG.openai_large_model

GROQ_API_KEY           = CONFIG.groq_api_key
GROQ_SMALL_MODEL_NAME  = CONFIG.groq_small_model
GROQ_LARGE_MODEL_NAME  = CONFIG.groq_large_model

OLLAMA_BASE_URL          = CONFIG.ollama_base_url
OLLAMA_SMALL_MODEL_NAME  = CONFIG.ollama_small_model
OLLAMA_LARGE_MODEL_NAME  = CONFIG.ollama_large_model

SMALL_MODEL_TEMPERATURE = CONFIG.small_model_temperature
LARGE_MODEL_TEMPERATURE = CONFIG.large_model_temperature
MAX_TOKENS              = CONFIG.max_tokens

# Network reliability — SDK'lara timeout + retry (exp backoff + Retry-After) geçirmek için
REQUEST_TIMEOUT         = CONFIG.request_timeout
MAX_RETRIES             = CONFIG.max_retries

ENABLE_DEBUG_LOGS      = CONFIG.enable_debug_logs
ENABLE_JUDGE_STEP      = CONFIG.enable_judge_step
ENABLE_CORRECTION_STEP = CONFIG.enable_correction_step


def print_config_summary() -> None:
    CONFIG.print_summary()
