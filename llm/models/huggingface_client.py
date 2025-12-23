# models/huggingface_client.py
from __future__ import annotations
from huggingface_hub import InferenceClient
from ..config import (
    HF_API_KEY,
    SMALL_MODEL_NAME,
    LARGE_MODEL_NAME,
    SMALL_MODEL_TEMPERATURE,
    LARGE_MODEL_TEMPERATURE,
    MAX_TOKENS,
)

class HuggingFaceClient:
    """
    Hugging Face Serverless Inference API client.
    Provider'ı manuel olarak 'hf-inference' olarak belirtiyoruz.
    """
    
    def __init__(
        self,
        model_name: str,
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> None:
        if not HF_API_KEY:
            raise RuntimeError("HF_API_KEY tanımlı değil. .env dosyanı kontrol et.")
        
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # ✅ Provider'ı manuel belirt: "hf-inference" (ücretsiz serverless API)
        self.client = InferenceClient(
            token=HF_API_KEY,
            provider="hf-inference"  # 🔥 ÖNEMLİ: Provider belirtilmeli
        )
        
        print(f"✅ Model yüklendi: {model_name}")
    
    def __call__(self, prompt: str) -> str:
        """Modele prompt gönder ve cevap al"""
        try:
            # Chat completion dene
            messages = [{"role": "user", "content": prompt}]
            
            response = self.client.chat_completion(
                messages=messages,
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            return response.choices[0].message.content.strip()
            
        except (AttributeError, KeyError, TypeError):
            # Chat desteklenmiyorsa text generation dene
            try:
                response = self.client.text_generation(
                    prompt=prompt,
                    model=self.model_name,
                    temperature=self.temperature,
                    max_new_tokens=self.max_tokens,
                    return_full_text=False,
                )
                return response.strip()
                
            except Exception as e:
                error_msg = str(e)
                
                # Model desteklenmiyorsa
                if "not supported" in error_msg or "model_not_supported" in error_msg:
                    raise RuntimeError(
                        f"❌ Model '{self.model_name}' ücretsiz API'de desteklenmiyor.\n"
                        f"💡 Çözüm 1: Başka model dene (örn: google/flan-t5-base)\n"
                        f"💡 Çözüm 2: PRO'ya geç ($9/ay): https://huggingface.co/pricing\n"
                        f"💡 Çözüm 3: Ollama kullan (tamamen ücretsiz)"
                    ) from e
                
                # Rate limit veya kredi dolmuşsa
                if "exceeded" in error_msg or "402" in error_msg or "rate limit" in error_msg.lower():
                    raise RuntimeError(
                        f"❌ Rate limit veya aylık kredin doldu.\n"
                        f"💡 Çözüm: PRO'ya geç ($9/ay) - 20x daha fazla kredi\n"
                        f"https://huggingface.co/pricing"
                    ) from e
                
                raise RuntimeError(f"HuggingFace API hatası: {error_msg}") from e
                
        except Exception as e:
            error_msg = str(e)
            
            if "not supported" in error_msg or "model_not_supported" in error_msg:
                raise RuntimeError(
                    f"❌ Model '{self.model_name}' desteklenmiyor.\n"
                    f"💡 Başka model dene veya PRO'ya geç."
                ) from e
            
            raise RuntimeError(f"HuggingFace API hatası: {error_msg}") from e


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