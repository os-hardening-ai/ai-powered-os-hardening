from config.config_loader import get_config
from core.embeddings.base import IEmbeddingClient
from core.embeddings.embeddings import SentenceTransformersEmbeddingClient
from core.embeddings.cohere_embeddings import CohereEmbeddingClient
from core.embeddings.novita_embeddings import NovitaEmbeddingClient
# from core.embeddings.openai_embeddings import OpenAIEmbeddingClient # ileride


def get_embedding_client() -> IEmbeddingClient:
    cfg = get_config().embedding
    if cfg.provider == "sentence_transformers":
        return SentenceTransformersEmbeddingClient()
    elif cfg.provider == "cohere":
        return CohereEmbeddingClient()
    elif cfg.provider == "novita":
        return NovitaEmbeddingClient()
    # elif cfg.provider == "openai":
    #     return OpenAIEmbeddingClient()
    else:
        raise ValueError(f"Unsupported embedding provider: {cfg.provider}")
