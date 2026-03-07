from __future__ import annotations
from abc import ABC, abstractmethod
import numpy as np


class IEmbeddingClient(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> np.ndarray:
        ...

    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray:
        ...
