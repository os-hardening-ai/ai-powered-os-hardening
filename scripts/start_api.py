#!/usr/bin/env python
"""
Start API Server - Config-driven
Tüm yapılandırma config.json'dan yüklenir
"""

from __future__ import annotations
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import uvicorn
from config.config_loader import get_config
from main import create_app


def main():
    """API sunucusunu başlat"""
    config = get_config()
    
    print("\n" + "=" * 60)
    print("🚀 Starting AI-Powered OS Hardening API")
    print("=" * 60)
    print(f"App: {config.app.name} v{config.app.version}")
    print(f"Environment: {config.app.env}")
    print(f"Host: {config.api.host}")
    print(f"Port: {config.api.port}")
    print(f"Debug: {config.app.debug}")
    print(f"RAG: {'Enabled' if config.rag.enabled else 'Disabled'}")
    print(f"LLM Provider: {config.llm.default_provider}")
    print("=" * 60 + "\n")
    
    # App'ı oluştur
    app = create_app()
    
    # Sunucuyu başlat
    uvicorn.run(
        app,
        host=config.api.host,
        port=config.api.port,
        log_level=config.app.log_level.lower(),
    )


if __name__ == "__main__":
    main()
