from typing import Optional

from config.config_loader import get_config
from rag.vector_store.base import IVectorStore
from rag.vector_store.vector_store import FaissVectorStore
from rag.vector_store.qdrant_store import QdrantVectorStore

_store: Optional[IVectorStore] = None


def get_vector_store() -> IVectorStore:
    global _store
    if _store is not None:
        return _store

    cfg = get_config().vector_store
    if cfg.provider == "faiss":
        _store = FaissVectorStore(
            index_path=cfg.index_path,
            metadata_path=cfg.metadata_path,
        )
    elif cfg.provider == "qdrant":
        _store = QdrantVectorStore()
    else:
        raise ValueError(f"Unsupported vector store provider: {cfg.provider}")

    return _store
