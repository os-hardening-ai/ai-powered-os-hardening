from __future__ import annotations

from typing import List
import os
import time
from dotenv import load_dotenv
import numpy as np
from openai import OpenAI, RateLimitError, APIError

from config.config_loader import get_config
from core.embeddings.base import IEmbeddingClient


class NovitaEmbeddingClient(IEmbeddingClient):
    """
    Novita.ai üzerinde OpenAI uyumlu embedding client.

    Özellikler:
      - Batch'leyerek istek atar
      - Dakikadaki istek sayısını sınırlayan basit rate limiter
      - 429 (RATE_LIMIT_EXCEEDED) için backoff + retry
      - 5xx server error'larda batch'i bölüp tekrar dener
    """

    def __init__(self) -> None:
        load_dotenv() 
        cfg = get_config().embedding

        api_key = os.getenv("NOVITA_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Novita API key embedding.api_key veya NOVITA_API_KEY environment değişkeni ile verilmelidir."
            )

        base_url = cfg.base_url or "https://api.novita.ai/openai"

        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self._model_name = cfg.model_name
        self._dim = cfg.dim

        # 🔥 Rate limit ayarları (Novita free/standart için muhafazakâr)
        self._max_calls_per_minute = 50      # istersen bunu deneyerek artırabilirsin
        self._calls_in_window = 0
        self._window_start = time.time()

        # Batch boyutu
        self._batch_size = 32                # 32 text / çağrı

    # ----------------- RATE LIMIT HELPER ----------------- #
    def _before_api_call(self) -> None:
        """
        Dakikadaki istek sayısını takip eder, limit dolduysa sleep atar.
        """
        now = time.time()
        elapsed = now - self._window_start

        # 60 sn'lik pencereyi resetle
        if elapsed >= 60:
            self._window_start = now
            self._calls_in_window = 0

        # Limit dolduysa yeni pencereye kadar bekle
        if self._calls_in_window >= self._max_calls_per_minute:
            sleep_for = 60 - elapsed
            if sleep_for > 0:
                print(f"[NovitaEmbeddingClient] Rate limit → {sleep_for:.1f}s bekleniyor...")
                time.sleep(sleep_for)
            # yeni pencere
            self._window_start = time.time()
            self._calls_in_window = 0

        self._calls_in_window += 1

    # ----------------- LOW LEVEL RETRY HELPER ----------------- #
    def _embed_batch_with_retry(
        self,
        texts: List[str],
        max_retries: int = 3,
        input_type: str | None = None,  # Novita/OpenAI için gerek yok ama interface dursun
    ) -> np.ndarray:
        """
        Tek bir batch'i embed eder.
        - 429: exponential backoff ile yeniden dene
        - 5xx: batch'i ikiye bölüp recursive olarak dene
        """
        attempt = 0

        while True:
            self._before_api_call()
            try:
                resp = self._client.embeddings.create(
                    model=self._model_name,
                    input=texts,
                )
                vectors = [item.embedding for item in resp.data]
                return np.array(vectors, dtype="float32")

            except RateLimitError as e:
                if attempt < max_retries:
                    wait = 5 * (attempt + 1)
                    print(f"[NovitaEmbeddingClient] 429 RATE_LIMIT_EXCEEDED (attempt={attempt+1}) → {wait}s bekleniyor...")
                    time.sleep(wait)
                    attempt += 1
                    continue
                print("[NovitaEmbeddingClient] Rate limit retry denemeleri bitti, hatayı yükseltiyorum.")
                raise

            except APIError as e:
                status = getattr(e, "status_code", None)
                msg = getattr(e, "message", str(e))

                # 5xx ise ve batch 1'den büyükse ikiye böl
                if status and status >= 500 and len(texts) > 1:
                    print(
                        f"[NovitaEmbeddingClient] {status} server error (batch_size={len(texts)}), "
                        f"batch ikiye bölünüyor..."
                    )
                    mid = len(texts) // 2
                    left = texts[:mid]
                    right = texts[mid:]

                    left_vecs = self._embed_batch_with_retry(left, max_retries=max_retries, input_type=input_type)
                    right_vecs = self._embed_batch_with_retry(right, max_retries=max_retries, input_type=input_type)
                    return np.vstack([left_vecs, right_vecs])

                print(f"[NovitaEmbeddingClient] APIError (status={status}) msg={msg}")
                raise

            except Exception as e:
                # Beklenmeyen diğer hatalar
                print(f"[NovitaEmbeddingClient] Beklenmeyen hata: {type(e).__name__}: {e}")
                raise

    # ----------------- PUBLIC API ----------------- #
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Bir liste text'i batch'lere bölerek embed eder.
        Her batch, _embed_batch_with_retry ile gönderilir.
        """
        if not texts:
            return np.zeros((0, self._dim), dtype="float32")

        all_vectors: List[np.ndarray] = []

        for i in range(0, len(texts), self._batch_size):
            batch = texts[i:i + self._batch_size]
            print(
                f"[NovitaEmbeddingClient] Embedding batch {i}–{i+len(batch)-1} "
                f"(size={len(batch)})"
            )
            vecs = self._embed_batch_with_retry(batch)
            all_vectors.append(vecs)

        return np.vstack(all_vectors)

    def embed_query(self, text: str) -> np.ndarray:
        """
        Tek query için embedding (RAG query time).
        """
        vecs = self._embed_batch_with_retry([text])
        return vecs[0]
