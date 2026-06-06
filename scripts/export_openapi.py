#!/usr/bin/env python3
"""OpenAPI şemasını dosyaya döker — Postman / Insomnia / SwaggerUI import için.

Kullanım:
    python scripts/export_openapi.py                 # → openapi.json
    python scripts/export_openapi.py docs/openapi.json

Postman'a aktarma: Import → File → openapi.json → koleksiyon otomatik üretilir.
Not: `main` import edildiği için uygulama env'i (LLM_PROVIDER + ilgili API key) gereklidir;
sunucuda .env mevcutken çalıştırın.
"""
import json
import sys

from main import app


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
    schema = app.openapi()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    info = schema.get("info", {})
    paths = len(schema.get("paths", {}))
    print(f"OpenAPI yazıldı: {out}  (başlık: {info.get('title')}, sürüm: {info.get('version')}, {paths} uç)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
