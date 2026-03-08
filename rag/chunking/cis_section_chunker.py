from __future__ import annotations

import re
from pathlib import Path
from typing import List, Dict, Any

import fitz  # PyMuPDF

from rag.chunking.base import IChunker, Chunk
from rag.embeddings import get_embedding_client
from rag.embeddings.base import IEmbeddingClient
from rag.metadata.cis_benchmark_parser import (
    parse_benchmark_from_filename,
    extract_cis_chunk_metadata,
    is_toc_or_frontmatter,
)

# Her CIS öneri bölümü bu pattern ile başlar: "5.1.1 Ensure ..."
_SECTION_SPLIT_RE = re.compile(
    r"(?=\b\d+(?:\.\d+){1,3}\s+Ensure\s+)",
    re.IGNORECASE,
)


class CISSectionChunker(IChunker):
    """
    CIS Benchmark PDF'leri için bölüm bazlı chunker.

    Mevcut sayfa-bazlı chunker'ın aksine tüm doküman metnini tek seferde
    işler ve her 'N.N.N Ensure ...' bölümünü ayrı bir chunk yapar.
    Böylece Description + Rationale + Audit + Remediation aynı chunk'ta
    kalır; sayfa sınırlarında kopma olmaz.

    Büyük bölümler max_chars'a göre paragraf sınırlarında ikincil bölmeye
    tabi tutulur.
    """

    def __init__(
        self,
        embedding_client: IEmbeddingClient | None = None,
        max_chars: int = 15000,
        min_chars: int = 500,
    ) -> None:
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.embedding_client = embedding_client or get_embedding_client()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_full_text(self, doc: fitz.Document) -> str:
        parts: List[str] = []
        for page_num in range(len(doc)):
            text = doc[page_num].get_text("text")
            if not text:
                continue
            text = text.strip()
            if is_toc_or_frontmatter(text):
                continue
            parts.append(text)
        return "\n\n".join(parts)

    def _split_by_sections(self, full_text: str) -> List[str]:
        """Tüm metni CIS bölümlerine böl."""
        raw = _SECTION_SPLIT_RE.split(full_text)
        sections: List[str] = []
        for s in raw:
            s = s.strip()
            if len(s) < self.min_chars:
                continue
            if len(s) <= self.max_chars:
                sections.append(s)
            else:
                # Büyük bölüm → paragraf sınırlarında ikincil bölme
                sections.extend(self._split_large_section(s))
        return sections

    def _split_large_section(self, text: str) -> List[str]:
        """max_chars'ı aşan bölümleri paragraf bazında böl."""
        paragraphs = re.split(r"\n\s*\n", text)
        chunks: List[str] = []
        buf: List[str] = []
        buf_len = 0
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            if buf and buf_len + len(p) + 2 > self.max_chars:
                chunks.append("\n\n".join(buf))
                buf = [p]
                buf_len = len(p)
            else:
                buf.append(p)
                buf_len += len(p) + 2
        if buf:
            chunks.append("\n\n".join(buf))
        return [c for c in chunks if len(c) >= self.min_chars]

    # ------------------------------------------------------------------
    # IChunker.chunk
    # ------------------------------------------------------------------

    def chunk(self, source_id: str, path: str) -> List[Chunk]:
        pdf_path = Path(path)
        doc = fitz.open(pdf_path)

        doc_meta = parse_benchmark_from_filename(pdf_path)

        full_text = self._extract_full_text(doc)
        sections = self._split_by_sections(full_text)

        if not sections:
            return []

        # Tek batch olarak embed et
        embeddings = self.embedding_client.embed_texts(sections)

        chunks: List[Chunk] = []
        last_profiles: List[str] | None = None

        for idx, (text, emb) in enumerate(zip(sections, embeddings)):
            cis_meta = extract_cis_chunk_metadata(text)

            profiles = cis_meta.get("profile_applicability")
            if profiles:
                last_profiles = profiles
            elif last_profiles:
                cis_meta["profile_applicability"] = last_profiles

            metadata: Dict[str, Any] = {
                "source_id": source_id,
                "doc_type": "cis_benchmark",
                **doc_meta,
                "num_chars": len(text),
                **cis_meta,
            }

            chunk_id = f"{source_id}-s{idx}"

            chunks.append(
                Chunk(
                    id=chunk_id,
                    text=text,
                    metadata=metadata,
                    embedding=emb if isinstance(emb, list) else emb.tolist(),
                )
            )

        return chunks
