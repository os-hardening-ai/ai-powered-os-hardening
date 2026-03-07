from __future__ import annotations
from typing import List, Dict, Any
from pathlib import Path
from rag.chunking.base import IChunker, Chunk
import fitz  # PyMuPDF

class SimplePdfChunker(IChunker):
    """
    Şimdilik: her sayfayı al, belirli bir karakter uzunluğuna göre parçalara böl.
    Metadata: source_id, page_num, chunk_index.
    İleride: section başlıklarını regex ile yakalayıp 'section_id' vs. ekleyebiliriz.
    """

    def __init__(self, max_chars: int = 1200, overlap: int = 200) -> None:
        self.max_chars = max_chars
        self.overlap = overlap

    def chunk(self, source_id: str, path: str) -> List[Chunk]:
        pdf_path = Path(path)
        doc = fitz.open(pdf_path)

        chunks: List[Chunk] = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            text = text.strip()

            if not text:
                continue

            start = 0
            chunk_idx = 0
            while start < len(text):
                end = min(start + self.max_chars, len(text))
                part = text[start:end]

                chunk_id = f"{source_id}-p{page_num+1}-c{chunk_idx}"
                metadata: Dict[str, Any] = {
                    "source_id": source_id,
                    "page": page_num + 1,
                    "chunk_index": chunk_idx,
                    "doc_type": "cis_benchmark",
                }

                chunks.append(
                    Chunk(
                        id=chunk_id,
                        text=part,
                        metadata=metadata,
                    )
                )

                if end >= len(text):
                    break

                start = end - self.overlap
                chunk_idx += 1

        return chunks
