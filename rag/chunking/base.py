from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional


@dataclass
class Chunk:
    id: str
    text: str
    metadata: Dict[str, Any]
    embedding: Optional[list[float]] = None


class IChunker(ABC):
    @abstractmethod
    def chunk(self, source_id: str, path: str) -> List[Chunk]:
        """Verilen kaynağı (pdf vs.) küçük parçalar + metadata olarak döndür."""
        ...
