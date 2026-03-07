from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Any
from pydantic import BaseModel, Field


@dataclass
class AppConfig:
    name: str
    env: Literal["dev", "prod"]
    language: Literal["tr", "en"]


@dataclass
class SourceDocumentConfig:
    id: str
    type: Literal["pdf", "markdown", "html"]
    path: str
    chunker: str
    metadata_strategy: str


@dataclass
class RulesConfig:
    path: str
    enabled: bool = True

class LateChunkingConfig(BaseModel):
    enabled: bool = True
    window_size: int = Field(3, ge=1, le=10)
    coarse_k_factor: int = Field(3, ge=1, le=10)
    fine_k: int = Field(10, ge=1, le=50)    

@dataclass
class RagConfig:
    source_documents: List[SourceDocumentConfig]
    rules: Dict[str, RulesConfig]
    late_chunking: Dict[str, Any] | LateChunkingConfig | None = None


@dataclass
class EmbeddingConfig:
    provider: Literal["sentence_transformers", "openai", "cohere","novita"]
    model_name: str
    dim: int
    api_key: Optional[str] = None
    base_url: str | None = None

@dataclass
class VectorStoreConfig:
    provider: Literal["faiss", "qdrant"]
    qdrant: Dict[str, Any]
    index_path: Optional[str] = None   # FAISS only
    metadata_path: Optional[str] = None  # FAISS only


@dataclass
class LlmConfig:
    provider: Literal["groq", "openai", "ollama", "huggingface"]
    model_name: str
    api_key: Optional[str]


@dataclass
class AppConfigRoot:
    app: AppConfig
    rag: RagConfig
    embedding: EmbeddingConfig
    vector_store: VectorStoreConfig
    llm: LlmConfig

@dataclass
class IndexStats:
    num_chunks: int
    embed_time_sec: float
    upsert_time_sec: float