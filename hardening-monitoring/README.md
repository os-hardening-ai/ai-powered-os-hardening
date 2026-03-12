# hardening-monitoring

**AI-Powered OS Hardening — Observability Stack**

OpenTelemetry + Prometheus + Grafana monitoring infrastructure for the [ai-powered-os-hardening](https://github.com/os-hardening-ai/ai-powered-os-hardening) backend.

---

## Stack

| Component | Version | Port | Purpose |
|-----------|---------|------|---------|
| **Prometheus** | v2.53 | 9090 | Metrics scraping & storage |
| **Grafana** | 11.2 | 3000 | Visualization & dashboards |
| **OTel Collector** | 0.112 | 4317/4318 | Trace/metric collection |

---

## Quick Start

### 1. Prerequisites
- Docker & Docker Compose installed
- Backend running at `localhost:8000`

### 2. Start the monitoring stack

```bash
git clone https://github.com/os-hardening-ai/hardening-monitoring
cd hardening-monitoring
docker compose up -d
```

### 3. Access dashboards

| URL | Credentials |
|-----|-------------|
| Grafana: http://localhost:3000 | admin / hardening123 |
| Prometheus: http://localhost:9090 | — |

---

## Dashboards

### Overview Dashboard (`/d/hardening-overview`)
- HTTP Request Rate (req/s) — success vs errors
- Latency percentiles: P50 / P95 / P99
- Request distribution by endpoint
- Backend health status (UP/DOWN)

### RAG Performance (`/d/hardening-rag`)
- RAG usage rate (what % of queries use RAG)
- Intent distribution: greeting / info_request / action_request
- Query complexity: simple / medium / complex
- LLM model usage breakdown (Groq / OpenAI)
- Estimated cost over time

### Pipeline Layers (`/d/hardening-pipeline`)
- Layer 1 (Safety Check) average duration
- Layer 2 (Intent Detection) average duration
- Layer 3 routing breakdown (3A Pattern / 3B Info / 3C Action)
- Unsafe query rejection rate
- Safety category distribution (safe_defensive / unsafe_offensive / etc.)

---

## Backend Integration

The backend must expose metrics at `/metrics/prometheus`. Add to the backend:

```bash
pip install prometheus-fastapi-instrumentator opentelemetry-sdk opentelemetry-instrumentation-fastapi
```

In `main.py`:
```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app, endpoint="/metrics/prometheus")
```

For OpenTelemetry traces (send to `localhost:4317`):
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=hardening-backend
```

---

## Configuration

Edit `prometheus/prometheus.yml` to change the backend scrape target:

```yaml
scrape_configs:
  - job_name: "hardening-backend"
    static_configs:
      - targets: ["host.docker.internal:8000"]   # Change this
    metrics_path: /metrics/prometheus
```

---

## Project Info

**Marmara Üniversitesi - Bilgisayar Mühendisliği Bitirme Projesi**
Geliştiriciler: Engin Çetintaş, Mert Baytaş, Tankut Arca Can
Danışman: Doç. Dr. Önder Demir
