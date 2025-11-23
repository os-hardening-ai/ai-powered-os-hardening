from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List
import numpy as np


class IVectorStore(ABC):
    @abstractmethod
    def upsert(self, embeddings: np.ndarray, docs: List[Dict[str, Any]]) -> None:
        """Embeddings + metadata dokümanlarını indekse ekle/güncelle."""
        ...

    @abstractmethod
    def search(self, query_emb: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        """En benzer top_k dokümanı döndür."""
        ...
