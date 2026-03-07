"""
CLI Interface - Komut satırı üzerinden sistem yönetimi
Config-driven pattern kullanarak esnek yapı sağlar
"""

from __future__ import annotations
import sys
import argparse
from pathlib import Path
from typing import Optional
import json

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.orchestrator import get_orchestrator


class CLIManager:
    """Komut satırı arayüzü"""

    def __init__(self):
        self.orchestrator = get_orchestrator()

    def cmd_rag_search(self, args):
        """RAG arama yap"""
        results = self.orchestrator.search_rag(
            query=args.query,
            top_k=args.top_k,
            min_score=args.min_score,
        )
        
        print(f"\n[RAG SEARCH] Results: {len(results)} found\n")
        for i, result in enumerate(results, 1):
            print(f"[{i}] Score: {result.get('score', 0):.3f}")
            print(f"    Text: {result.get('text', '')[:150]}...")
            print(f"    ID: {result.get('id', 'N/A')}\n")

    def cmd_chat(self, args):
        """Chat sorgusu"""
        response = self.orchestrator.chat_with_rag(
            question=args.question,
            use_rag=args.use_rag,
        )
        
        print(f"\n[RESPONSE]\n")
        print(response)
        print("\n")

    def cmd_health(self, args):
        """Sistem sağlığını kontrol et"""
        health = self.orchestrator.health_check()
        self.orchestrator.print_status()

    def cmd_config(self, args):
        """Konfigürasyonu göster"""
        config_dict = self.orchestrator.get_config_dict()
        print("\n[CONFIG] Current Configuration:\n")
        print(json.dumps(config_dict, indent=2))
        print("\n")

    def cmd_info(self, args):
        """Sistem bilgilerini göster"""
        config = self.orchestrator.config
        print("\n[INFO] System Information:\n")
        print(f"App Name: {config.app.name}")
        print(f"Version: {config.app.version}")
        print(f"Environment: {config.app.env}")
        print(f"Language: {config.app.language}")
        print(f"\nAPI: {config.api.host}:{config.api.port}")
        print(f"RAG Enabled: {config.rag.enabled}")
        print(f"LLM Provider: {config.llm.default_provider}")
        print("\n")

    def run(self):
        """CLI argümanlarını işle"""
        parser = argparse.ArgumentParser(
            description="AI-Powered OS Hardening - CLI Interface",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # RAG arama yap
  python -m src.cli rag "SSH hardening" --top-k 5 --min-score 0.3
  
  # Chat sorgusu
  python -m src.cli chat "Ubuntu 24.04'de SSH portu nasıl değiştirilir?"
  
  # Sistem sağlığını kontrol et
  python -m src.cli health
  
  # Konfigürasyonu göster
  python -m src.cli config
            """
        )

        subparsers = parser.add_subparsers(dest="command", help="Komutlar")

        # RAG search
        rag_parser = subparsers.add_parser("rag", help="RAG arama yap")
        rag_parser.add_argument("query", help="Arama sorgusu")
        rag_parser.add_argument("--top-k", type=int, default=5, help="Sonuç sayısı")
        rag_parser.add_argument("--min-score", type=float, default=0.3, help="Minimum skor")
        rag_parser.set_defaults(func=self.cmd_rag_search)

        # Chat
        chat_parser = subparsers.add_parser("chat", help="Chat sorgusu")
        chat_parser.add_argument("question", help="Soru")
        chat_parser.add_argument("--no-rag", action="store_true", help="RAG'i devre dışı bırak")
        chat_parser.set_defaults(func=lambda args: self.cmd_chat(
            type('Args', (), {'question': args.question, 'use_rag': not args.no_rag})()
        ))

        # Health check
        health_parser = subparsers.add_parser("health", help="Sistem sağlığını kontrol et")
        health_parser.set_defaults(func=self.cmd_health)

        # Config
        config_parser = subparsers.add_parser("config", help="Konfigürasyonu göster")
        config_parser.set_defaults(func=self.cmd_config)

        # Info
        info_parser = subparsers.add_parser("info", help="Sistem bilgileri")
        info_parser.set_defaults(func=self.cmd_info)

        # Argümanları parse et
        args = parser.parse_args()

        if not args.command:
            parser.print_help()
            return

        # Komutu çalıştır
        if hasattr(args, 'func'):
            try:
                args.func(args)
            except Exception as e:
                print(f"\n[ERROR] {e}\n")
