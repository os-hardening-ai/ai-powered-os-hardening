"""
Advanced Analytics Collector

Daha detaylı metrikler toplar:
- Query pattern analysis
- Cost breakdown per endpoint/user
- Intent distribution
- Error tracking with context
- Response quality metrics
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
import json


@dataclass
class QueryAnalytics:
    """Tek bir query için detaylı analytics"""
    timestamp: datetime
    query: str
    intent_type: str
    safety_category: str
    layer_path: str
    complexity: str
    rag_used: bool
    rag_chunks: int
    model_used: str
    response_time_s: float
    estimated_cost: float
    success: bool
    error_msg: Optional[str] = None
    user_id: Optional[str] = None  # Future: user tracking
    session_id: Optional[str] = None  # Future: session tracking


class AdvancedAnalyticsCollector:
    """
    Advanced analytics collection and aggregation

    Features:
    - Query pattern tracking
    - Cost attribution (per endpoint, intent, complexity)
    - Trend analysis
    - Performance degradation detection
    """

    def __init__(self, retention_hours: int = 24):
        """
        Args:
            retention_hours: How long to keep analytics data
        """
        self.retention_hours = retention_hours
        self.queries: List[QueryAnalytics] = []

        # Aggregated stats
        self.stats = {
            "total_queries": 0,
            "total_cost": 0.0,
            "total_time": 0.0,
            "intent_breakdown": defaultdict(int),
            "complexity_breakdown": defaultdict(int),
            "model_breakdown": defaultdict(int),
            "layer_path_breakdown": defaultdict(int),
            "rag_usage_count": 0,
            "error_count": 0,
        }

    def record_query(
        self,
        query: str,
        intent_type: str,
        safety_category: str,
        layer_path: str,
        complexity: str = "unknown",
        rag_used: bool = False,
        rag_chunks: int = 0,
        model_used: str = "unknown",
        response_time_s: float = 0.0,
        estimated_cost: float = 0.0,
        success: bool = True,
        error_msg: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Record a single query"""

        analytics = QueryAnalytics(
            timestamp=datetime.now(),
            query=query[:200],  # Truncate for privacy/storage
            intent_type=intent_type,
            safety_category=safety_category,
            layer_path=layer_path,
            complexity=complexity,
            rag_used=rag_used,
            rag_chunks=rag_chunks,
            model_used=model_used,
            response_time_s=response_time_s,
            estimated_cost=estimated_cost,
            success=success,
            error_msg=error_msg,
            user_id=user_id,
            session_id=session_id,
        )

        self.queries.append(analytics)

        # Update aggregated stats
        self.stats["total_queries"] += 1
        self.stats["total_cost"] += estimated_cost
        self.stats["total_time"] += response_time_s
        self.stats["intent_breakdown"][intent_type] += 1
        self.stats["complexity_breakdown"][complexity] += 1
        self.stats["model_breakdown"][model_used] += 1
        self.stats["layer_path_breakdown"][layer_path] += 1

        if rag_used:
            self.stats["rag_usage_count"] += 1

        if not success:
            self.stats["error_count"] += 1

        # Cleanup old data
        self._cleanup_old_data()

    def _cleanup_old_data(self):
        """Remove data older than retention period"""
        cutoff = datetime.now() - timedelta(hours=self.retention_hours)
        self.queries = [q for q in self.queries if q.timestamp > cutoff]

    def get_query_patterns(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Analyze common query patterns

        Returns:
            List of top N query patterns with frequency
        """
        # Group similar queries (simple keyword matching)
        pattern_counts = defaultdict(int)

        for q in self.queries:
            # Extract keywords (very simple approach)
            keywords = set(q.query.lower().split())
            # Remove common words
            keywords = keywords - {"nedir", "nasıl", "ne", "için", "bir", "bu", "the", "how", "what"}

            if keywords:
                pattern = " ".join(sorted(keywords)[:3])  # Top 3 keywords
                pattern_counts[pattern] += 1

        # Sort by frequency
        sorted_patterns = sorted(
            pattern_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

        return [
            {"pattern": pattern, "count": count}
            for pattern, count in sorted_patterns
        ]

    def get_cost_breakdown(self) -> Dict[str, Any]:
        """
        Cost attribution breakdown

        Returns:
            Cost breakdown by intent, complexity, model
        """
        cost_by_intent = defaultdict(float)
        cost_by_complexity = defaultdict(float)
        cost_by_model = defaultdict(float)
        cost_by_layer = defaultdict(float)

        for q in self.queries:
            cost_by_intent[q.intent_type] += q.estimated_cost
            cost_by_complexity[q.complexity] += q.estimated_cost
            cost_by_model[q.model_used] += q.estimated_cost
            cost_by_layer[q.layer_path] += q.estimated_cost

        return {
            "total_cost": self.stats["total_cost"],
            "by_intent": dict(cost_by_intent),
            "by_complexity": dict(cost_by_complexity),
            "by_model": dict(cost_by_model),
            "by_layer_path": dict(cost_by_layer),
            "avg_cost_per_query": (
                self.stats["total_cost"] / self.stats["total_queries"]
                if self.stats["total_queries"] > 0 else 0.0
            ),
        }

    def get_performance_trends(self, window_minutes: int = 60) -> Dict[str, Any]:
        """
        Performance trends over time

        Args:
            window_minutes: Time window for trend analysis

        Returns:
            Performance metrics over time
        """
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        recent_queries = [q for q in self.queries if q.timestamp > cutoff]

        if not recent_queries:
            return {
                "window_minutes": window_minutes,
                "query_count": 0,
                "avg_latency_ms": 0.0,
                "error_rate": 0.0,
            }

        total_time = sum(q.response_time_s for q in recent_queries)
        error_count = sum(1 for q in recent_queries if not q.success)

        return {
            "window_minutes": window_minutes,
            "query_count": len(recent_queries),
            "avg_latency_ms": (total_time / len(recent_queries)) * 1000,
            "error_rate": error_count / len(recent_queries),
            "queries_per_minute": len(recent_queries) / window_minutes,
        }

    def get_rag_effectiveness(self) -> Dict[str, Any]:
        """
        RAG usage effectiveness analysis

        Returns:
            RAG performance metrics
        """
        rag_queries = [q for q in self.queries if q.rag_used]
        non_rag_queries = [q for q in self.queries if not q.rag_used]

        if not rag_queries:
            return {
                "rag_usage_rate": 0.0,
                "avg_chunks_per_query": 0.0,
                "avg_latency_with_rag_ms": 0.0,
                "avg_latency_without_rag_ms": 0.0,
                "rag_overhead_ms": 0.0,
            }

        avg_rag_latency = (
            sum(q.response_time_s for q in rag_queries) / len(rag_queries) * 1000
        )

        avg_non_rag_latency = (
            sum(q.response_time_s for q in non_rag_queries) / len(non_rag_queries) * 1000
            if non_rag_queries else 0.0
        )

        return {
            "rag_usage_rate": len(rag_queries) / len(self.queries),
            "avg_chunks_per_query": sum(q.rag_chunks for q in rag_queries) / len(rag_queries),
            "avg_latency_with_rag_ms": avg_rag_latency,
            "avg_latency_without_rag_ms": avg_non_rag_latency,
            "rag_overhead_ms": avg_rag_latency - avg_non_rag_latency,
        }

    def get_error_analysis(self, limit: int = 10) -> Dict[str, Any]:
        """
        Error analysis and tracking

        Args:
            limit: Max number of recent errors to return

        Returns:
            Error breakdown and recent errors
        """
        errors = [q for q in self.queries if not q.success]

        if not errors:
            return {
                "total_errors": 0,
                "error_rate": 0.0,
                "recent_errors": [],
            }

        # Error type breakdown (by error message prefix)
        error_types = defaultdict(int)
        for e in errors:
            if e.error_msg:
                error_type = e.error_msg.split(":")[0][:50]  # First part of error
                error_types[error_type] += 1

        recent_errors = errors[-limit:]

        return {
            "total_errors": len(errors),
            "error_rate": len(errors) / len(self.queries),
            "error_types": dict(error_types),
            "recent_errors": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "query": e.query[:100],
                    "layer_path": e.layer_path,
                    "error": e.error_msg,
                }
                for e in recent_errors
            ],
        }

    def get_full_analytics(self) -> Dict[str, Any]:
        """
        Get comprehensive analytics report

        Returns:
            Complete analytics dashboard data
        """
        return {
            "overview": {
                "total_queries": self.stats["total_queries"],
                "total_cost_usd": round(self.stats["total_cost"], 4),
                "total_time_s": round(self.stats["total_time"], 2),
                "avg_latency_ms": (
                    (self.stats["total_time"] / self.stats["total_queries"]) * 1000
                    if self.stats["total_queries"] > 0 else 0.0
                ),
                "error_count": self.stats["error_count"],
                "error_rate": (
                    self.stats["error_count"] / self.stats["total_queries"]
                    if self.stats["total_queries"] > 0 else 0.0
                ),
            },
            "breakdown": {
                "by_intent": dict(self.stats["intent_breakdown"]),
                "by_complexity": dict(self.stats["complexity_breakdown"]),
                "by_model": dict(self.stats["model_breakdown"]),
                "by_layer_path": dict(self.stats["layer_path_breakdown"]),
            },
            "cost_analysis": self.get_cost_breakdown(),
            "rag_effectiveness": self.get_rag_effectiveness(),
            "query_patterns": self.get_query_patterns(),
            "performance_trends": {
                "last_1h": self.get_performance_trends(60),
                "last_24h": self.get_performance_trends(24 * 60),
            },
            "error_analysis": self.get_error_analysis(),
        }


# Global instance
_analytics_collector: Optional[AdvancedAnalyticsCollector] = None


def get_analytics_collector() -> AdvancedAnalyticsCollector:
    """Get global analytics collector instance"""
    global _analytics_collector
    if _analytics_collector is None:
        _analytics_collector = AdvancedAnalyticsCollector()
    return _analytics_collector
