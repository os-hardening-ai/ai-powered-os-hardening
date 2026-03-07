from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, List

from dotenv import load_dotenv
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from qdrant_client.http.exceptions import ResponseHandlingException

from config.config_loader import get_config
from core.vector_store.base import IVectorStore


class QdrantVectorStore(IVectorStore):
    """
    Qdrant Cloud üzerinde collection tutan vektör veritabanı implementasyonu.
    Her doküman payload'ına hem 'text' hem de metadata alanlarını yazıyoruz.
    """

    def __init__(self,batch_size : int = 100) -> None:
        load_dotenv()
        cfg = get_config()
        vs_cfg = cfg.vector_store
        qd_cfg = vs_cfg.qdrant
        self._batch_size = batch_size

        # qd_cfg pydantic model ise attribute, dict ise key şeklinde erişelim
        url = getattr(qd_cfg, "url", None) or qd_cfg.get("url")
        coll_name = getattr(qd_cfg, "collection_name", None) or qd_cfg.get("collection_name")

        if not url:
            raise RuntimeError("Qdrant URL config.vector_store.qdrant altında tanımlanmalı.")
        if not coll_name:
            raise RuntimeError("Qdrant collection_name config.vector_store.qdrant altında tanımlanmalı.")

        self._collection = coll_name
        self._dim = cfg.embedding.dim

        api_key = os.getenv("QDRANT_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Qdrant API key config.vector_store.qdrant.api_key veya QDRANT_API_KEY env ile verilmelidir."
            )

        self._client = QdrantClient(
            url=url,
            api_key=api_key,
            timeout=120.0
        )

        self._ensure_collection()

    def _ensure_collection(self) -> None:
        try:
            self._client.get_collection(self._collection)
        except Exception:
            # Yoksa oluştur
            self._client.recreate_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=self._dim,
                    distance=Distance.COSINE,
                ),
            )

    def upsert(self, embeddings: np.ndarray, docs: List[Dict[str, Any]]) -> None:
        if embeddings.shape[0] != len(docs):
            raise ValueError("Embeddings ve docs uzunluğu eşleşmiyor.")

        # Qdrant float32 istiyor
        vectors = embeddings.astype("float32")

        batch_size = self._batch_size or 200
        total = vectors.shape[0]

        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch_vecs = vectors[start:end].tolist()
            batch_docs = docs[start:end]

            points: List[PointStruct] = []
            for doc, vec in zip(batch_docs, batch_vecs):
                # doc: {"id": ..., "text": ..., "metadata": {...}}
                point_id = str(uuid.uuid4())

                payload: Dict[str, Any] = {
                    "chunk_id": doc["id"],
                    "text": doc["text"],
                }
                metadata = doc.get("metadata") or {}
                payload.update(metadata)

                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vec,
                        payload=payload,
                    )
                )
            for attempt in range(3):
                try:
                    self._client.upsert(
                        collection_name=self._collection,
                        points=points,
                        wait=True,
                    )
                    break
                except ResponseHandlingException as e:
                    if attempt == 2:
                        raise
                    time.sleep(1 + attempt)

    def search(self, query_emb: np.ndarray, top_k: int = 5, min_score: float = 0.0) -> List[Dict[str, Any]]:
        q = query_emb.astype("float32").tolist()

        # Bazı qdrant-client sürümlerinde `search` yok, yerine `query_points` var.
        if hasattr(self._client, "search"):
            # Klasik API
            hits = self._client.search(
                collection_name=self._collection,
                query_vector=q,
                limit=top_k * 2,  # Min_score filter için daha fazla getir
            )
        else:
            # Yeni Query API / farklı sürümler
            resp = self._client.query_points(
                collection_name=self._collection,
                query=q,
                limit=top_k * 2,
            )
            hits = resp.points

        results: List[Dict[str, Any]] = []
        for h in hits:
            # Min score filtering
            if h.score < min_score:
                continue
                
            payload = h.payload or {}
            text = payload.get("text", "")
            # chunk id'yi geri al (biz payload'a chunk_id koymuştuk)
            doc_id = payload.get("chunk_id", h.id)

            # text ve chunk_id dışındaki her şeyi metadata'ya koy
            metadata = {
                k: v for k, v in payload.items()
                if k not in ("text", "chunk_id")
            }

            results.append(
                {
                    "score": float(h.score),
                    "id": doc_id,
                    "text": text,
                    "metadata": metadata,
                }
            )
            
            # Yeterli sonuç tuttuk
            if len(results) >= top_k:
                break

        return results
