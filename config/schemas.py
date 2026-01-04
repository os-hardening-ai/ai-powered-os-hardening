from dataclasses import dataclass
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

@dataclass
class LateChunkingConfig(BaseModel):
    enabled: bool = True
    window_size: int = Field(3, ge=1, le=10)
    coarse_k_factor: int = Field(3, ge=1, le=10)
    fine_k: int = Field(10, ge=1, le=50)    

@dataclass
class RagConfig:
    source_documents: List[SourceDocumentConfig]
    rules: Dict[str, RulesConfig]
    late_chunking: LateChunkingConfig = Field(default_factory=LateChunkingConfig)


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
    index_path: str
    metadata_path: str
    qdrant: Dict[str, Any]


@dataclass
class LlmConfig:
    provider: Literal["dummy", "openai", "mistral", "novita"]
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