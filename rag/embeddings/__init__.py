from config.config_loader import get_config
from rag.embeddings.base import IEmbeddingClient


def get_embedding_client() -> IEmbeddingClient:
    cfg = get_config().embedding
    if cfg.provider == "sentence_transformers":
        from rag.embeddings.embeddings import SentenceTransformersEmbeddingClient
        return SentenceTransformersEmbeddingClient()
    elif cfg.provider == "cohere":
        from rag.embeddings.cohere_embeddings import CohereEmbeddingClient
        return CohereEmbeddingClient()
    elif cfg.provider == "novita":
        from rag.embeddings.novita_embeddings import NovitaEmbeddingClient
        return NovitaEmbeddingClient()
    else:
        raise ValueError(f"Unsupported embedding provider: {cfg.provider}")
