# utils/monitoring.py
"""
Structured Logging & Monitoring System

LLM Production Best Practices:
- Structured JSON logging
- Trace ID tracking
- Metrics collection
- Performance monitoring

References:
- LLM Evaluation Framework: https://www.datadoghq.com/blog/llm-evaluation-framework-best-practices/
- Datadog Observability: https://www.datadoghq.com/blog/llm-observability/
"""

from __future__ import annotations
import logging
import json
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict, field
from pathlib import Path


@dataclass
class RequestTrace:
    """Single request trace/span"""
    trace_id: str
    user_question: str
    intent: Optional[str] = None
    complexity: Optional[str] = None
    path: Optional[str] = None  # fast/simple/medium/complex
    provider: Optional[str] = None
    model: Optional[str] = None
    response_length: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    validation_passed: bool = True
    quality_score: float = 100.0
    fallback_count: int = 0
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class StructuredLogger:
    """
    Production-grade structured logging system.

    Features:
    - JSON formatted logs
    - Trace ID tracking
    - Multiple log levels
    - File + console output
    - Metrics aggregation
    """

    def __init__(
        self,
        log_file: str = "logs/chatbot.log",
        metrics_file: str = "logs/metrics.jsonl",
        console_logging: bool = True,
        log_level: str = "INFO"
    ):
        """
        Args:
            log_file: Log dosyası yolu
            metrics_file: Metrics JSONL dosyası
            console_logging: Console'a da log yaz
            log_level: Log seviyesi (DEBUG, INFO, WARNING, ERROR)
        """
        self.metrics_file = Path(metrics_file)
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

        # Setup logging
        self.logger = logging.getLogger("CyberChatbot")
        self.logger.setLevel(getattr(logging, log_level.upper()))

        # Clear existing handlers
        self.logger.handlers = []

        # File handler (JSON format)
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(file_handler)

        # Console handler (human-readable)
        if console_logging:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(
                logging.Formatter('[%(levelname)s] %(message)s')
            )
            self.logger.addHandler(console_handler)

        # Metrics aggregation
        self.session_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_latency_ms": 0.0,
            "total_cost_usd": 0.0,
            "path_distribution": {
                "local": 0,
                "fast": 0,
                "simple": 0,
                "medium": 0,
                "complex": 0
            },
            "provider_distribution": {},
            "error_types": {},
            "session_start": datetime.now().isoformat()
        }

    def generate_trace_id(self) -> str:
        """Unique trace ID oluştur"""
        return f"trace_{uuid.uuid4().hex[:16]}"

    def log_request(self, trace: RequestTrace) -> None:
        """
        Request trace'i logla.

        Args:
            trace: RequestTrace object
        """
        # Update session metrics
        self._update_metrics(trace)

        # Log as JSON
        log_entry = {
            "timestamp": trace.timestamp,
            "trace_id": trace.trace_id,
            "event": "request",
            "question": trace.user_question[:100],  # Truncate
            "intent": trace.intent,
            "complexity": trace.complexity,
            "path": trace.path,
            "provider": trace.provider,
            "model": trace.model,
            "response_length": trace.response_length,
            "latency_ms": round(trace.latency_ms, 2),
            "cost_usd": round(trace.cost_usd, 6),
            "quality_score": round(trace.quality_score, 1),
            "validation_passed": trace.validation_passed,
            "fallback_count": trace.fallback_count,
            "error": trace.error,
            "warnings": trace.warnings
        }

        # Write to log file
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))

        # Write metrics to JSONL (for analysis)
        self._append_metrics(trace)

    def _update_metrics(self, trace: RequestTrace) -> None:
        """Update aggregated metrics"""
        self.session_metrics["total_requests"] += 1

        if trace.error:
            self.session_metrics["failed_requests"] += 1

            # Track error types
            error_type = trace.error.split(":")[0] if ":" in trace.error else trace.error
            self.session_metrics["error_types"][error_type] = \
                self.session_metrics["error_types"].get(error_type, 0) + 1
        else:
            self.session_metrics["successful_requests"] += 1

        self.session_metrics["total_latency_ms"] += trace.latency_ms
        self.session_metrics["total_cost_usd"] += trace.cost_usd

        # Path distribution
        if trace.path:
            self.session_metrics["path_distribution"][trace.path] = \
                self.session_metrics["path_distribution"].get(trace.path, 0) + 1

        # Provider distribution
        if trace.provider:
            self.session_metrics["provider_distribution"][trace.provider] = \
                self.session_metrics["provider_distribution"].get(trace.provider, 0) + 1

    def _append_metrics(self, trace: RequestTrace) -> None:
        """Append single metric to JSONL file"""
        with open(self.metrics_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(trace.to_dict(), ensure_ascii=False) + '\n')

    def get_session_summary(self) -> Dict[str, Any]:
        """Get current session metrics summary"""
        total_reqs = self.session_metrics["total_requests"]

        if total_reqs == 0:
            return self.session_metrics

        # Calculate averages
        avg_latency = self.session_metrics["total_latency_ms"] / total_reqs
        avg_cost = self.session_metrics["total_cost_usd"] / total_reqs
        success_rate = (self.session_metrics["successful_requests"] / total_reqs) * 100

        summary = {
            **self.session_metrics,
            "avg_latency_ms": round(avg_latency, 2),
            "avg_cost_usd": round(avg_cost, 6),
            "success_rate_pct": round(success_rate, 2),
            "session_end": datetime.now().isoformat()
        }

        return summary

    def log_summary(self) -> None:
        """Log session summary"""
        summary = self.get_session_summary()

        self.logger.info("\n" + "="*70)
        self.logger.info("SESSION SUMMARY")
        self.logger.info("="*70)
        self.logger.info(json.dumps(summary, indent=2, ensure_ascii=False))
        self.logger.info("="*70)

    def log_error(self, trace_id: str, error_msg: str, context: Dict[str, Any] = None) -> None:
        """
        Log error with context.

        Args:
            trace_id: Trace ID
            error_msg: Error message
            context: Additional context
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "trace_id": trace_id,
            "event": "error",
            "error": error_msg,
            "context": context or {}
        }

        self.logger.error(json.dumps(log_entry, ensure_ascii=False))


# Global logger instance
_logger: Optional[StructuredLogger] = None


def get_logger(
    log_file: str = "logs/chatbot.log",
    metrics_file: str = "logs/metrics.jsonl",
    console_logging: bool = True,
    log_level: str = "INFO"
) -> StructuredLogger:
    """
    Get or create global logger instance.

    Args:
        log_file: Log file path
        metrics_file: Metrics JSONL file path
        console_logging: Enable console output
        log_level: Logging level

    Returns:
        StructuredLogger instance
    """
    global _logger

    if _logger is None:
        _logger = StructuredLogger(
            log_file=log_file,
            metrics_file=metrics_file,
            console_logging=console_logging,
            log_level=log_level
        )

    return _logger


# ─────────────────────────────────────────────
# Performance Timer Context Manager
# ─────────────────────────────────────────────

class Timer:
    """Context manager for timing code blocks"""

    def __init__(self, name: str = "operation"):
        self.name = name
        self.start_time = None
        self.elapsed_ms = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.time() - self.start_time) * 1000
