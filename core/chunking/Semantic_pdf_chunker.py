from __future__ import annotations

from typing import List, Dict, Any
from pathlib import Path
import re

import numpy as np
import fitz  # PyMuPDF

from core.chunking.base import IChunker, Chunk
from core.embeddings import get_embedding_client
from core.embeddings.base import IEmbeddingClient

from core.metadata.cis_benchmark_parser import (
    parse_benchmark_from_filename,
    extract_cis_chunk_metadata,
)


class EmbeddingSemanticPdfChunker(IChunker):
    """
    Semantic + similarity tabanlı PDF chunker.
    CIS Benchmark metadata’larını otomatik ekler.
    """

    def __init__(
        self,
        embedding_client: IEmbeddingClient | None = None,
        max_chars: int = 1200,
        min_chars: int = 300,
        similarity_threshold: float = 0.6,
    ) -> None:
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.similarity_threshold = similarity_threshold
        self.embedding_client = embedding_client or get_embedding_client()

    def _split_paragraphs(self, text: str) -> List[str]:
        text = text.replace("\r", "\n")
        raw_pars = re.split(r"\n\s*\n", text)

        paragraphs: List[str] = []
        for p in raw_pars:
            p = p.strip()
            if not p:
                continue
            if len(p) < 10:
                continue
            paragraphs.append(p)
        return paragraphs

    def _cosine_sim(self, a: np.ndarray, b: np.ndarray) -> float:
        denom = (np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def chunk(self, source_id: str, path: str) -> List[Chunk]:
        pdf_path = Path(path)
        doc = fitz.open(pdf_path)

        # filename'den: os_family, os_version, benchmark_version, benchmark_product
        doc_meta = parse_benchmark_from_filename(pdf_path)

        chunks: List[Chunk] = []

        # Son görülen profile_applicability'yi tutuyoruz (inherit için)
        last_profiles: List[str] | None = None

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if not text:
                continue
            text = text.strip()

            paragraphs = self._split_paragraphs(text)
            if not paragraphs:
                continue

            # paragraf embeddingleri
            par_embs = self.embedding_client.embed_texts(paragraphs)

            current_buf: List[str] = []
            current_len = 0
            start_par_idx = 0
            last_emb: np.ndarray | None = None
            chunk_idx = 0

            for i, (p, p_emb) in enumerate(zip(paragraphs, par_embs)):
                p_len = len(p)

                if not current_buf:
                    current_buf.append(p)
                    current_len = p_len
                    start_par_idx = i
                    last_emb = p_emb
                    continue

                sim = self._cosine_sim(last_emb, p_emb)

                if sim >= self.similarity_threshold and (current_len + p_len + 2) <= self.max_chars:
                    current_buf.append(p)
                    current_len += p_len + 2
                    last_emb = p_emb
                else:
                    # ------ CHUNK FLUSH ------
                    chunk_text = "\n\n".join(current_buf)
                    # bu chunk'ın kapsadığı paragraflar: [start_par_idx, i)
                    chunk_par_embs = par_embs[start_par_idx:i]
                    chunk_emb = np.mean(chunk_par_embs, axis=0)

                    cis_meta = extract_cis_chunk_metadata(chunk_text)

                    # Profile inherit mantığı
                    profiles = cis_meta.get("profile_applicability")
                    if profiles:
                        last_profiles = profiles
                    elif last_profiles:
                        cis_meta["profile_applicability"] = last_profiles

                    metadata: Dict[str, Any] = {
                        "source_id": source_id,
                        "page": page_num + 1,
                        "doc_type": "cis_benchmark",
                        **doc_meta,
                        "num_paragraphs": len(current_buf),
                        "num_chars": len(chunk_text),
                        **cis_meta,
                    }

                    chunk_id = f"{source_id}-p{page_num+1}-c{chunk_idx}"

                    chunks.append(
                        Chunk(
                            id=chunk_id,
                            text=chunk_text,
                            metadata=metadata,
                            embedding=chunk_emb.tolist(),
                        )
                    )

                    chunk_idx += 1

                    # yeni chunk
                    current_buf = [p]
                    current_len = p_len
                    start_par_idx = i
                    last_emb = p_emb

            # ------ SAYFA SONU → son chunk ------
            if current_buf:
                chunk_text = "\n\n".join(current_buf)

                # küçük chunk ise önceki ile merge et
                if len(chunk_text) < self.min_chars and chunks:
                    last = chunks.pop()
                    merged_text = last.text + "\n\n" + chunk_text

                    # merge edilmiş metin için profile + embed'i yeniden hesapla
                    cis_meta = extract_cis_chunk_metadata(merged_text)
                    profiles = cis_meta.get("profile_applicability")
                    if profiles:
                        last_profiles = profiles
                    elif last_profiles:
                        cis_meta["profile_applicability"] = last_profiles

                    merged_meta = dict(last.metadata)
                    merged_meta["num_paragraphs"] = merged_meta.get("num_paragraphs", 0) + len(current_buf)
                    merged_meta["num_chars"] = len(merged_text)
                    merged_meta.update(cis_meta)

                    # merged embedding'i direkt text üstünden alıyoruz (nadir case, sık değil)
                    merged_emb = self.embedding_client.embed_texts([merged_text])[0]

                    chunks.append(
                        Chunk(
                            id=last.id,
                            text=merged_text,
                            metadata=merged_meta,
                            embedding=merged_emb,
                        )
                    )
                else:
                    # NORMAL SON CHUNK
                    chunk_par_embs = par_embs[start_par_idx:len(paragraphs)]
                    chunk_emb = np.mean(chunk_par_embs, axis=0)

                    cis_meta = extract_cis_chunk_metadata(chunk_text)
                    profiles = cis_meta.get("profile_applicability")
                    if profiles:
                        last_profiles = profiles
                    elif last_profiles:
                        cis_meta["profile_applicability"] = last_profiles

                    metadata: Dict[str, Any] = {
                        "source_id": source_id,
                        "page": page_num + 1,
                        "doc_type": "cis_benchmark",
                        **doc_meta,
                        "num_paragraphs": len(current_buf),
                        "num_chars": len(chunk_text),
                        **cis_meta,
                    }

                    chunk_id = f"{source_id}-p{page_num+1}-c{chunk_idx}"

                    chunks.append(
                        Chunk(
                            id=chunk_id,
                            text=chunk_text,
                            metadata=metadata,
                            embedding=chunk_emb.tolist(),
                        )
                    )

        return chunks
