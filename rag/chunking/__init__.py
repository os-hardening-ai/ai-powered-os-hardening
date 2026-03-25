from config.config_loader import get_config
from rag.chunking.base import IChunker
from rag.chunking.pdf_chunker import SimplePdfChunker
from rag.chunking.semantic_pdf_chunker import EmbeddingSemanticPdfChunker
from rag.chunking.cis_section_chunker import CISSectionChunker
from rag.chunking.yaml_rules_chunker import YamlRulesChunker


def get_chunker(chunker_name: str) -> IChunker:
    if chunker_name == "pdf_simple":
        return SimplePdfChunker()
    elif chunker_name == "pdf_semantic":
        return EmbeddingSemanticPdfChunker()
    elif chunker_name == "cis_section":
        return CISSectionChunker()
    elif chunker_name == "yaml_rules":
        return YamlRulesChunker()
    else:
        raise ValueError(f"Unsupported chunker: {chunker_name}")