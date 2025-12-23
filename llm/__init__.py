"""
AI-Powered OS Hardening - LLM Module
====================================

Bu modül, işletim sistemi güvenlik sıkılaştırma (hardening) için
RAG + LLM tabanlı asistan işlevlerini sağlar.

## Modül Yapısı:

- **core**: Temel konfigürasyon, context ve session yönetimi
- **models**: LLM model clients (Groq, OpenAI, Ollama, HuggingFace)
- **pipelines**: Security pipeline implementasyonları
- **prompts**: Prompt şablonları (CoT, few-shot, simple)
- **rag**: RAG (Retrieval Augmented Generation) entegrasyonu
- **ml**: ML modelleri ve değerlendirme
- **utils**: Yardımcı fonksiyonlar ve validators
- **cli**: Komut satırı uygulamaları
- **examples**: Kullanım örnekleri
- **tests**: Test suite (unit + integration)
- **archive**: Eski versiyon kodları

## Hızlı Kullanım:

```python
from llm.core.config import CONFIG
from llm.models import get_llm_clients
from llm.pipelines.secure_v2 import SecurePipelineV2, run_secure_pipeline_v2
from llm.core.context import RequestContext

# LLM clients
llm_ultra_fast, llm_small, llm_large = get_llm_clients()

# Pipeline çalıştır
result = run_secure_pipeline_v2(
    question="Ubuntu 22.04 SSH hardening nasıl yapılır?",
    llm_ultra_fast=llm_ultra_fast,
    llm_small=llm_small,
    llm_large=llm_large,
    debug=True
)

print(result.answer)
```

## Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "AI-Powered OS Hardening Team"

# Core exports
from .core.config import CONFIG, load_config
from .core.context import RequestContext, SafetyResult

__all__ = [
    "CONFIG",
    "load_config",
    "RequestContext",
    "SafetyResult",
    "__version__",
]
