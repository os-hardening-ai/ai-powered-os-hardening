from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import faiss
import json
import numpy as np

from rag.vector_store.base import IVectorStore


class FaissVectorStore(IVectorStore):
    def __init__(self, index_path: str, metadata_path: str) -> None:
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)

        self.index = None
        self.docs: List[Dict[str, Any]] = []

        if self.index_path.exists() and self.metadata_path.exists():
            self._load()

    def _load(self) -> None:
        self.index = faiss.read_index(str(self.index_path))
        with self.metadata_path.open("r", encoding="utf-8") as f:
            self.docs = json.load(f)

    def upsert(self, embeddings: np.ndarray, docs: List[Dict[str, Any]]) -> None:
        d = embeddings.shape[1]
        if self.index is None:
            self.index = faiss.IndexFlatIP(d)

        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)

        self.docs.extend(docs)

        faiss.write_index(self.index, str(self.index_path))
        with self.metadata_path.open("w", encoding="utf-8") as f:
            json.dump(self.docs, f, ensure_ascii=False, indent=2)

    def search(self, query_emb: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        if self.index is None:
            raise RuntimeError("FAISS index boş. Önce index job çalışmalı.")

        q = query_emb.reshape(1, -1).astype("float32")
        faiss.normalize_L2(q)
        scores, idxs = self.index.search(q, top_k)

        scores = scores[0]
        idxs = idxs[0]

        results: List[Dict[str, Any]] = []
        for i, score in zip(idxs, scores):
            if i == -1:
                continue
            doc = self.docs[int(i)]
            results.append(
                {
                    "score": float(score),
                    **doc,
                }
            )
        return results
