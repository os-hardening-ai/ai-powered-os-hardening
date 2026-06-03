# api/metrics.py
"""
Performance Monitoring and Metrics Collection

Tracks:
- Request latency (p50, p95, p99)
- Request count
- Error rate
- Token usage
- LLM provider stats
"""

from __future__ import annotations

import time
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict, deque

from starlette.types import ASGIApp, Scope, Receive, Send, Message


# ─────────────────────────────────────────────
# Metrics Data Structures
# ─────────────────────────────────────────────

@dataclass
class RequestMetrics:
    """Metrics for a single request"""
    timestamp: datetime
    endpoint: str
    method: str
    status_code: int
    duration_ms: float
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    tokens_used: int = 0
    error: Optional[str] = None


@dataclass
class AggregatedMetrics:
    """Aggregated metrics over a time window"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_rate: float = 0.0

    # Latency statistics (milliseconds)
    avg_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    # Token statistics
    total_tokens: int = 0
    avg_tokens_per_request: float = 0.0

    # Provider breakdown
    provider_stats: Dict[str, int] = field(default_factory=dict)
    model_stats: Dict[str, int] = field(default_factory=dict)


# ─────────────────────────────────────────────
# Metrics Collector
# ─────────────────────────────────────────────

class MetricsCollector:
    """
    In-memory metrics collector.

    Stores metrics with a rolling window to prevent memory growth.
    """

    def __init__(self, max_history_hours: int = 24):
        """
        Args:
            max_history_hours: How many hours of metrics to keep in memory
        """
        self.max_history_hours = max_history_hours
        self.metrics: deque[RequestMetrics] = deque()

        # Endpoint-specific metrics
        self.endpoint_metrics: Dict[str, deque[RequestMetrics]] = defaultdict(deque)

    def record(self, metric: RequestMetrics) -> None:
        """Record a new metric"""
        # Add to global metrics
        self.metrics.append(metric)

        # Add to endpoint-specific metrics
        self.endpoint_metrics[metric.endpoint].append(metric)

        # Clean old metrics
        self._cleanup_old_metrics()

    def _cleanup_old_metrics(self) -> None:
        """Remove metrics older than max_history_hours"""
        cutoff = datetime.now() - timedelta(hours=self.max_history_hours)

        # Clean global metrics
        while self.metrics and self.metrics[0].timestamp < cutoff:
            self.metrics.popleft()

        # Clean endpoint-specific metrics
        for endpoint, metrics in self.endpoint_metrics.items():
            while metrics and metrics[0].timestamp < cutoff:
                metrics.popleft()

    def get_aggregated_metrics(
        self,
        endpoint: Optional[str] = None,
        time_window_minutes: Optional[int] = None
    ) -> AggregatedMetrics:
        """
        Get aggregated metrics.

        Args:
            endpoint: Filter by specific endpoint (None = all endpoints)
            time_window_minutes: Only include last N minutes (None = all time)

        Returns:
            Aggregated metrics
        """
        # Select metrics to aggregate
        if endpoint:
            metrics_list = list(self.endpoint_metrics.get(endpoint, []))
        else:
            metrics_list = list(self.metrics)

        # Filter by time window
        if time_window_minutes:
            cutoff = datetime.now() - timedelta(minutes=time_window_minutes)
            metrics_list = [m for m in metrics_list if m.timestamp >= cutoff]

        if not metrics_list:
            return AggregatedMetrics()

        # Calculate statistics
        total_requests = len(metrics_list)
        successful_requests = sum(1 for m in metrics_list if 200 <= m.status_code < 300)
        failed_requests = total_requests - successful_requests
        error_rate = failed_requests / total_requests if total_requests > 0 else 0.0

        # Latency statistics
        latencies = [m.duration_ms for m in metrics_list]
        avg_latency = statistics.mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)

        # Percentiles
        sorted_latencies = sorted(latencies)
        p50 = self._percentile(sorted_latencies, 0.50)
        p95 = self._percentile(sorted_latencies, 0.95)
        p99 = self._percentile(sorted_latencies, 0.99)

        # Token statistics
        total_tokens = sum(m.tokens_used for m in metrics_list)
        avg_tokens = total_tokens / total_requests if total_requests > 0 else 0.0

        # Provider/model breakdown
        provider_stats: Dict[str, int] = defaultdict(int)
        model_stats: Dict[str, int] = defaultdict(int)

        for m in metrics_list:
            if m.llm_provider:
                provider_stats[m.llm_provider] += 1
            if m.llm_model:
                model_stats[m.llm_model] += 1

        return AggregatedMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            error_rate=error_rate,
            avg_latency_ms=avg_latency,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
            total_tokens=total_tokens,
            avg_tokens_per_request=avg_tokens,
            provider_stats=dict(provider_stats),
            model_stats=dict(model_stats),
        )

    @staticmethod
    def _percentile(sorted_data: List[float], percentile: float) -> float:
        """Calculate percentile from sorted data"""
        if not sorted_data:
            return 0.0

        index = int(len(sorted_data) * percentile)
        index = min(index, len(sorted_data) - 1)
        return sorted_data[index]

    def get_recent_errors(self, limit: int = 10) -> List[RequestMetrics]:
        """Get most recent error requests"""
        errors = [m for m in reversed(self.metrics) if m.error]
        return errors[:limit]

    def get_slowest_requests(self, limit: int = 10) -> List[RequestMetrics]:
        """Get slowest requests"""
        sorted_metrics = sorted(self.metrics, key=lambda m: m.duration_ms, reverse=True)
        return sorted_metrics[:limit]

    def get_endpoint_breakdown(self, time_window_minutes: Optional[int] = None) -> Dict[str, dict]:
        """Özellik-grubu (chat / agent / rules / rag / diğer) başına gecikme + sayı.
        'Agent vs normal chat' gecikme karşılaştırması için → endpoint path'i bucket'a eşlenir."""
        metrics_list = list(self.metrics)
        if time_window_minutes:
            cutoff = datetime.now() - timedelta(minutes=time_window_minutes)
            metrics_list = [m for m in metrics_list if m.timestamp >= cutoff]

        def bucket(ep: str) -> str:
            ep = ep or ""
            if ep.startswith("/api/chat"):
                return "chat"
            if ep.startswith("/api/agent"):
                return "agent"
            if ep.startswith("/api/rules") or ep.startswith("/api/artifacts"):
                return "rules"
            if ep.startswith("/rag"):
                return "rag"
            if ep.startswith("/v1"):
                return "openai_compat"
            return "other"

        groups: Dict[str, List[float]] = defaultdict(list)
        for m in metrics_list:
            groups[bucket(m.endpoint)].append(m.duration_ms)

        out: Dict[str, dict] = {}
        for g, lats in groups.items():
            s = sorted(lats)
            out[g] = {
                "count": len(s),
                "avg_ms": round(statistics.mean(s), 1),
                "p95_ms": round(self._percentile(s, 0.95), 1),
                "max_ms": round(max(s), 1),
            }
        return out


# ─────────────────────────────────────────────
# Global Metrics Instance
# ─────────────────────────────────────────────

metrics_collector = MetricsCollector(max_history_hours=24)


# ─────────────────────────────────────────────
# Middleware for Automatic Metrics Collection
# ─────────────────────────────────────────────

class MetricsMiddleware:
    """Collect request metrics without buffering streaming responses."""

    def __init__(self, app: ASGIApp, collector: Optional[MetricsCollector] = None) -> None:
        self.app = app
        self.collector = collector or metrics_collector

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        path = scope.get("path", "")
        method = scope.get("method", "")
        status: list[int] = [500]
        collector = self.collector

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status[0] = message.get("status", 500)
            elif message["type"] == "http.response.body" and not message.get("more_body", False):
                duration_ms = (time.time() - start_time) * 1000
                state = scope.get("state") or {}
                metric = RequestMetrics(
                    timestamp=datetime.now(),
                    endpoint=path,
                    method=method,
                    status_code=status[0],
                    duration_ms=duration_ms,
                    llm_provider=state.get("llm_provider"),
                    llm_model=state.get("llm_model"),
                    tokens_used=int(state.get("llm_tokens", 0)),
                    error=None if status[0] < 400 else f"HTTP {status[0]}",
                )
                collector.record(metric)
            await send(message)

        await self.app(scope, receive, send_wrapper)


# ─────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────

def format_metrics_summary(metrics: AggregatedMetrics) -> str:
    """Format metrics as a human-readable string"""
    return f"""
Performance Metrics Summary
{'='*60}
Total Requests:        {metrics.total_requests}
Successful:            {metrics.successful_requests} ({100 * (1-metrics.error_rate):.1f}%)
Failed:                {metrics.failed_requests} ({100 * metrics.error_rate:.1f}%)

Latency Statistics (ms):
  Average:             {metrics.avg_latency_ms:.1f}
  Min:                 {metrics.min_latency_ms:.1f}
  Max:                 {metrics.max_latency_ms:.1f}
  P50 (median):        {metrics.p50_latency_ms:.1f}
  P95:                 {metrics.p95_latency_ms:.1f}
  P99:                 {metrics.p99_latency_ms:.1f}

Token Usage:
  Total Tokens:        {metrics.total_tokens:,}
  Avg per Request:     {metrics.avg_tokens_per_request:.0f}

LLM Provider Breakdown:
{_format_dict(metrics.provider_stats)}

Model Usage:
{_format_dict(metrics.model_stats)}
{'='*60}
"""


def _format_dict(d: Dict[str, int]) -> str:
    """Format dictionary as indented lines"""
    if not d:
        return "  (no data)"
    return "\n".join(f"  {k}: {v}" for k, v in d.items())


