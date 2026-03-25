"""
Sadece belirtilen yeni kaynakları indeksler.
Mevcut kaynakları yeniden embed etmez.
"""
from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from rag.indexing import IndexPipeline

NEW_SOURCES = [
    "cis_windows_11_desktop",
    "windows_rules_yaml",
]


def main() -> None:
    pipeline = IndexPipeline()

    print("\n" + "=" * 60)
    print("Indexing New Sources")
    print("=" * 60)

    for source_id in NEW_SOURCES:
        print(f"\n  [run]  {source_id}")
        stats = pipeline.run_for_source(source_id)
        print(f"         chunks={stats.num_chunks}  "
              f"embed={stats.embed_time_sec:.1f}s  "
              f"upsert={stats.upsert_time_sec:.1f}s")

    print("\n" + "=" * 60)
    print(f"Done. {len(NEW_SOURCES)} source(s) indexed.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
