from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from config.config_loader import get_config
from core.embeddings.base import IEmbeddingClient


class SentenceTransformersEmbeddingClient(IEmbeddingClient):
    def __init__(self) -> None:
        cfg = get_config()
        self._model = SentenceTransformer(cfg.embedding.model_name)

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(
            texts,
            batch_size=16,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_texts([text])[0]
