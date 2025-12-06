# tests/unit/test_metrics.py
"""
Unit tests for api/metrics.py module

Tests:
- MetricsCollector
- RequestMetrics
- Aggregated statistics
- Percentile calculations
"""

import pytest
import time
from datetime import datetime, timedelta
from api.metrics import (
    MetricsCollector,
    RequestMetrics,
    AggregatedMetrics,
    format_metrics_summary,
)


# ─────────────────────────────────────────────
# MetricsCollector Tests
# ─────────────────────────────────────────────

class TestMetricsCollector:
    """Test MetricsCollector class"""

    def test_records_metric(self):
        """Test that metrics are recorded correctly"""
        collector = MetricsCollector()

        metric = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/test",
            method="GET",
            status_code=200,
            duration_ms=100.0,
        )

        collector.record(metric)

        assert len(collector.metrics) == 1
        assert collector.metrics[0] == metric

    def test_aggregates_empty_metrics(self):
        """Test aggregation with no metrics"""
        collector = MetricsCollector()

        agg = collector.get_aggregated_metrics()

        assert agg.total_requests == 0
        assert agg.error_rate == 0.0

    def test_aggregates_successful_requests(self):
        """Test aggregation of successful requests"""
        collector = MetricsCollector()

        # Add 10 successful requests
        for i in range(10):
            metric = RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/test",
                method="GET",
                status_code=200,
                duration_ms=float(i * 10),
                tokens_used=100,
            )
            collector.record(metric)

        agg = collector.get_aggregated_metrics()

        assert agg.total_requests == 10
        assert agg.successful_requests == 10
        assert agg.failed_requests == 0
        assert agg.error_rate == 0.0

    def test_aggregates_failed_requests(self):
        """Test aggregation with failed requests"""
        collector = MetricsCollector()

        # Add 7 successful, 3 failed
        for i in range(7):
            collector.record(RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/test",
                method="GET",
                status_code=200,
                duration_ms=100.0,
            ))

        for i in range(3):
            collector.record(RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/test",
                method="GET",
                status_code=500,
                duration_ms=100.0,
                error="Internal error",
            ))

        agg = collector.get_aggregated_metrics()

        assert agg.total_requests == 10
        assert agg.successful_requests == 7
        assert agg.failed_requests == 3
        assert agg.error_rate == 0.3  # 30%

    def test_calculates_latency_stats(self):
        """Test latency statistics calculation"""
        collector = MetricsCollector()

        # Add requests with known latencies
        latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        for lat in latencies:
            collector.record(RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/test",
                method="GET",
                status_code=200,
                duration_ms=float(lat),
            ))

        agg = collector.get_aggregated_metrics()

        assert agg.avg_latency_ms == 55.0  # Mean of 10-100
        assert agg.min_latency_ms == 10.0
        assert agg.max_latency_ms == 100.0
        assert agg.p50_latency_ms == 50.0  # Median

    def test_calculates_token_stats(self):
        """Test token usage statistics"""
        collector = MetricsCollector()

        # Add requests with token usage
        for i in range(5):
            collector.record(RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/api/chat",
                method="POST",
                status_code=200,
                duration_ms=100.0,
                tokens_used=500,
                llm_provider="groq",
                llm_model="llama-3.1-8b-instant",
            ))

        agg = collector.get_aggregated_metrics()

        assert agg.total_tokens == 2500  # 5 * 500
        assert agg.avg_tokens_per_request == 500.0

    def test_provider_stats(self):
        """Test LLM provider breakdown"""
        collector = MetricsCollector()

        # Add requests with different providers
        for _ in range(3):
            collector.record(RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/api/chat",
                method="POST",
                status_code=200,
                duration_ms=100.0,
                llm_provider="groq",
            ))

        for _ in range(2):
            collector.record(RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/api/chat",
                method="POST",
                status_code=200,
                duration_ms=100.0,
                llm_provider="openai",
            ))

        agg = collector.get_aggregated_metrics()

        assert agg.provider_stats["groq"] == 3
        assert agg.provider_stats["openai"] == 2

    def test_filters_by_endpoint(self):
        """Test filtering metrics by endpoint"""
        collector = MetricsCollector()

        # Add metrics for different endpoints
        for _ in range(3):
            collector.record(RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/api/chat",
                method="POST",
                status_code=200,
                duration_ms=100.0,
            ))

        for _ in range(2):
            collector.record(RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/health",
                method="GET",
                status_code=200,
                duration_ms=10.0,
            ))

        # Get metrics for specific endpoint
        agg = collector.get_aggregated_metrics(endpoint="/api/chat")

        assert agg.total_requests == 3

    def test_filters_by_time_window(self):
        """Test filtering metrics by time window"""
        collector = MetricsCollector()

        # Add old metric (2 hours ago)
        old_metric = RequestMetrics(
            timestamp=datetime.now() - timedelta(hours=2),
            endpoint="/test",
            method="GET",
            status_code=200,
            duration_ms=100.0,
        )
        collector.record(old_metric)

        # Add recent metric
        recent_metric = RequestMetrics(
            timestamp=datetime.now(),
            endpoint="/test",
            method="GET",
            status_code=200,
            duration_ms=100.0,
        )
        collector.record(recent_metric)

        # Get metrics for last 60 minutes
        agg = collector.get_aggregated_metrics(time_window_minutes=60)

        assert agg.total_requests == 1  # Only recent metric

    def test_cleanup_old_metrics(self):
        """Test that old metrics are cleaned up"""
        collector = MetricsCollector(max_history_hours=1)

        # Add very old metric
        old_metric = RequestMetrics(
            timestamp=datetime.now() - timedelta(hours=2),
            endpoint="/test",
            method="GET",
            status_code=200,
            duration_ms=100.0,
        )
        collector.record(old_metric)

        # Force cleanup
        collector._cleanup_old_metrics()

        assert len(collector.metrics) == 0

    def test_get_recent_errors(self):
        """Test getting recent errors"""
        collector = MetricsCollector()

        # Add successful requests
        for _ in range(5):
            collector.record(RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/test",
                method="GET",
                status_code=200,
                duration_ms=100.0,
            ))

        # Add failed requests
        for i in range(3):
            collector.record(RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/test",
                method="GET",
                status_code=500,
                duration_ms=100.0,
                error=f"Error {i}",
            ))

        errors = collector.get_recent_errors(limit=10)

        assert len(errors) == 3
        assert all(e.error is not None for e in errors)

    def test_get_slowest_requests(self):
        """Test getting slowest requests"""
        collector = MetricsCollector()

        # Add requests with different latencies
        for i in range(10):
            collector.record(RequestMetrics(
                timestamp=datetime.now(),
                endpoint="/test",
                method="GET",
                status_code=200,
                duration_ms=float(i * 100),
            ))

        slowest = collector.get_slowest_requests(limit=3)

        assert len(slowest) == 3
        assert slowest[0].duration_ms == 900.0  # Slowest
        assert slowest[1].duration_ms == 800.0
        assert slowest[2].duration_ms == 700.0


# ─────────────────────────────────────────────
# Percentile Calculation Tests
# ─────────────────────────────────────────────

class TestPercentileCalculation:
    """Test percentile calculation logic"""

    def test_percentile_simple_case(self):
        """Test percentile with simple data"""
        collector = MetricsCollector()

        data = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

        p50 = collector._percentile(data, 0.50)
        p95 = collector._percentile(data, 0.95)
        p99 = collector._percentile(data, 0.99)

        assert p50 == 50  # 50th percentile
        assert p95 >= 90  # 95th percentile
        assert p99 >= 99  # 99th percentile

    def test_percentile_empty_data(self):
        """Test percentile with empty data"""
        collector = MetricsCollector()

        result = collector._percentile([], 0.95)

        assert result == 0.0


# ─────────────────────────────────────────────
# Format Tests
# ─────────────────────────────────────────────

class TestFormatting:
    """Test metric formatting"""

    def test_format_metrics_summary(self):
        """Test format_metrics_summary function"""
        metrics = AggregatedMetrics(
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            error_rate=0.05,
            avg_latency_ms=123.4,
            min_latency_ms=10.0,
            max_latency_ms=500.0,
            p50_latency_ms=100.0,
            p95_latency_ms=300.0,
            p99_latency_ms=450.0,
            total_tokens=50000,
            avg_tokens_per_request=500.0,
            provider_stats={"groq": 60, "openai": 40},
            model_stats={"llama-3.1-8b-instant": 60, "gpt-4o-mini": 40},
        )

        summary = format_metrics_summary(metrics)

        # Check that summary contains key information
        assert "Total Requests" in summary
        assert "100" in summary
        assert "Latency Statistics" in summary
        assert "groq" in summary
        assert "openai" in summary


# ─────────────────────────────────────────────
# Run Tests
# ─────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
