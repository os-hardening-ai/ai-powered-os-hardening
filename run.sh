#!/bin/bash
# Linux / macOS — kullanım: bash run.sh
set -e

if [ ! -f .env ]; then
  echo "Hata: .env dosyası bulunamadı. Önce çalıştır: cp .env.example .env"
  exit 1
fi

echo "Docker image build ediliyor ve container başlatılıyor..."
docker compose up --build -d

echo ""
echo "API ayağa kalktı → http://localhost:8000"
echo "Swagger UI       → http://localhost:8000/docs"
echo "Health           → http://localhost:8000/health"
echo ""
echo "Loglar icin: docker compose logs -f"
echo "Durdurmak icin:  docker compose down"
