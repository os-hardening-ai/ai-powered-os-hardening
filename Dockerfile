# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# libgomp1 — faiss-cpu için OpenMP desteği gerekli
# libgl1, libglib2.0-0 — PyMuPDF için gerekli
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Önce requirements'ı kopyala — requirements değişmediği sürece pip layer cache'den gelir
COPY requirements-python311.txt .
RUN pip install --no-cache-dir -r requirements-python311.txt

# Uygulama kodunu kopyala
COPY . .

# logs dizinini oluştur (volume mount edilmezse container içinde kullanılır)
RUN mkdir -p logs

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# --workers 1: session_store ve metrics_collector in-memory singleton — multi-worker'da tutarsızlık olur
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
