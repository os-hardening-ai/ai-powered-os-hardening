# models/ollama_client.py
"""
Ollama Local LLM Client - 100% FREE & OFFLINE

Ollama yerel olarak LLM'leri çalıştırır:
- Tamamen ücretsiz (API key gerekmez)
- Internet bağlantısı gerektirmez
- Gizlilik (data dışarı gönderilmez)
- Model seçenekleri: Llama 3.1, Mistral, Phi-3, etc.

Kurulum:
1. https://ollama.ai/download adresinden indir
2. ollama pull llama3.1:8b
3. ollama serve (arka planda çalışır)
"""

from __future__ import annotations
import requests
from typing import Optional

class OllamaClient:
    """
    Ollama API client - Local LLM inference.

    Avantajlar:
    - Maliyet: $0 (tamamen ücretsiz)
    - Gizlilik: Data local kalır
    - Hız: GPU varsa çok hızlı
    - Offline: Internet gerekmez
    """

    def __init__(
        self,
        model_name: str,
        base_url: str = "http://localhost:11434",
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(self, prompt: str) -> str:
        """
        Ollama'dan yanıt al.

        Args:
            prompt: LLM'e gönderilecek prompt

        Returns:
            LLM yanıtı (string)

        Raises:
            RuntimeError: Ollama bağlantı hatası
        """
        try:
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,  # Streaming değil, tek yanıt
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,  # max_tokens equivalent
                }
            }

            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()

            result = response.json()
            return result.get("response", "").strip()

        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"❌ Ollama'ya bağlanılamadı ({self.base_url})\n"
                f"   Ollama çalışıyor mu kontrol edin:\n"
                f"   1. Ollama yüklü mü? https://ollama.ai/download\n"
                f"   2. Servis çalışıyor mu? 'ollama serve'\n"
                f"   3. Model indirildi mi? 'ollama pull {self.model_name}'"
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise RuntimeError(
                    f"❌ Model bulunamadı: {self.model_name}\n"
                    f"   Model'i indirin: ollama pull {self.model_name}\n"
                    f"   Mevcut modeller: ollama list"
                )
            raise RuntimeError(f"Ollama API hatası: {e}")
        except Exception as e:
            raise RuntimeError(f"Ollama generate hatası: {e}")


# ─────────────────────────────────────────────
# Factory Functions (models/__init__.py için)
# ─────────────────────────────────────────────

def get_small_ollama_llm(
    model_name: str = "llama3.1:8b",
    base_url: str = "http://localhost:11434",
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> callable:
    """Small Ollama model client döndürür (8B)."""
    client = OllamaClient(
        model_name=model_name,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return client.generate


def get_large_ollama_llm(
    model_name: str = "llama3.1:70b",
    base_url: str = "http://localhost:11434",
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> callable:
    """Large Ollama model client döndürür (70B)."""
    client = OllamaClient(
        model_name=model_name,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return client.generate


# ─────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────

def check_ollama_health(base_url: str = "http://localhost:11434") -> bool:
    """
    Ollama servisinin çalıştığını kontrol eder.

    Returns:
        True if Ollama is running, False otherwise
    """
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False


def list_ollama_models(base_url: str = "http://localhost:11434") -> list[str]:
    """
    Yüklü Ollama modellerini listele.

    Returns:
        Model isimleri listesi (örn: ['llama3.1:8b', 'mistral:7b'])
    """
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        response.raise_for_status()
        data = response.json()
        return [model["name"] for model in data.get("models", [])]
    except:
        return []
