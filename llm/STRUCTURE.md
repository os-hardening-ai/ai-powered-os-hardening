# LLM Module Structure

## Best Practice Dosya Yapısı

```
llm/
├── __init__.py                    # Ana paket
├── core/                          # Temel işlevsellik
│   ├── __init__.py
│   ├── config.py                  # Konfigürasyon (CONFIG, load_config)
│   ├── context.py                 # RequestContext ve data modelleri
│   └── session_store.py           # Session yönetimi
│
├── models/                        # LLM model clients
│   ├── __init__.py
│   ├── adaptive_router.py         # Adaptive model seçici
│   ├── fallback_handler.py        # Fallback mantığı
│   ├── groq_client.py             # Groq API client
│   ├── huggingface_client.py      # HuggingFace API client
│   ├── ollama_client.py           # Ollama (local) client
│   └── openai_client.py           # OpenAI API client
│
├── pipelines/                     # Pipeline implementasyonları
│   ├── __init__.py
│   ├── optimized.py               # Optimized Pipeline (CoT + Adaptive)
│   ├── secure_v2.py               # 4-Layer Secure Pipeline
│   └── layers/                    # Pipeline katmanları
│       ├── __init__.py
│       ├── safety_classifier.py   # Layer 1: Safety Classification
│       ├── hybrid_intent_detector.py  # Layer 2: Intent Detection
│       ├── intent_detector.py
│       ├── pattern_responder.py   # Layer 3A: Pattern Responder
│       ├── info_pipeline.py       # Layer 3B: Info Pipeline
│       ├── action_pipeline.py     # Layer 3C: Action Pipeline
│       ├── zt_enrichment.py       # Zero Trust enrichment
│       └── output_validator.py    # Output validation
│
├── prompts/                       # Prompt şablonları
│   ├── __init__.py
│   ├── cot_prompts.py             # Chain-of-Thought prompts
│   ├── simple_prompts.py          # Simple & medium complexity prompts
│   └── few_shot_examples.py       # Few-shot learning examples
│
├── rag/                           # RAG entegrasyonu
│   ├── __init__.py
│   └── integration.py             # CIS Benchmark retrieval
│
├── ml/                            # Machine Learning
│   ├── __init__.py
│   ├── intent_detector.py         # ML intent classifier (97% accuracy)
│   └── evaluation/                # Model evaluation tools
│       ├── __init__.py
│       ├── dataset.py             # Dataset management
│       └── run_eval.py            # Model evaluation runner
│
├── utils/                         # Yardımcı fonksiyonlar
│   ├── __init__.py
│   ├── analytics_collector.py     # Analytics & metrics
│   ├── input_validator.py         # Input validation
│   ├── langchain_helpers.py       # LangChain utilities
│   ├── local_responder.py         # Pattern-based responses (no LLM)
│   ├── logger.py                  # Logging utilities
│   ├── monitoring.py              # Monitoring & health checks
│   ├── output_validator.py        # Output validation
│   ├── parameter_inference.py     # Parameter inference engine
│   └── question_classifier.py     # Question complexity classifier
│
├── cli/                           # Command-line applications
│   ├── __init__.py
│   └── chat.py                    # Interactive chat interface
│
├── examples/                      # Kullanım örnekleri
│   ├── __init__.py
│   ├── simple_chat.py             # Basit chat örneği
│   ├── script_generation.py       # Script oluşturma
│   ├── info_queries.py            # Bilgi soruları
│   └── different_os_types.py      # Farklı OS tipleri
│
├── tests/                         # Test suite
│   ├── __init__.py
│   ├── integration/               # Integration tests
│   │   ├── __init__.py
│   │   ├── test_api_integration.py
│   │   ├── test_rag_llm_integration.py
│   │   └── test_single_turn_chat.py
│   ├── unit/                      # Unit tests
│   │   ├── __init__.py
│   │   ├── test_groq_models.py
│   │   ├── test_metrics.py
│   │   └── test_security.py
│   ├── pipeline_evaluator.py      # 50-test automated evaluation
│   ├── run_all_tests.py           # Test runner
│   ├── test_dataset.py            # Test dataset
│   ├── test_safety_classifier.py  # Safety tests
│   └── test_security_features.py  # Security tests
│
└── archive/                       # Eski kodlar (deprecated)
    ├── steps/
    └── tests/
```

## Önemli Değişiklikler

### Taşınan Dosyalar

| Eski Konum | Yeni Konum |
|-----------|-----------|
| `core/models/` | `models/` |
| `core/pipeline_optimized.py` | `pipelines/optimized.py` |
| `core/pipeline_v2.py` | `pipelines/secure_v2.py` |
| `core/layers/` | `pipelines/layers/` |
| `core/prompts/` | `prompts/` |
| `core/rag_integration.py` | `rag/integration.py` |
| `core/ml_intent_detector.py` | `ml/intent_detector.py` |
| `core/langchain_helpers.py` | `utils/langchain_helpers.py` |
| `core/run_chat.py` | `cli/chat.py` |
| `testing/examples/` | `examples/` |
| `testing/tests/` | `tests/` |

### Yeni Klasörler

- **`pipelines/`**: Pipeline implementasyonları (önceden core içindeydi)
- **`prompts/`**: Prompt şablonları (önceden core içindeydi)
- **`rag/`**: RAG entegrasyonu (önceden core içindeydi)
- **`cli/`**: CLI uygulamaları (yeni)
- **`examples/`**: Kullanım örnekleri (önceden testing içindeydi)

### core/ Klasöründe Kalanlar

Sadece **temel konfigürasyon ve data modelleri**:
- `config.py`: Global konfigürasyon
- `context.py`: RequestContext ve diğer data modelleri
- `session_store.py`: Session yönetimi

## Import Path Değişiklikleri

### Eski → Yeni

```python
# MODELS
from llm.core.models import get_llm_clients
→ from llm.models import get_llm_clients

# PIPELINES
from llm.core.pipeline_optimized import OptimizedPipeline
→ from llm.pipelines.optimized import OptimizedPipeline

from llm.core.pipeline_v2 import SecurePipelineV2
→ from llm.pipelines.secure_v2 import SecurePipelineV2

# LAYERS
from llm.core.layers.safety_classifier import SafetyClassifier
→ from llm.pipelines.layers.safety_classifier import SafetyClassifier

# PROMPTS
from llm.core.prompts.cot_prompts import CoTSecurityAnalyzer
→ from llm.prompts.cot_prompts import CoTSecurityAnalyzer

# RAG
from llm.core.rag_integration import get_rag_context_builder
→ from llm.rag.integration import get_rag_context_builder

# ML
from llm.core.ml_intent_detector import MLIntentDetector
→ from llm.ml.intent_detector import MLIntentDetector

# UTILS
from llm.core.langchain_helpers import setup_langchain_cache
→ from llm.utils.langchain_helpers import setup_langchain_cache
```

## Avantajlar

### 1. Daha İyi Organizasyon
- Her modül tek bir sorumlulukta
- İlişkili dosyalar gruplandırılmış
- core/ sadece temel işlevsellik içeriyor

### 2. Daha Kolay Bakım
- Dosyaları bulmak kolay
- Modüller arası bağımlılıklar net
- Test dosyaları ayrı ve organize

### 3. Best Practice Uyumu
- Python package structure standartları
- Separation of Concerns prensibi
- Clean Architecture prensipleri

### 4. Daha İyi Testability
- Unit testler ayrı
- Integration testler ayrı
- Test klasörü root'ta

### 5. Daha İyi Scalability
- Yeni modüller eklemek kolay
- Mevcut modülleri extend etmek kolay
- Deprecated kod ayrı (archive/)

## Kullanım Örnekleri

### Temel Kullanım

```python
from llm import CONFIG, RequestContext
from llm.models import get_llm_clients
from llm.pipelines.secure_v2 import run_secure_pipeline_v2

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
print(f"Cost: ${result.estimated_cost:.4f}")
```

### CLI Kullanımı

```bash
# Interactive chat
python -m llm.cli.chat

# Example scripts
python -m llm.examples.simple_chat
python -m llm.examples.script_generation
```

### Test Çalıştırma

```bash
# Tüm testler
python -m llm.tests.run_all_tests

# Sadece integration
python -m pytest llm/tests/integration/

# Sadece unit
python -m pytest llm/tests/unit/

# Pipeline evaluator (50 test case)
python -m llm.tests.pipeline_evaluator
```

## Sonraki Adımlar

1. ✅ Dosya yapısı oluşturuldu
2. ⏳ Import path'lerini güncelle
3. ⏳ Testleri çalıştır ve hataları düzelt
4. ⏳ Git commit yap
5. ⏳ Develop branch oluştur

## Version: 1.0.0 - Structure Refactoring

**Tarih**: 2025-12-24
**Durum**: Dosya yapısı tamamlandı, import path güncellemesi devam ediyor
