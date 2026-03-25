"""
OpenAI-Compatible Chat Completions Endpoint

POST /v1/chat/completions — standart OpenAI formatını kabul eder,
mevcut 4-katmanlı pipeline'a yönlendirir, OpenAI formatında cevap döner.

Web siteleri ve araçlar doğrudan OpenAI SDK ile bağlanabilir:
  client = OpenAI(base_url="http://localhost:8000/v1", api_key="any")
  client.chat.completions.create(model="any", messages=[...])
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from llm.core.context import RequestContext
from llm.pipelines.secure_v2 import SecurePipelineV2
from llm.clients import get_llm_clients
from llm.rag.integration import RAGContextBuilder
from api.security import validate_chat_input, sanitize_output
from api.errors import APIError, ErrorCode
from log_manager import get_logger

_logger = get_logger("openai_compat")

router = APIRouter()

# ── Request / Response schemas (OpenAI format) ──────────────────────────────

class OAIMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class OAIChatRequest(BaseModel):
    model: str = Field("hardening-ai", description="Model adı (görmezden gelinir, pipeline kullanır)")
    messages: List[OAIMessage] = Field(..., min_length=1)
    stream: bool = False
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=65536)
    # Ek parametreler (opsiyonel, pipeline'a aktarılır)
    os: Optional[str] = Field(None, description="OS hedefi: ubuntu_24_04, windows_11 vb.")
    role: Optional[str] = Field(None, description="Kullanıcı rolü: sysadmin, soc vb.")
    use_rag: bool = Field(True)
    rag_top_k: int = Field(3, ge=1, le=20)
    rag_min_score: float = Field(0.5, ge=0.0, le=1.0)
    timeout: Optional[int] = Field(60, ge=1, le=300)


class OAIChoice(BaseModel):
    index: int
    message: OAIMessage
    finish_reason: str = "stop"


class OAIUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class OAIChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[OAIChoice]
    usage: OAIUsage
    # Ek alanlar (pipeline metadata)
    x_intent: Optional[str] = Field(None, alias="x-intent")
    x_safety: Optional[str] = Field(None, alias="x-safety")
    x_layer_path: Optional[str] = Field(None, alias="x-layer-path")

    model_config = {"populate_by_name": True}


# ── Helpers ──────────────────────────────────────────────────────────────────

_llm_small = None
_llm_large = None


def _get_clients():
    global _llm_small, _llm_large
    if _llm_small is None or _llm_large is None:
        _llm_small, _llm_large = get_llm_clients()
    return _llm_small, _llm_large


def _extract_question(messages: List[OAIMessage]) -> str:
    """Son user mesajını döner."""
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content.strip()
    return messages[-1].content.strip()


def _extract_os_from_system(messages: List[OAIMessage]) -> Optional[str]:
    """System mesajından OS bilgisi çıkarmaya çalışır."""
    os_keywords = {
        "ubuntu": "ubuntu_24_04",
        "windows 11": "windows_11",
        "windows server": "windows_server_2025",
        "debian": "debian",
        "centos": "centos",
        "rhel": "rhel",
    }
    for msg in messages:
        if msg.role == "system":
            lower = msg.content.lower()
            for keyword, os_id in os_keywords.items():
                if keyword in lower:
                    return os_id
    return None


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post(
    "/chat/completions",
    response_model=OAIChatResponse,
    summary="OpenAI-Compatible Chat Completions",
    description="""
**OpenAI SDK veya herhangi bir OpenAI-compatible araç ile doğrudan kullanılabilir.**

### Bağlantı

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"   # herhangi bir değer
)

response = client.chat.completions.create(
    model="hardening-ai",
    messages=[
        {"role": "system", "content": "Sen bir OS güvenlik uzmanısın."},
        {"role": "user", "content": "Ubuntu 24.04 SSH nasıl sıkılaştırılır?"}
    ]
)
print(response.choices[0].message.content)
```

### OS Algılama
- `os` alanı ile açıkça belirtilebilir: `"ubuntu_24_04"`, `"windows_11"`, `"windows_server_2025"`
- Veya system mesajı içinde otomatik algılanır (Ubuntu, Windows 11 vb. geçiyorsa)

### Ek Parametreler (opsiyonel)
| Alan | Tip | Varsayılan | Açıklama |
|------|-----|------------|----------|
| `os` | string | null | Hedef OS |
| `role` | string | null | Kullanıcı rolü: sysadmin, soc, developer |
| `use_rag` | bool | true | RAG retrieval kullanılsın mı |
| `rag_top_k` | int | 5 | Kaç chunk getirilsin |
| `rag_min_score` | float | 0.5 | Minimum benzerlik skoru |
| `timeout` | int | 60 | Saniye cinsinden timeout |
""",
    response_description="OpenAI-compatible chat completion response",
)
async def openai_chat_completions(payload: OAIChatRequest) -> OAIChatResponse:
    """OpenAI-compatible chat completions — 4-layer security pipeline ile."""
    question = _extract_question(payload.messages)

    # Güvenlik doğrulaması
    is_valid, error_msg = validate_chat_input(question, max_length=5000, check_injection=False)
    if not is_valid:
        raise APIError(
            status_code=400,
            error_code=ErrorCode.INVALID_INPUT,
            message=error_msg,
            details={"field": "messages[-1].content"},
        )

    # OS bilgisini önce payload'dan, yoksa system mesajından al
    os_target = payload.os or _extract_os_from_system(payload.messages)

    timeout_seconds = payload.timeout or 60

    try:
        llm_small, llm_large = _get_clients()

        ctx = RequestContext(
            user_question=question,
            os=os_target,
            role=payload.role,
        )

        rag_builder = None
        if payload.use_rag:
            try:
                rag_builder = RAGContextBuilder(
                    top_k=payload.rag_top_k,
                    min_score=payload.rag_min_score,
                )
            except Exception as e:
                _logger.warning(f"[OpenAI Compat] RAG init failed: {e}")

        pipeline = SecurePipelineV2(
            llm_ultra_fast=llm_small,
            llm_small=llm_small,
            llm_large=llm_large,
            rag_builder=rag_builder,
            debug=False,
        )

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(pipeline.run, ctx),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise APIError(
                status_code=504,
                error_code=ErrorCode.TIMEOUT,
                message=f"Request timed out after {timeout_seconds}s",
                details={"timeout": timeout_seconds},
            )

        answer = sanitize_output(result.answer or "Cevap üretilemedi.")

        prompt_tokens = sum(_estimate_tokens(m.content) for m in payload.messages)
        completion_tokens = _estimate_tokens(answer)

        return OAIChatResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
            object="chat.completion",
            created=int(time.time()),
            model=payload.model,
            choices=[
                OAIChoice(
                    index=0,
                    message=OAIMessage(role="assistant", content=answer),
                    finish_reason="stop",
                )
            ],
            usage=OAIUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            **{
                "x-intent": result.intent.type if result.intent else None,
                "x-safety": result.safety.category if result.safety else None,
                "x-layer-path": result.layer_path,
            },
        )

    except APIError:
        raise
    except Exception as e:
        raise APIError(
            status_code=500,
            error_code=ErrorCode.PIPELINE_ERROR,
            message=f"Pipeline failed: {str(e)}",
            details={"stage": "openai_compat"},
        )


@router.get(
    "/models",
    summary="List Available Models",
    description="OpenAI-compatible model listesi. `GET /v1/models` — mevcut modelleri döner.",
)
async def list_models() -> Dict[str, Any]:
    """OpenAI-compatible model listesi."""
    return {
        "object": "list",
        "data": [
            {
                "id": "hardening-ai",
                "object": "model",
                "created": 1700000000,
                "owned_by": "marmara-university",
                "description": "AI-Powered OS Hardening — CIS Benchmark RAG + 4-layer pipeline",
            }
        ],
    }
