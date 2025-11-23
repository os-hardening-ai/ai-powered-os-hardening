from __future__ import annotations
import json
from pathlib import Path
from typing import  Optional
from config.schemas import AppConfig, AppConfigRoot, EmbeddingConfig, LlmConfig, RagConfig, RulesConfig, SourceDocumentConfig, VectorStoreConfig


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

        app = AppConfig(**raw["app"])

        sd_list = [
            SourceDocumentConfig(**sd) for sd in raw["rag"]["source_documents"]
        ]
        rules_dict = {
            key: RulesConfig(**val) for key, val in raw["rag"]["rules"].items()
        }
        rag = RagConfig(source_documents=sd_list, rules=rules_dict)

        embedding = EmbeddingConfig(**raw["embedding"])
        vector_store = VectorStoreConfig(**raw["vector_store"])
        llm = LlmConfig(**raw["llm"])

        self._config = AppConfigRoot(
            app=app,
            rag=rag,
            embedding=embedding,
            vector_store=vector_store,
            llm=llm,
        )
        return self._config

    @property
    def config(self) -> AppConfigRoot:
        if self._config is None:
            return self.load()
        return self._config

_config_loader = ConfigLoader()


def get_config() -> AppConfigRoot:
    return _config_loader.config
