from __future__ import annotations
from typing import List, Dict, Any
import time 
import numpy as np
from config.config_loader import get_config
from core.chunking import get_chunker
from core.embeddings import get_embedding_client
from core.vector_store import get_vector_store
from config.schemas import IndexStats


class IndexPipeline:
    """
    Tek sorumluluk: kaynak dokümanları al, chunkla, embed et, vector store'a bas.
    """

    def __init__(self) -> None:
        self.cfg = get_config()
        self.embed_client = get_embedding_client()
        self.vector_store = get_vector_store()

    def run_for_source(self, source_id: str) -> IndexStats:
        sd = next(
            (s for s in self.cfg.rag.source_documents if s.id == source_id),
            None,
        )
        if not sd:
            raise ValueError(f"Unknown source_id: {source_id}")

        chunker = get_chunker(sd.chunker)

        t0 = time.perf_counter()

        print(f"[IndexPipeline] {source_id} için chunklama başlatılıyor...")
        chunks = chunker.chunk(source_id=sd.id, path=sd.path)
        print(f"[IndexPipeline] {source_id} için {len(chunks)} chunk oluşturuldu.")

        if chunks and getattr(chunks[0], "embedding", None) is not None:
            print("[IndexPipeline] Chunk embedding bulundu, API çağrısı yapılmayacak.")
            embs = np.vstack([np.array(c.embedding, dtype="float32") for c in chunks])
        else:
            print("[IndexPipeline] Chunk embedding yok, embed_client embed_texts() çağırılıyor...")
            texts = [c.text for c in chunks]
            embs = self.embed_client.embed_texts(texts)

        t1 = time.perf_counter()
        embed_time_sec = t1 - t0
        num_chunks = len(chunks)

        docs: List[Dict[str, Any]] = []
        for c in chunks:
            docs.append(
                {
                    "id": c.id,
                    "text": c.text,
                    "metadata": c.metadata,
                }
            )

        t2 = time.perf_counter()
        self.vector_store.upsert(embs, docs)
        t3 = time.perf_counter()
        upsert_time_sec = t3 - t2

        print(f"[IndexPipeline] {source_id} için index güncellendi.")
        print(f"[IndexPipeline] İstatistikler -> chunks: {num_chunks}, "
              f"embed_time: {embed_time_sec:.2f}s, upsert_time: {upsert_time_sec:.2f}s")

        return IndexStats(
            num_chunks=num_chunks,
            embed_time_sec=embed_time_sec,
            upsert_time_sec=upsert_time_sec,
        )
