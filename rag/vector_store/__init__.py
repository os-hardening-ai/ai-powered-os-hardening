from config.config_loader import get_config
from core.vector_store.base import IVectorStore
from core.vector_store.vector_store import FaissVectorStore
from core.vector_store.qdrant_store import QdrantVectorStore


def get_vector_store() -> IVectorStore:
    cfg = get_config().vector_store
    if cfg.provider == "faiss":
        return FaissVectorStore(
            index_path=cfg.index_path,
            metadata_path=cfg.metadata_path,
        )
    elif cfg.provider == "qdrant":
        return QdrantVectorStore()
    else:
        raise ValueError(f"Unsupported vector store provider: {cfg.provider}")
