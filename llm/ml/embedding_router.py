"""
Embedding-benzerlik tabanlı intent router (semantic router).

NEDEN: TF-IDF + LogReg sınıflandırıcı kelime-yüzeyine bağlı → argo/yazım-hatası/beklenmedik
ifadelere kırılgan ("naber" destanı) ve yeni ifade için retrain gerektirir. Embedding-benzerlik
router ise ANLAM uzayında çalışır: referans örneklere kosinüs-benzerliğiyle oylar. Retrain
GEREKMEZ (yeni örnek = referans setine bir satır), çok-dilli + typo toleranslı.

TASARIM:
- Referanslar `data/intent_training_dataset.csv` (text,intent) → intent başına örnekler.
- Embedding'ler bir kez hesaplanır + `llm/ml/models/intent_embeddings.npz`'e CACHE'lenir
  (CSV içeriği + model adı hash'iyle anahtarlı → CSV değişirse otomatik yeniden kurulur).
- predict(text): sorguyu embed et → tüm referanslara kosinüs → sınıf başına top-k ortalaması →
  en yüksek sınıf kazanır. Global en yüksek benzerlik düşükse → out_of_scope (eşik).
- Drop-in: `MLIntent(type, confidence, probabilities)` döndürür (MLIntentDetector ile aynı arayüz).

Test edilebilirlik: embed_client ENJEKTE edilebilir (gerçek API yerine sahte embedder ile test).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import List, Optional

import numpy as np

from llm.ml.intent_detector import MLIntent

logger = logging.getLogger("embedding_router")

_DEFAULT_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "intent_training_dataset.csv"
_DEFAULT_CACHE = Path(__file__).resolve().parent / "models" / "intent_embeddings.npz"

# İntent başına en fazla referans. None → SINIRSIZ: CSV'deki tüm örnekler referans olur
# (daha geniş anlam kapsama; npz bir kez kurulur, kosinüs maliyeti önemsiz).
_MAX_PER_INTENT: Optional[int] = None
# Global en yüksek kosinüs bunun altındaysa hiçbir sınıfa benzemiyor → out_of_scope.
_OOS_SIM_THRESHOLD = 0.42
# Sınıf skoru = o sınıfın en yüksek k benzerliğinin ortalaması (tek outlier domine etmesin).
_TOPK = 3


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    """Satır-bazlı L2 normalizasyon (kosinüs = normalize vektörlerin nokta çarpımı)."""
    norms = np.linalg.norm(mat, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def _csv_signature(csv_path: Path, model_name: str) -> str:
    """CSV içeriği + model adından kararlı imza (cache geçerliliği için)."""
    h = hashlib.sha256()
    h.update(model_name.encode("utf-8"))
    h.update(csv_path.read_bytes())
    h.update(str(_MAX_PER_INTENT).encode("utf-8"))
    return h.hexdigest()[:16]


def _sample_references(csv_path: Path) -> tuple[List[str], List[str]]:
    """CSV'den referans örnekleri çek. _MAX_PER_INTENT=None ise intent başına TÜM örnekler
    (sınırsız); bir sayı verilirse intent başına ilk N (deterministik)."""
    import pandas as pd

    df = pd.read_csv(csv_path)
    texts: List[str] = []
    labels: List[str] = []
    for intent, grp in df.groupby("intent"):
        rows = [t for t in grp["text"].astype(str).str.strip().tolist() if t]
        if _MAX_PER_INTENT is not None:
            rows = rows[:_MAX_PER_INTENT]
        texts.extend(rows)
        labels.extend([str(intent)] * len(rows))
    return texts, labels


class EmbeddingIntentRouter:
    """Embedding-benzerlik intent router — MLIntentDetector ile aynı `predict()` arayüzü."""

    def __init__(
        self,
        embed_client=None,
        csv_path: Optional[Path] = None,
        cache_path: Optional[Path] = None,
        oos_threshold: float = _OOS_SIM_THRESHOLD,
        topk: int = _TOPK,
        debug: bool = False,
    ) -> None:
        self.csv_path = Path(csv_path) if csv_path else _DEFAULT_CSV
        self.cache_path = Path(cache_path) if cache_path else _DEFAULT_CACHE
        self.oos_threshold = oos_threshold
        self.topk = topk
        self.debug = debug
        self._embed_client = embed_client  # None → lazy (ilk gerekince Novita kurulur)

        self._vectors: Optional[np.ndarray] = None     # (n, dim) L2-normalize
        self._labels: Optional[np.ndarray] = None       # (n,)
        self._classes: List[str] = []
        self._model_name: str = ""
        self._ensure_references()

    # ── embedding client (lazy) ──────────────────────────────────────────────
    def _client(self):
        if self._embed_client is None:
            from rag.embeddings import get_embedding_client
            self._embed_client = get_embedding_client()
        return self._embed_client

    def _resolve_model_name(self) -> str:
        try:
            from config.config_loader import get_config
            return get_config().embedding.model_name
        except Exception:
            return "unknown-embedding-model"

    # ── referans seti (cache veya kur) ───────────────────────────────────────
    def _ensure_references(self) -> None:
        self._model_name = self._resolve_model_name()
        sig = _csv_signature(self.csv_path, self._model_name)
        if self._load_cache(sig):
            if self.debug:
                logger.info("[EmbeddingRouter] cache HIT (%d ref)", len(self._labels))
            return
        if self.debug:
            logger.info("[EmbeddingRouter] cache MISS → referanslar embed ediliyor")
        texts, labels = _sample_references(self.csv_path)
        vecs = np.asarray(self._client().embed_texts(texts), dtype=np.float32)
        self._vectors = _l2_normalize(vecs)
        self._labels = np.asarray(labels, dtype=object)
        self._classes = sorted(set(labels))
        self._save_cache(sig)

    def _load_cache(self, sig: str) -> bool:
        if not self.cache_path.exists():
            return False
        try:
            data = np.load(self.cache_path, allow_pickle=True)
            if str(data.get("sig")) != sig:
                return False
            self._vectors = _l2_normalize(np.asarray(data["vectors"], dtype=np.float32))
            self._labels = np.asarray(data["labels"], dtype=object)
            self._classes = sorted(set(self._labels.tolist()))
            return True
        except Exception as exc:  # bozuk cache → yeniden kur
            logger.warning("[EmbeddingRouter] cache okunamadı (yeniden kurulacak): %s", exc)
            return False

    def _save_cache(self, sig: str) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                self.cache_path,
                vectors=self._vectors.astype(np.float16),  # disk için float16 (kosinüs için yeterli)
                labels=self._labels,
                sig=sig,
                model=self._model_name,
            )
            if self.debug:
                logger.info("[EmbeddingRouter] cache yazıldı: %s (%d ref)", self.cache_path, len(self._labels))
        except Exception as exc:
            logger.warning("[EmbeddingRouter] cache yazılamadı (önemsiz): %s", exc)

    # ── tahmin ───────────────────────────────────────────────────────────────
    def predict(self, text: str) -> MLIntent:
        """Sorguyu embed et → referanslara kosinüs → sınıf başına top-k ortalaması → MLIntent."""
        if self._vectors is None or len(self._vectors) == 0:
            raise RuntimeError("EmbeddingRouter: referans seti boş")

        q = np.asarray(self._client().embed_query(text), dtype=np.float32).reshape(-1)
        q = q / (np.linalg.norm(q) or 1.0)
        sims = self._vectors @ q  # kosinüs (her ikisi de L2-normalize) → (n,)

        scores: dict[str, float] = {}
        for cls in self._classes:
            cls_sims = sims[self._labels == cls]
            if cls_sims.size == 0:
                continue
            top = np.sort(cls_sims)[::-1][: self.topk]
            scores[cls] = float(top.mean())

        best = max(scores, key=scores.get)
        best_score = scores[best]
        global_max = float(sims.max())

        labels_sorted = list(scores.keys())
        arr = np.array([scores[c] for c in labels_sorted], dtype=np.float64)
        exp = np.exp((arr - arr.max()) * 8.0)  # sıcaklık ölçeği (ayrımı keskinleştir)
        probs = {c: float(p) for c, p in zip(labels_sorted, exp / exp.sum())}

        if global_max < self.oos_threshold:
            if self.debug:
                logger.info("[EmbeddingRouter] %r global_max=%.3f < %.2f → out_of_scope",
                            text, global_max, self.oos_threshold)
            return MLIntent(type="out_of_scope", confidence=1.0 - global_max, probabilities=probs)

        if self.debug:
            logger.info("[EmbeddingRouter] %r → %s (score=%.3f, gmax=%.3f)",
                        text, best, best_score, global_max)
        return MLIntent(type=best, confidence=best_score, probabilities=probs)
