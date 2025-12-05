# config.py
from __future__ import annotations

import os
from typing import Literal
from dataclasses import dataclass

# .env desteği
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ─────────────────────────────────────────────
# Type Definitions
# ─────────────────────────────────────────────

LLMProvider = Literal["huggingface", "openai", "groq"]


# ─────────────────────────────────────────────
# Configuration Class (Type-Safe)
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class Config:
    """
    Immutable configuration object.
    
    Avantajları:
    - Type-safe: IDE autocomplete çalışır
    - Immutable: Yanlışlıkla değiştirilemez
    - Validation: __post_init__ ile doğrulama yapılabilir
    """
    
    # ── LLM Provider ──
    llm_provider: LLMProvider
    
    # ── HuggingFace ──
    hf_api_key: str
    hf_small_model: str
    hf_large_model: str
    
    # ── OpenAI ──
    openai_api_key: str
    openai_small_model: str
    openai_large_model: str
    
    # ── Groq ──
    groq_api_key: str
    groq_small_model: str
    groq_large_model: str
    
    # ── Sampling Parameters ──
    small_model_temperature: float
    large_model_temperature: float
    max_tokens: int
    
    # ── Pipeline Behavior ──
    enable_debug_logs: bool
    enable_judge_step: bool
    enable_correction_step: bool
    
    # ── Advanced ──
    request_timeout: int  # API çağrıları için timeout (saniye)
    max_retries: int      # Hata durumunda retry sayısı
    
    def __post_init__(self) -> None:
        """Config doğrulama - hatalı değerleri yakala."""
        # Temperature validation
        if not 0.0 <= self.small_model_temperature <= 2.0:
            raise ValueError(
                f"❌ Invalid small_model_temperature: {self.small_model_temperature}\n"
                f"   Must be between 0.0 and 2.0\n"
                f"   Suggested values: 0.1-0.3 for classification, 0.5-0.7 for generation"
            )
        if not 0.0 <= self.large_model_temperature <= 2.0:
            raise ValueError(
                f"❌ Invalid large_model_temperature: {self.large_model_temperature}\n"
                f"   Must be between 0.0 and 2.0\n"
                f"   Suggested values: 0.2-0.4 for security content"
            )

        # Token validation
        if self.max_tokens < 100:
            raise ValueError(
                f"❌ max_tokens too low: {self.max_tokens}\n"
                f"   Must be at least 100, recommended: 1024-4096"
            )
        if self.max_tokens > 32000:
            import warnings
            warnings.warn(
                f"⚠️  max_tokens is very high: {self.max_tokens}\n"
                f"   This may increase costs and latency. Consider using 4096 or less.",
                UserWarning
            )

        # Timeout validation
        if self.request_timeout < 10:
            raise ValueError(
                f"❌ request_timeout too low: {self.request_timeout}s\n"
                f"   Must be at least 10 seconds to handle LLM responses"
            )

        # Retry validation
        if self.max_retries < 0:
            raise ValueError(f"❌ max_retries cannot be negative: {self.max_retries}")
        if self.max_retries > 5:
            import warnings
            warnings.warn(
                f"⚠️  max_retries is high: {self.max_retries}\n"
                f"   High retry counts may cause long delays on persistent errors.",
                UserWarning
            )

        # API key validation (provider'a göre)
        if self.llm_provider == "openai":
            if not self.openai_api_key:
                raise ValueError(
                    "❌ LLM_PROVIDER=openai but OPENAI_API_KEY is empty\n"
                    "   Get API key from: https://platform.openai.com/api-keys\n"
                    "   Add to .env: OPENAI_API_KEY=sk-..."
                )
            if not self.openai_api_key.startswith("sk-"):
                import warnings
                warnings.warn(
                    "⚠️  OPENAI_API_KEY doesn't start with 'sk-' - might be invalid",
                    UserWarning
                )

        if self.llm_provider == "groq":
            if not self.groq_api_key:
                raise ValueError(
                    "❌ LLM_PROVIDER=groq but GROQ_API_KEY is empty\n"
                    "   Get free API key from: https://console.groq.com/keys\n"
                    "   Add to .env: GROQ_API_KEY=gsk_..."
                )
            if not self.groq_api_key.startswith("gsk_"):
                import warnings
                warnings.warn(
                    "⚠️  GROQ_API_KEY doesn't start with 'gsk_' - might be invalid",
                    UserWarning
                )

        if self.llm_provider == "huggingface":
            if not self.hf_api_key:
                raise ValueError(
                    "❌ LLM_PROVIDER=huggingface but HF_API_KEY is empty\n"
                    "   Get API key from: https://huggingface.co/settings/tokens\n"
                    "   Add to .env: HF_API_KEY=hf_..."
                )
    
    def get_active_models(self) -> tuple[str, str]:
        """Aktif provider'ın model isimlerini döner (small, large)."""
        if self.llm_provider == "openai":
            return (self.openai_small_model, self.openai_large_model)
        elif self.llm_provider == "groq":
            return (self.groq_small_model, self.groq_large_model)
        else:  # huggingface
            return (self.hf_small_model, self.hf_large_model)
    
    def print_summary(self) -> None:
        """Config özetini yazdırır."""
        if not self.enable_debug_logs:
            return
        
        small, large = self.get_active_models()
        
        print("\n" + "="*60)
        print("⚙️  CONFIGURATION SUMMARY")
        print("="*60)
        print(f"  Provider:     {self.llm_provider.upper()}")
        print(f"  Small Model:  {small}")
        print(f"  Large Model:  {large}")
        print(f"  Max Tokens:   {self.max_tokens}")
        print(f"  Small Temp:   {self.small_model_temperature}")
        print(f"  Large Temp:   {self.large_model_temperature}")
        print(f"  Judge Step:   {'✅ Enabled' if self.enable_judge_step else '❌ Disabled'}")
        print(f"  Correction:   {'✅ Enabled' if self.enable_correction_step else '❌ Disabled'}")
        print(f"  Debug Logs:   {'✅ Enabled' if self.enable_debug_logs else '❌ Disabled'}")
        print(f"  Timeout:      {self.request_timeout}s")
        print(f"  Max Retries:  {self.max_retries}")
        print("="*60 + "\n")


# ─────────────────────────────────────────────
# Config Loading
# ─────────────────────────────────────────────

def _get_env(key: str, default: str = "") -> str:
    """Environment variable'ı oku, boşsa default döndür."""
    return os.getenv(key, default).strip()


def _get_env_bool(key: str, default: bool = False) -> bool:
    """Boolean environment variable'ı oku."""
    value = _get_env(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


def _get_env_int(key: str, default: int) -> int:
    """Integer environment variable'ı oku."""
    try:
        return int(_get_env(key, str(default)))
    except ValueError:
        return default


def _get_env_float(key: str, default: float) -> float:
    """Float environment variable'ı oku."""
    try:
        return float(_get_env(key, str(default)))
    except ValueError:
        return default


def load_config() -> Config:
    """
    Environment variable'lardan Config objesini oluşturur.
    
    Hata varsa anlamlı exception fırlatır.
    """
    # Provider validation
    provider_str = _get_env("LLM_PROVIDER", "huggingface").lower()
    if provider_str not in ("huggingface", "openai", "groq"):
        raise ValueError(
            f"Invalid LLM_PROVIDER: '{provider_str}'. "
            f"Valid values: 'huggingface', 'openai', 'groq'"
        )
    
    provider: LLMProvider = provider_str  # type: ignore[assignment]
    
    return Config(
        # Provider
        llm_provider=provider,
        
        # HuggingFace
        hf_api_key=_get_env("HF_API_KEY"),
        hf_small_model=_get_env("SMALL_MODEL_NAME", "mistralai/Mistral-7B-Instruct-v0.2"),
        hf_large_model=_get_env("LARGE_MODEL_NAME", "mistralai/Mixtral-8x7B-Instruct-v0.1"),
        
        # OpenAI
        openai_api_key=_get_env("OPENAI_API_KEY"),
        openai_small_model=_get_env("OPENAI_SMALL_MODEL_NAME", "gpt-4o-mini"),
        openai_large_model=_get_env("OPENAI_LARGE_MODEL_NAME", "gpt-4o"),
        
        # Groq
        groq_api_key=_get_env("GROQ_API_KEY"),
        groq_small_model=_get_env("GROQ_SMALL_MODEL_NAME", "llama-3.1-8b-instant"),
        groq_large_model=_get_env("GROQ_LARGE_MODEL_NAME", "llama-3.1-70b-versatile"),
        
        # Sampling
        small_model_temperature=_get_env_float("SMALL_MODEL_TEMPERATURE", 0.3),
        large_model_temperature=_get_env_float("LARGE_MODEL_TEMPERATURE", 0.2),
        max_tokens=_get_env_int("MAX_TOKENS", 2048),
        
        # Pipeline
        enable_debug_logs=_get_env_bool("ENABLE_DEBUG_LOGS", False),
        enable_judge_step=_get_env_bool("ENABLE_JUDGE_STEP", True),
        enable_correction_step=_get_env_bool("ENABLE_CORRECTION_STEP", True),
        
        # Advanced
        request_timeout=_get_env_int("REQUEST_TIMEOUT", 60),
        max_retries=_get_env_int("MAX_RETRIES", 2),
    )


# ─────────────────────────────────────────────
# Global Config Instance
# ─────────────────────────────────────────────

try:
    CONFIG = load_config()
except Exception as e:
    print(f"❌ Config loading failed: {e}")
    print("   Please check your .env file and environment variables.")
    raise


# ─────────────────────────────────────────────
# Backward Compatibility (eski kod için)
# ─────────────────────────────────────────────

# Eski config.py kullanımlarını desteklemek için değişkenler export et
LLM_PROVIDER = CONFIG.llm_provider

HF_API_KEY = CONFIG.hf_api_key
SMALL_MODEL_NAME = CONFIG.hf_small_model
LARGE_MODEL_NAME = CONFIG.hf_large_model

OPENAI_API_KEY = CONFIG.openai_api_key
OPENAI_SMALL_MODEL_NAME = CONFIG.openai_small_model
OPENAI_LARGE_MODEL_NAME = CONFIG.openai_large_model

GROQ_API_KEY = CONFIG.groq_api_key
GROQ_SMALL_MODEL_NAME = CONFIG.groq_small_model
GROQ_LARGE_MODEL_NAME = CONFIG.groq_large_model

SMALL_MODEL_TEMPERATURE = CONFIG.small_model_temperature
LARGE_MODEL_TEMPERATURE = CONFIG.large_model_temperature
MAX_TOKENS = CONFIG.max_tokens

ENABLE_DEBUG_LOGS = CONFIG.enable_debug_logs
ENABLE_JUDGE_STEP = CONFIG.enable_judge_step
ENABLE_CORRECTION_STEP = CONFIG.enable_correction_step


def print_config_summary() -> None:
    """Legacy function - yeni Config.print_summary() kullan."""
    CONFIG.print_summary()