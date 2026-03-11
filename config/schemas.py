from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Any
from pydantic import BaseModel, Field


@dataclass
class AppConfig:
    name: str
    version: str
    env: Literal["dev", "prod"]
    debug: bool = False
    log_level: str = "info"
    language: Literal["tr", "en"] = "tr"


@dataclass
class ApiConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    rate_limit_requests: int = 100
    rate_limit_period_seconds: int = 60


@dataclass
class PipelineConfig:
    enable_debug_logs: bool = False
    enable_judge_step: bool = True
    enable_correction_step: bool = True
    safety_classification: Dict[str, Any] = field(default_factory=dict)
    intent_detection: Dict[str, Any] = field(default_factory=dict)
    generation: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitoringConfig:
    enabled: bool = True
    retention_hours: int = 24
    log_requests: bool = True
    log_errors: bool = True


@dataclass
class DataPathsConfig:
    documents: str = "data/source"
    embeddings: str = "data/embeddings"
    logs: str = "logs"
    cache: str = ".cache"


@dataclass
class SourceDocumentConfig:
    id: str
    type: Literal["pdf", "markdown", "html", "yaml"]
    path: str
    chunker: str
    metadata_strategy: str = "auto"
    name: str = ""
    enabled: bool = True
    priority: int = 0


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
    enabled: bool = True
    chunk_method: str = "semantic"
    source_documents: List[SourceDocumentConfig] = field(default_factory=list)
    rules: Dict[str, RulesConfig] = field(default_factory=dict)
    late_chunking: Dict[str, Any] | LateChunkingConfig | None = None
    retrieval: Dict[str, Any] = field(default_factory=lambda: {
        "top_k": 5,
        "min_score": 0.3,
        "max_results": 10
    })


@dataclass
class EmbeddingConfig:
    provider: Literal["sentence_transformers", "openai", "cohere", "novita"]
    model_name: str
    dim: int
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    batch_size: int = 100
    cache_enabled: bool = False


@dataclass
class VectorStoreConfig:
    provider: Literal["faiss", "qdrant"]
    qdrant: Dict[str, Any]
    index_path: Optional[str] = None   # FAISS only
    metadata_path: Optional[str] = None  # FAISS only


@dataclass
class LlmConfig:
    default_provider: str = "groq"
    timeout: int = 60
    max_retries: int = 3
    providers: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AppConfigRoot:
    app: AppConfig
    api: ApiConfig
    rag: RagConfig
    embedding: EmbeddingConfig
    vector_store: VectorStoreConfig
    llm: LlmConfig
    pipeline: PipelineConfig
    monitoring: MonitoringConfig
    data_paths: DataPathsConfig


@dataclass
class IndexStats:
    num_chunks: int
    embed_time_sec: float
    upsert_time_sec: float
