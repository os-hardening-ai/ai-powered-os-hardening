#!/usr/bin/env python
"""
Build RAG Index - Config-driven

config/config.json'daki tüm enabled source_documents'ları sırayla indeksler.
Mantık IndexPipeline tarafından yönetilir.
"""

from __future__ import annotations
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.config_loader import get_config
from rag.indexing import IndexPipeline


def main() -> None:
    config = get_config()
    pipeline = IndexPipeline()

    print("\n" + "=" * 60)
    print("Building RAG Index")
    print("=" * 60)

    enabled = [s for s in config.rag.source_documents if s.enabled]
    skipped = [s for s in config.rag.source_documents if not s.enabled]

    for s in skipped:
        print(f"  [skip] {s.id}  (disabled in config)")

    for doc in enabled:
        print(f"\n  [run]  {doc.id}")
        print(f"         {doc.path}")
        stats = pipeline.run_for_source(doc.id)
        print(f"         chunks={stats.num_chunks}  "
              f"embed={stats.embed_time_sec:.1f}s  "
              f"upsert={stats.upsert_time_sec:.1f}s")

    print("\n" + "=" * 60)
    print(f"Done. {len(enabled)} source(s) indexed.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
