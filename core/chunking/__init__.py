from config.config_loader import get_config
from core.chunking.base import IChunker
from core.chunking.pdf_chunker import SimplePdfChunker
from core.chunking.Semantic_pdf_chunker import EmbeddingSemanticPdfChunker

def get_chunker(chunker_name: str) -> IChunker:
    if chunker_name == "pdf_simple":
        return SimplePdfChunker()
    elif chunker_name == "pdf_semantic":
        return EmbeddingSemanticPdfChunker()
    else:
        raise ValueError(f"Unsupported chunker: {chunker_name}")

# SectionAwarePdfChunker yazıp heading’leri yakalarsın (1.1.1 gibi).

# metadata_strategy alanına göre farklı extractor’lar bağlarız (Strategy pattern).