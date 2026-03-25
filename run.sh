#!/bin/bash
# Linux / macOS — kullanim: bash run.sh
set -e

if [ ! -f .env ]; then
  echo "Hata: .env dosyasi bulunamadi. Once calistir: cp .env.example .env"
  exit 1
fi

HASH_FILE=".requirements_hash"
REQ_FILE="requirements-python311.txt"
CURRENT_HASH=$(md5sum "$REQ_FILE" | cut -d' ' -f1)

if [ -f "$HASH_FILE" ] && [ "$(cat $HASH_FILE)" = "$CURRENT_HASH" ]; then
  echo "[requirements ayni] Sadece kod katmani yeniden build edilecek (~10s)..."
else
  echo "[requirements degisti] Container ve dangling image'lar temizleniyor..."
  docker compose down 2>/dev/null || true
  docker image prune -f
  echo "Image yeniden build ediliyor (pip yeniden kurulacak)..."
  echo "$CURRENT_HASH" > "$HASH_FILE"
fi

docker compose up --build -d

echo ""
echo "API  -> http://localhost:8000"
echo "Docs -> http://localhost:8000/docs"
echo ""
echo "Loglar : docker compose logs -f"
echo "Durdur : docker compose down"
