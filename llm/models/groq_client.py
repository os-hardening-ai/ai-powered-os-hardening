# models/groq_client.py
from __future__ import annotations
from groq import Groq
from config import (
    GROQ_API_KEY,
    GROQ_SMALL_MODEL_NAME,
    GROQ_LARGE_MODEL_NAME,
    SMALL_MODEL_TEMPERATURE,
    LARGE_MODEL_TEMPERATURE,
    MAX_TOKENS,
)


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
    ) -> None:
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY tanımlı değil. .env dosyanı kontrol et.\n"
                "Ücretsiz API key al: https://console.groq.com/keys"
            )
        
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = Groq(api_key=api_key)

        print(f"[OK] Groq API - Model: {model_name}")
    
    def __call__(self, prompt: str) -> str:
        """Modele prompt gönder ve cevap al"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            content = response.choices[0].message.content

            if content is None:
                raise RuntimeError("Groq API boş content döndürdü")

            return content.strip()
            
        except Exception as e:
            error_msg = str(e)
            
            # Rate limit hatası
            if "rate_limit" in error_msg.lower() or "429" in error_msg:
                raise RuntimeError(
                    "⚠️  Groq rate limit aşıldı.\n"
                    "Çözüm: 1 dakika bekle veya ücretsiz tier limitlerini kontrol et:\n"
                    "https://console.groq.com/settings/limits"
                ) from e
            
            # API key hatası
            if "401" in error_msg or "unauthorized" in error_msg.lower():
                raise RuntimeError(
                    "❌ Groq API key geçersiz.\n"
                    "Yeni key al: https://console.groq.com/keys"
                ) from e
            
            raise RuntimeError(f"Groq API hatası: {error_msg}") from e


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