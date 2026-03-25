from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from config.schemas import (
    AppConfig, AppConfigRoot, ApiConfig, EmbeddingConfig, LlmConfig,
    RagConfig, RulesConfig, SourceDocumentConfig, VectorStoreConfig,
    PipelineConfig, MonitoringConfig, DataPathsConfig, LateChunkingConfig
)


ConfigPath = Path("config/config.json")


class ConfigLoader:
    def __init__(self, path: Path = ConfigPath) -> None:
        self._path = path
        self._config: Optional[AppConfigRoot] = None

    def load(self) -> AppConfigRoot:
        if self._config is not None:
            return self._config

        with self._path.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        # App
        app = AppConfig(**raw["app"])

        # API - flatten nested structure
        api_raw = raw.get("api", {})
        api = ApiConfig(
            host=api_raw.get("host", "0.0.0.0"),
            port=api_raw.get("port", 8000),
            cors_origins=api_raw.get("cors", {}).get("allow_origins", ["*"]),
            rate_limit_requests=api_raw.get("rate_limit", {}).get("requests_per_minute", 100),
            rate_limit_period_seconds=60,
        )

        # RAG with source documents and rules
        rag_raw = raw.get("rag", {})
        sd_list = [
            SourceDocumentConfig(**sd) for sd in rag_raw.get("source_documents", [])
        ]
        rules_dict = {
            key: RulesConfig(**val) for key, val in rag_raw.get("rules", {}).items()
        }
        late_chunking_raw = rag_raw.get("late_chunking") or {}
        rag = RagConfig(
            enabled=rag_raw.get("enabled", True),
            chunk_method=rag_raw.get("chunk_method", "semantic"),
            late_chunking=late_chunking_raw,
            retrieval=rag_raw.get("retrieval", {}),
            source_documents=sd_list,
            rules=rules_dict,
        )

        # Embedding
        embedding = EmbeddingConfig(**raw["embedding"])

        # Vector Store
        vector_store = VectorStoreConfig(**raw["vector_store"])

        # LLM
        llm_raw = raw["llm"]
        llm = LlmConfig(
            default_provider=llm_raw.get("default_provider", "groq"),
            timeout=llm_raw.get("timeout", 60),
            max_retries=llm_raw.get("max_retries", 3),
            providers=llm_raw.get("providers", {}),
        )

        # Pipeline - includes feature flags
        p_raw = raw.get("pipeline", {})
        pipeline = PipelineConfig(
            enable_debug_logs=p_raw.get("enable_debug_logs", False),
            enable_judge_step=p_raw.get("enable_judge_step", True),
            enable_correction_step=p_raw.get("enable_correction_step", True),
            safety_classification=p_raw.get("safety_classification", {}),
            intent_detection=p_raw.get("intent_detection", {}),
            generation=p_raw.get("generation", {}),
        )

        # Monitoring
        mon_raw = raw.get("monitoring", {})
        monitoring = MonitoringConfig(
            enabled=mon_raw.get("enabled", True),
            retention_hours=mon_raw.get("metrics_retention_hours", 24),
            log_requests=mon_raw.get("log_requests", True),
            log_errors=mon_raw.get("log_errors", True),
        )

        # Data Paths
        dp_raw = raw.get("data_paths", {})
        data_paths = DataPathsConfig(
            documents=dp_raw.get("source_documents", "data/source"),
            embeddings=dp_raw.get("cache", "data/cache"),
            logs=dp_raw.get("logs", "logs"),
            cache=dp_raw.get("cache", ".cache"),
        )

        self._config = AppConfigRoot(
            app=app,
            api=api,
            rag=rag,
            embedding=embedding,
            vector_store=vector_store,
            llm=llm,
            pipeline=pipeline,
            monitoring=monitoring,
            data_paths=data_paths,
        )
        return self._config

    @property
    def config(self) -> AppConfigRoot:
        if self._config is None:
            return self.load()
        return self._config


_config_loader: Optional[ConfigLoader] = None


def get_config(config_path: Optional[Path] = None) -> AppConfigRoot:
    """Get or create config loader singleton."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader(config_path or ConfigPath)
    return _config_loader.config
