from __future__ import annotations

import os
from typing import List
import time

from dotenv import load_dotenv
import numpy as np
import cohere

from config.config_loader import get_config
from core.embeddings.base import IEmbeddingClient


class CohereEmbeddingClient(IEmbeddingClient):
    """
    Cohere embed-multilingual-v3.0 kullanarak TR+EN uyumlu embedding üretir.
    + Dakikada istek sayısını kontrol eden basit bir rate limiter içerir.
    """

    def __init__(self) -> None:
        load_dotenv() 
        cfg = get_config().embedding
        api_key = os.getenv("COHERE_API_KEY")

        self._client = cohere.Client(api_key=api_key)
        self._model_name = cfg.model_name
        self._dim = cfg.dim

        self._max_calls_per_minute = 60   # Cohere trial: 100 call/min → 60 ile güvenli kal
        self._calls_in_window = 0
        self._window_start = time.time()

        # Aynı anda kaç text embed edeceğiz (batch)
        self._batch_size = 32  # çok yüksek yapma, token limitine de saygılı ol

    # ----------------- RATE LIMIT HELPER ----------------- #
    def _before_api_call(self) -> None:
        """Dakikadaki istek sayısını kontrol eder, gerekirse sleep atar."""
        now = time.time()
        elapsed = now - self._window_start

        # 1 dakikalık pencereyi resetle
        if elapsed >= 60:
            self._window_start = now
            self._calls_in_window = 0

        # Limit aşıldıysa yeni pencereye kadar bekle
        if self._calls_in_window >= self._max_calls_per_minute:
            sleep_for = 60 - elapsed
            if sleep_for > 0:
                print(f"[CohereEmbeddingClient] Rate limit yaklaştı, {sleep_for:.1f}s bekleniyor...")
                time.sleep(sleep_for)
            # pencereyi sıfırla
            self._window_start = time.time()
            self._calls_in_window = 0

        self._calls_in_window += 1

    # ----------------- PUBLIC API ----------------- #
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Çok sayıda text geldiğinde:
          - Batch'lere böler
          - Her batch için rate limit'e saygı gösterir
          - Tüm embeddingleri birleştirip (N, dim) numpy array olarak döner.
        """
        if not texts:
            return np.zeros((0, self._dim), dtype="float32")

        all_vectors: List[np.ndarray] = []

        for i in range(0, len(texts), self._batch_size):
            batch = texts[i:i + self._batch_size]

            # Rate limit kontrolü
            self._before_api_call()

            resp = self._client.embed(
                model=self._model_name,
                texts=batch,
                input_type="search_document",  # doküman embedding
            )
            vectors = np.array(resp.embeddings, dtype="float32")
            all_vectors.append(vectors)

        return np.vstack(all_vectors)

    def embed_query(self, text: str) -> np.ndarray:
        """Tek query için embedding (search_query tipi)."""
        self._before_api_call()

        resp = self._client.embed(
            model=self._model_name,
            texts=[text],
            input_type="search_query",
        )
        vec = np.array(resp.embeddings[0], dtype="float32")
        return vec
