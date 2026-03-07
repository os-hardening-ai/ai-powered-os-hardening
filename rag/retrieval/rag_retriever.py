from __future__ import annotations
import re
from typing import List, Dict, Any
import numpy as np
from core.embeddings import get_embedding_client
from core.vector_store import get_vector_store
from api.schemas import RagSearchResult

def _is_junky_window(w: str) -> bool:
    """
    URL / referans / çok kısa saçma pencereleri ele.
    Çok agresif değil, kaba bir temizlik.
    """
    txt = w.strip()
    if not txt:
        return True

    # Kısacık şeyleri at
    if len(txt) < 40:
        return True

    # Sadece URL listesi gibi görünenler
    if txt.count("http://") + txt.count("https://") >= 1 and len(txt) < 300:
        return True

    # 'References' sayfası gibi pattern'ler
    lower = txt.lower()
    if "references:" in lower and len(txt) < 250:
        return True

    # Harf sayısı çok azsa (sayı/tablo vs)
    import re
    letters = re.findall(r"[A-Za-zĞÜŞİÖÇığüşiöç]", txt)
    if len(letters) < 25:
        return True

    return False

def split_into_sentences(text: str) -> List[str]:
    """
    Çok ileri gitmeden basit bir cümle bölücü.
    İstersen sonra nltk / spacy ile değiştirirsin.
    """
    text = text.strip()
    if not text:
        return []

    # Nokta, soru, ünleme göre kaba bölme
    parts = re.split(r'(?<=[\.!\?])\s+', text)
    # Boşları at
    sentences = [p.strip() for p in parts if p.strip()]
    return sentences


def build_sliding_windows(
    sentences: List[str],
    window_size: int = 3,
    stride: int = 1,
) -> List[str]:
    """
    3 cümlelik kaymalı pencereler oluşturur. 
    Örn: [s0 s1 s2], [s1 s2 s3], ...
    """
    if not sentences:
        return []

    windows: List[str] = []
    n = len(sentences)
    i = 0
    while i < n:
        window = sentences[i : i + window_size]
        if not window:
            break
        windows.append(" ".join(window))
        if i + window_size >= n:
            break
        i += stride
    return windows

def cosine_sim(a, b) -> float:
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-8
    return float(np.dot(a, b) / denom)

class RAGRetriever:
    """
    Sadece retrieval (top-k chunk getirme) yapan servis.
    Embedding provider + vector store, config.json üzerinden geliyor.
    
    - search_raw: eski direkt top-k arama (late chunk yok)
    - search: varsayılan olarak late chunking kullanan arama
    """

    def __init__(self) -> None:
        self._embed_client = get_embedding_client()
        self._vector_store = get_vector_store()

    # ==== 1) Eski davranış: direkt Qdrant top-k ====
    def search_raw(self, query: str, top_k: int = 5) -> List[RagSearchResult]:
        """
        Eski basit search: query'i embed et → vector store'dan top-k chunk çek.
        Late chunking yok.
        """
        # 1) Query'i embed et
        query_emb = self._embed_client.embed_query(query)

        # 2) Vector store'dan top-k sonuçları çek
        raw_results = self._vector_store.search(query_emb, top_k=top_k)

        # Beklenen şekil: {"score": float, "id": ..., "text": ..., "metadata": {...}}
        results: List[RagSearchResult] = []
        for r in raw_results:
            results.append(
                RagSearchResult(
                    id=str(r.get("id")),
                    score=float(r.get("score", 0.0)),
                    text=r.get("text", ""),
                    metadata=r.get("metadata", {}),
                )
            )
        return results

    # ==== 2) Late chunk refine ====
    def _late_chunk_refine(
        self,
        query: str,
        query_emb,  # <<< query_emb'i dışarıdan alacağız
        coarse_results: List[Dict[str, Any]],
        top_k_fine: int = 5,
        window_size: int = 3,
        stride: int = 1,
        max_windows_per_chunk: int = 10,
        min_score: float = 0.7,
    ) -> List[RagSearchResult]:
        """
        coarse_results: vector_store.search'ten gelen büyük chunk'lar.
        Burada runtime'da cümlelere bölüp küçük pencereler oluşturuyoruz.
        """
        fine_candidates: List[Dict[str, Any]] = []

        for r in coarse_results:
            base_text: str = r.get("text", "") or ""
            base_meta: Dict[str, Any] = r.get("metadata", {}) or {}

            sentences = split_into_sentences(base_text)
            windows = build_sliding_windows(
                sentences,
                window_size=window_size,
                stride=stride,
            )

            # Çok uzun sayfaları tamamen patlatmamak için sınır koyalım
            windows = windows[:max_windows_per_chunk]

            for idx, w in enumerate(windows):
                if _is_junky_window(w):
                    continue

                meta = dict(base_meta)
                meta["window_index"] = idx
                fine_candidates.append(
                    {
                        "id": r.get("id"),
                        "text": w,
                        "metadata": meta,
                    }
                )

        # Hiç düzgün window kalmazsa: coarse fallback
        if not fine_candidates:
            results: List[RagSearchResult] = []
            for r in coarse_results[:top_k_fine]:
                results.append(
                    RagSearchResult(
                        id=str(r.get("id")),
                        score=float(r.get("score", 0.0)),
                        text=r.get("text", ""),
                        metadata=r.get("metadata", {}),
                    )
                )
            return results

        texts = [c["text"] for c in fine_candidates]

        # embed_documents varsa onu kullan
        if hasattr(self._embed_client, "embed_documents"):
            embs = self._embed_client.embed_documents(texts)
        else:
            embs = [self._embed_client.embed_query(t) for t in texts]

        scored: List[Dict[str, Any]] = []
        for c, emb in zip(fine_candidates, embs):
            score = cosine_sim(query_emb, emb)
            scored.append(
                {
                    "id": c["id"],
                    "text": c["text"],
                    "metadata": c["metadata"],
                    "score": score,
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)

        results: List[RagSearchResult] = []
        for s in scored:
            # Min score filtering
            if s["score"] < min_score:
                continue
                
            results.append(
                RagSearchResult(
                    id=str(s["id"]),
                    score=float(s["score"]),
                    text=s["text"],
                    metadata=s["metadata"],
                )
            )
            
            # Yeterli sonuç tuttuk
            if len(results) >= top_k_fine:
                break
                
        return results

    # ==== 3) Dışarı açılan search: default late chunking ====
    def search(
        self,
        query: str,
        top_k: int = 5,
        use_late_chunking: bool = True,
        coarse_k_factor: int = 3,
        window_size: int = 3,
        stride: int = 1,
        min_score: float = 0.3,  # Minimum relevance score için threshold (default: 0.3)
    ) -> List[RagSearchResult]:
        """
        Varsayılan: late chunking açık.
        istersen use_late_chunking=False ile eski davranışa dönebilirsin.
        
        Args:
            query: Arama sorgusu
            top_k: Döndürülecek sonuç sayısı
            use_late_chunking: Late chunking kullan mı?
            coarse_k_factor: Koarse k faktörü
            window_size: Pencere boyutu
            stride: Pencere stride'ı
            min_score: Minimum relevance score (default: 0.7)
        """
        # Query için embedding'i sadece 1 kez üret
        query_emb = self._embed_client.embed_query(query)

        if not use_late_chunking:
            raw_results = self._vector_store.search(query_emb, top_k=top_k, min_score=min_score)
            results: List[RagSearchResult] = []
            for r in raw_results:
                # Min score filtering
                if float(r.get("score", 0.0)) < min_score:
                    continue
                results.append(
                    RagSearchResult(
                        id=str(r.get("id")),
                        score=float(r.get("score", 0.0)),
                        text=r.get("text", ""),
                        metadata=r.get("metadata", {}),
                    )
                )
            return results

        # Coarse k'i sınırla (çok büyümesin)
        coarse_k = max(top_k * coarse_k_factor, top_k)
        coarse_k = min(coarse_k, 20)  # güvenlik: en fazta 20 büyük chunk

        # Coarse level'de daha düşük threshold (fine level'de yüksek tutacağız)
        raw_results = self._vector_store.search(query_emb, top_k=coarse_k, min_score=max(min_score * 0.5, 0.0))

        fine_results = self._late_chunk_refine(
            query=query,
            query_emb=query_emb,
            coarse_results=raw_results,
            top_k_fine=top_k,
            window_size=window_size,
            stride=stride,
            max_windows_per_chunk=10,
            min_score=min_score,
        )
        return fine_results

