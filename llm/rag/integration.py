# rag_integration.py
"""
RAG Retrieval ile LLM Pipeline entegrasyonu.
CIS benchmark dokümanlarından ilgili bilgileri getirip LLM'e context olarak sunar.
"""

from __future__ import annotations
import logging
from typing import List, Dict, Any, Tuple

try:
    from rag.embeddings import get_embedding_client
    from rag.vector_store import get_vector_store
    RAG_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] Could not import RAG dependencies: {e}")
    print("[WARNING] RAG functionality will be limited")
    get_embedding_client = None  # type: ignore
    get_vector_store = None  # type: ignore
    RAG_AVAILABLE = False

try:
    from rag.retrieval.hybrid_retriever import InContextHybridScorer, is_hybrid_available
    _HYBRID_AVAILABLE = is_hybrid_available()
except ImportError:
    InContextHybridScorer = None  # type: ignore
    _HYBRID_AVAILABLE = False

from rag.retrieval.reranker import MMRReranker

_logger = logging.getLogger(__name__)


class RAGContextBuilder:
    """
    RAG sistemi ile LLM pipeline arasında köprü.
    Kullanıcı sorusuna göre ilgili doküman chunk'larını getirir.

    Enhanced mod (config'de enhanced_rag.enabled=true ise):
      - InContextHybridScorer: BM25 + dense scores via RRF fusion
      - MMRReranker: diversity-aware reranking (no extra embed calls)
      - retrieve_multi(): fan-out over query-planner expanded queries
    """

    def __init__(
        self,
        top_k: int = 5,
        min_score: float | None = None,
        use_hybrid: bool | None = None,
        use_mmr: bool | None = None,
        os_version: str | None = None,
    ):
        self.top_k = top_k

        if min_score is None:
            try:
                from config.config_loader import get_config
                self.min_score = get_config().rag.retrieval.get("min_score", 0.5)
            except Exception:
                self.min_score = 0.5
        else:
            self.min_score = min_score

        if get_embedding_client is None or get_vector_store is None:
            raise RuntimeError("RAG dependencies not available.")

        self._embed_client = get_embedding_client()
        self._vector_store = get_vector_store()

        # Resolve enhanced-mode flags from config (or explicit override)
        enhanced_cfg = self._load_enhanced_config()
        self._use_hybrid = use_hybrid if use_hybrid is not None else enhanced_cfg.get("use_hybrid", False)
        self._use_mmr = use_mmr if use_mmr is not None else enhanced_cfg.get("use_mmr", False)

        # OS metadata filter (soft: filtresiz fallback mevcuttur)
        self._os_version = os_version

        # Lazy-init scorers only when enabled
        self._hybrid_scorer: InContextHybridScorer | None = None
        if self._use_hybrid and _HYBRID_AVAILABLE and InContextHybridScorer is not None:
            self._hybrid_scorer = InContextHybridScorer(
                dense_weight=enhanced_cfg.get("dense_weight", 0.6),
                sparse_weight=enhanced_cfg.get("sparse_weight", 0.4),
            )
            _logger.info("[RAGContextBuilder] InContextHybridScorer enabled")

        self._mmr_reranker: MMRReranker | None = None
        if self._use_mmr:
            self._mmr_reranker = MMRReranker(
                lambda_param=enhanced_cfg.get("mmr_lambda", 0.7),
                max_per_source=enhanced_cfg.get("mmr_max_per_source", 3),
            )
            _logger.info("[RAGContextBuilder] MMRReranker enabled")

    @staticmethod
    def _load_enhanced_config() -> dict:
        try:
            from config.config_loader import get_config
            cfg = get_config()
            return getattr(cfg.rag, "enhanced", None) or {}
        except Exception:
            return {}

    # ── internal search helpers ───────────────────────────────────────────────

    def _search(self, query: str, doc_type: str | None = None) -> List[Dict[str, Any]]:
        print(f"[RAG._search] Embedding query: '{query[:60]}'")
        query_emb = self._embed_client.embed_query(query)
        print(f"[RAG._search] Searching vector store (top_k={self.top_k}, doc_type={doc_type})...")
        raw_results = self._vector_store.search(query_emb, top_k=self.top_k, doc_type=doc_type)
        scores = [round(r.get("score", 0), 3) for r in raw_results]
        print(f"[RAG._search] Raw scores: {scores}")
        filtered = [r for r in raw_results if r.get("score", 0.0) >= self.min_score]
        print(f"[RAG._search] {len(raw_results)} results, {len(filtered)} pass min_score={self.min_score}")
        return filtered

    def _search_with_emb(
        self,
        query_emb,
        top_k: int,
        doc_type: str | None = None,
        os_version: str | None = None,
    ) -> List[Dict[str, Any]]:
        effective_os = os_version if os_version is not None else self._os_version

        if effective_os:
            # Soft filter: önce OS filtreyle dene, yetersizse filtresiz fallback
            filtered = self._vector_store.search(
                query_emb, top_k=top_k, doc_type=doc_type, os_version=effective_os
            )
            filtered = [r for r in filtered if r.get("score", 0.0) >= self.min_score]
            if len(filtered) >= max(1, top_k // 2):
                return filtered
            # Yeterli sonuç gelmediyse os_version filtresi olmadan dene
            _logger.debug(
                "[RAGContextBuilder] OS filter '%s' → %d sonuç, filtresiz fallback",
                effective_os,
                len(filtered),
            )

        raw_results = self._vector_store.search(query_emb, top_k=top_k, doc_type=doc_type)
        return [r for r in raw_results if r.get("score", 0.0) >= self.min_score]

    def _apply_hybrid_and_mmr(
        self,
        query: str,
        combined: List[Dict[str, Any]],
        final_top_n: int,
    ) -> List[Dict[str, Any]]:
        """Apply BM25 hybrid fusion then MMR reranking to a candidate list."""
        if not combined:
            return combined

        # Step 1: hybrid BM25 re-scoring
        if self._hybrid_scorer is not None:
            fused = self._hybrid_scorer.score(query, combined, top_n=None)
            combined = [
                {
                    "id": r.id,
                    "text": r.text,
                    "metadata": r.metadata,
                    "score": r.fused_score,
                    "dense_score": r.dense_score,
                    "sparse_score": r.sparse_score,
                }
                for r in fused
            ]

        # Step 2: MMR diversity reranking
        if self._mmr_reranker is not None:
            reranked = self._mmr_reranker.rerank(combined, top_n=final_top_n)
            combined = [
                {
                    "id": r.id,
                    "text": r.text,
                    "metadata": r.metadata,
                    "score": r.original_score,
                }
                for r in reranked
            ]
        else:
            combined.sort(key=lambda r: r.get("score", 0.0), reverse=True)
            combined = combined[:final_top_n]

        return combined

    # ── refinement loop ───────────────────────────────────────────────────────

    def _max_score(self, results: List[Dict[str, Any]]) -> float:
        return max((r.get("score", 0.0) for r in results), default=0.0)

    def _refinement_retrieve(
        self,
        query: str,
        initial: List[Dict[str, Any]],
        min_confidence: float = 0.55,
        max_attempts: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Başlangıç sonuçlarının max skoru min_confidence'ın altındaysa iki
        strateji ile yeniden dener:

          1. Top-k'yı iki katına çıkarıp min_score'u gevşet (0.3'e indir).
          2. Fallback: hiç min_score filtresi olmadan en yüksek top-k.

        Her iki deneme de skoru iyileştirmezse orijinal sonuçlar döner.
        """
        if not initial:
            return initial
        if self._max_score(initial) >= min_confidence:
            return initial

        _logger.info(
            "[RefinementLoop] max_score=%.3f < %.3f — yeniden retrieval başlatılıyor",
            self._max_score(initial),
            min_confidence,
        )

        best = initial
        relaxed_min = 0.3
        relaxed_k = self.top_k * 2

        for attempt in range(1, max_attempts + 1):
            try:
                q_emb = self._embed_client.embed_query(query)
                hits = (
                    self._search_with_emb(q_emb, top_k=relaxed_k, doc_type="yaml_rule")
                    + self._search_with_emb(q_emb, top_k=relaxed_k, doc_type="cis_benchmark")
                )
                # min_score filtresi gevşet
                hits = [r for r in hits if r.get("score", 0.0) >= relaxed_min]
                hits.sort(key=lambda r: r.get("score", 0.0), reverse=True)

                if hits and self._max_score(hits) > self._max_score(best):
                    _logger.info(
                        "[RefinementLoop] attempt=%d: max_score %.3f → %.3f",
                        attempt,
                        self._max_score(best),
                        self._max_score(hits),
                    )
                    best = hits
                    if self._max_score(best) >= min_confidence:
                        break
                else:
                    break

                # İkinci denemede min_score'u tamamen kaldır
                relaxed_min = 0.0

            except Exception as exc:
                _logger.warning("[RefinementLoop] attempt=%d failed: %s", attempt, exc)
                break

        return best

    def _format_context(self, filtered_results: List[Dict[str, Any]]) -> str:
        context_parts = []
        for idx, result in enumerate(filtered_results, start=1):
            text = result.get("text", "").strip()
            score = result.get("score", 0.0)
            metadata = result.get("metadata", {})

            source = metadata.get("benchmark_product") or metadata.get("source_id") or "CIS Benchmark"
            section_id = metadata.get("section_id") or metadata.get("section") or ""
            section_title = metadata.get("section_title") or metadata.get("title") or ""
            if section_id and section_title and section_id != section_title:
                section = f"{section_id} - {section_title}"
            elif section_id:
                section = section_id
            elif section_title:
                section = section_title
            else:
                section = "N/A"

            context_parts.append(
                f"[Kaynak {idx}] (Relevance: {score:.2f})\n"
                f"Doküman: {source}\n"
                f"Bölüm: {section}\n"
                f"İçerik:\n{text}\n"
            )

        return "\n" + "=" * 60 + "\n" + "\n".join(context_parts) + "=" * 60 + "\n"

    # ── public retrieval API ──────────────────────────────────────────────────

    def retrieve_all(self, query: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Single-query retrieval — returns (context_str, raw_results)."""
        try:
            print(f"[RAG.retrieve_all] START — query='{query[:60]}'")
            filtered = self._search(query)
            if not filtered:
                print("[RAG.retrieve_all] No results passed score threshold → fallback")
                return self._get_fallback_message(), []
            context = self._format_context(filtered)
            print(f"[RAG.retrieve_all] OK — {len(filtered)} sources, context_len={len(context)}")
            return context, filtered
        except Exception as e:
            print(f"[RAG.retrieve_all] ERROR: {e}")
            return self._get_fallback_message(), []

    def retrieve_context(self, query: str) -> str:
        context, _ = self.retrieve_all(query)
        return context

    def retrieve_raw(self, query: str) -> List[Dict[str, Any]]:
        _, raw = self.retrieve_all(query)
        return raw

    def retrieve_balanced(
        self,
        query: str,
        yaml_k: int | None = None,
        pdf_k: int | None = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Retrieves chunks from yaml_rule and cis_benchmark sources separately
        (balanced), then optionally applies hybrid scoring + MMR.

        Args:
            query:  User question.
            yaml_k: Chunks from YAML rules (default: self.top_k).
            pdf_k:  Chunks from PDF benchmarks (default: self.top_k).

        Returns:
            (context_str, raw_results) — sorted by relevance.
        """
        yaml_k = yaml_k if yaml_k is not None else self.top_k
        pdf_k = pdf_k if pdf_k is not None else self.top_k

        try:
            print(f"[RAG.retrieve_balanced] START — query='{query[:60]}' yaml_k={yaml_k} pdf_k={pdf_k}")
            query_emb = self._embed_client.embed_query(query)

            yaml_results = self._search_with_emb(query_emb, top_k=yaml_k, doc_type="yaml_rule")
            pdf_results = self._search_with_emb(query_emb, top_k=pdf_k, doc_type="cis_benchmark")

            print(f"[RAG.retrieve_balanced] yaml={len(yaml_results)} chunks, pdf={len(pdf_results)} chunks")

            combined = sorted(
                yaml_results + pdf_results,
                key=lambda r: r.get("score", 0.0),
                reverse=True,
            )

            if not combined:
                print("[RAG.retrieve_balanced] No results → fallback")
                return self._get_fallback_message(), []

            # Refinement loop: düşük skor → otomatik yeniden retrieval
            combined = self._refinement_retrieve(query, combined)

            if not combined:
                return self._get_fallback_message(), []

            # Enhanced: hybrid + MMR
            final_top_n = yaml_k + pdf_k
            combined = self._apply_hybrid_and_mmr(query, combined, final_top_n)

            context = self._format_context(combined)
            print(f"[RAG.retrieve_balanced] OK — {len(combined)} total sources, context_len={len(context)}")
            return context, combined

        except Exception as e:
            print(f"[RAG.retrieve_balanced] ERROR: {e}")
            return self._get_fallback_message(), []

    def retrieve_multi(
        self,
        queries: List[str],
        original_query: str,
        yaml_k: int | None = None,
        pdf_k: int | None = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Fan-out retrieval over multiple queries (from QueryPlanner), then
        deduplicate by chunk-id (keeping best score), apply hybrid + MMR.

        Queries are embedded and searched in parallel via ThreadPoolExecutor
        (IO-bound: each query = 1 embed API call + 2 Qdrant searches).

        Args:
            queries:        All queries (original + subqueries + HyDE + stepback).
            original_query: The unmodified user question (used for BM25/MMR scoring).
            yaml_k:         Chunks per query per source (default: self.top_k).
            pdf_k:          Chunks per query per source (default: self.top_k).

        Returns:
            (context_str, raw_results) — deduplicated, scored, ranked.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        yaml_k = yaml_k if yaml_k is not None else self.top_k
        pdf_k = pdf_k if pdf_k is not None else self.top_k

        def _retrieve_single(q: str) -> List[Dict[str, Any]]:
            q_emb = self._embed_client.embed_query(q)
            return (
                self._search_with_emb(q_emb, top_k=yaml_k, doc_type="yaml_rule")
                + self._search_with_emb(q_emb, top_k=pdf_k, doc_type="cis_benchmark")
            )

        try:
            print(f"[RAG.retrieve_multi] START — {len(queries)} queries parallel, original='{original_query[:50]}'")

            best: Dict[str, Dict[str, Any]] = {}
            max_workers = min(len(queries), 4)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_retrieve_single, q): q for q in queries}
                for future in as_completed(futures):
                    try:
                        for hit in future.result():
                            cid = str(hit.get("id", ""))
                            if cid not in best or hit.get("score", 0.0) > best[cid].get("score", 0.0):
                                best[cid] = hit
                    except Exception as exc:
                        _logger.warning("[retrieve_multi] query failed ('%s'): %s", futures[future][:40], exc)

            combined = list(best.values())
            print(f"[RAG.retrieve_multi] {len(combined)} unique chunks after parallel dedup")

            if not combined:
                print("[RAG.retrieve_multi] No results → fallback")
                return self._get_fallback_message(), []

            # Refinement loop
            combined = self._refinement_retrieve(original_query, combined)

            if not combined:
                return self._get_fallback_message(), []

            # Enhanced: hybrid + MMR (scored against the ORIGINAL query)
            final_top_n = (yaml_k + pdf_k) * 2
            combined = self._apply_hybrid_and_mmr(original_query, combined, final_top_n)

            context = self._format_context(combined)
            print(f"[RAG.retrieve_multi] OK — {len(combined)} final chunks, context_len={len(context)}")
            return context, combined

        except Exception as exc:
            print(f"[RAG.retrieve_multi] ERROR: {exc}")
            return self._get_fallback_message(), []

    def _get_fallback_message(self) -> str:
        return (
            "\n[NOT: İlgili CIS benchmark dokümanı bulunamadı. "
            "Genel bilgilerle cevap verilecek.]\n"
        )


# Singleton instance
_rag_builder: RAGContextBuilder | None = None


def get_rag_context_builder(
    top_k: int = 5,
    min_score: float = 0.7,
) -> RAGContextBuilder:
    """Global RAGContextBuilder instance (singleton)."""
    global _rag_builder

    if _rag_builder is None:
        _rag_builder = RAGContextBuilder(top_k=top_k, min_score=min_score)

    return _rag_builder
