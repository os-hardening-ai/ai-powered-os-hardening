"""
Unified Orchestrator - Tüm sistem bileşenlerini yönetir
Config-driven pattern kullanarak esneklik sağlar
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, List
import json
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.config_loader import get_config


class SystemOrchestrator:
    """Ana koordinatör - Tüm sistemin merkezi"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: Custom config dosyası yolu (optional)
        """
        self.config = get_config(config_path)
        self.logger = self._setup_logging()
        self._components: Dict[str, Any] = {}
        self.logger.info(f"🚀 System Orchestrator initialized - Env: {self.config.app.env}")

    def _setup_logging(self) -> logging.Logger:
        """Logging sistemini konfigüre et"""
        logger = logging.getLogger("orchestrator")
        level = getattr(logging, self.config.app.log_level, logging.INFO)
        logger.setLevel(level)

        # Console handler
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

    def get_rag_retriever(self):
        """RAG Retriever'ı lazy-load et"""
        if "rag_retriever" not in self._components:
            from rag.retrieval.rag_retriever import RAGRetriever
            self._components["rag_retriever"] = RAGRetriever()
            self.logger.info("✅ RAG Retriever loaded")
        return self._components["rag_retriever"]

    def get_llm_clients(self):
        """LLM clients'ı lazy-load et"""
        if "llm_clients" not in self._components:
            from llm.clients import get_llm_clients
            self._components["llm_clients"] = get_llm_clients()
            self.logger.info("✅ LLM Clients loaded")
        return self._components["llm_clients"]

    def get_embedding_client(self):
        """Embedding client'ını lazy-load et"""
        if "embedding_client" not in self._components:
            from rag.embeddings import get_embedding_client
            self._components["embedding_client"] = get_embedding_client()
            self.logger.info("✅ Embedding Client loaded")
        return self._components["embedding_client"]

    def get_vector_store(self):
        """Vector store'u lazy-load et"""
        if "vector_store" not in self._components:
            from rag.vector_store import get_vector_store
            self._components["vector_store"] = get_vector_store()
            self.logger.info("✅ Vector Store loaded")
        return self._components["vector_store"]

    def get_pipeline(self):
        """Secure pipeline'ı lazy-load et"""
        if "pipeline" not in self._components:
            from llm.pipelines.secure_v2 import SecurePipelineV2
            self._components["pipeline"] = SecurePipelineV2()
            self.logger.info("✅ Secure Pipeline loaded")
        return self._components["pipeline"]

    # ──────────────────────────────────────────────────
    # RAG İşlemleri
    # ──────────────────────────────────────────────────

    def search_rag(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        RAG arama yap
        
        Args:
            query: Arama sorgusu
            top_k: Sonuç sayısı (config'ten default)
            min_score: Minimum skor (config'ten default)
        
        Returns:
            Sonuç listesi
        """
        retriever = self.get_rag_retriever()
        
        # Config defaults'ı kullan
        top_k = top_k or self.config.rag.retrieval.top_k
        min_score = min_score or self.config.rag.retrieval.min_score
        
        self.logger.info(f"🔍 RAG Search: '{query}' (top_k={top_k}, min_score={min_score})")
        
        results = retriever.search(
            query=query,
            top_k=top_k,
            use_late_chunking=self.config.rag.late_chunking.enabled,
            coarse_k_factor=self.config.rag.late_chunking.coarse_k_factor,
            window_size=self.config.rag.late_chunking.window_size,
            stride=self.config.rag.late_chunking.stride,
            min_score=min_score,
        )
        
        self.logger.info(f"✅ Found {len(results)} results")
        return results

    # ──────────────────────────────────────────────────
    # LLM İşlemleri
    # ──────────────────────────────────────────────────

    def chat_with_rag(
        self,
        question: str,
        use_rag: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        RAG + LLM entegre chat
        
        Args:
            question: Kullanıcı sorusu
            use_rag: RAG kullan mı?
            context: Opsiyonel bağlam
        
        Returns:
            Yanıt
        """
        pipeline = self.get_pipeline()
        
        self.logger.info(f"💬 Chat: '{question}' (use_rag={use_rag})")
        
        response = pipeline.run(
            user_input=question,
            use_rag=use_rag,
            context=context,
        )
        
        self.logger.info(f"✅ Generated response ({len(response)} chars)")
        return response

    # ──────────────────────────────────────────────────
    # Sistem Sağlığı
    # ──────────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """Sistem sağlığını kontrol et"""
        health_status = {
            "status": "healthy",
            "components": {},
            "timestamp": str(Path.ctime(Path(__file__))),
        }

        # Config yükleniyor mu?
        health_status["components"]["config"] = {
            "status": "ok",
            "env": self.config.app.env,
        }

        # LLM provider'lar
        try:
            self.get_llm_clients()
            health_status["components"]["llm"] = {"status": "ok"}
        except Exception as e:
            health_status["components"]["llm"] = {"status": "error", "message": str(e)}
            health_status["status"] = "degraded"

        # Embedding
        try:
            self.get_embedding_client()
            health_status["components"]["embedding"] = {"status": "ok"}
        except Exception as e:
            health_status["components"]["embedding"] = {"status": "error", "message": str(e)}
            health_status["status"] = "degraded"

        # Vector Store
        try:
            self.get_vector_store()
            health_status["components"]["vector_store"] = {"status": "ok"}
        except Exception as e:
            health_status["components"]["vector_store"] = {"status": "error", "message": str(e)}
            health_status["status"] = "degraded"

        return health_status

    # ──────────────────────────────────────────────────
    # Utility Metodları
    # ──────────────────────────────────────────────────

    def get_config_dict(self) -> Dict[str, Any]:
        """Konfigürasyonu dict olarak döndür"""
        if hasattr(self.config, "model_dump"):
            return self.config.model_dump()
        return self.config.__dict__

    def print_status(self):
        """Sistem durumunu yazdır"""
        health = self.health_check()
        print("\n" + "=" * 60)
        print("🛡️  AI-Powered OS Hardening - System Status")
        print("=" * 60)
        print(f"Environment: {self.config.app.env}")
        print(f"Status: {health['status'].upper()}")
        print("\nComponents:")
        for name, comp_status in health.get("components", {}).items():
            status_icon = "✅" if comp_status["status"] == "ok" else "❌"
            print(f"  {status_icon} {name}: {comp_status['status']}")
        print("=" * 60 + "\n")


# Singleton instance
_orchestrator: Optional[SystemOrchestrator] = None


def get_orchestrator(config_path: Optional[str] = None) -> SystemOrchestrator:
    """Orchestrator singleton'ını al"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SystemOrchestrator(config_path)
    return _orchestrator
