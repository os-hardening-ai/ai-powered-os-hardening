"""
Advanced Analytics API Endpoints
"""

from fastapi import APIRouter, Query
import sys
import os

# Add parent to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from llm.utils.analytics_collector import get_analytics_collector

router = APIRouter()


@router.get("/analytics")
async def get_full_analytics():
    """
    Get comprehensive analytics dashboard

    Returns all analytics data including:
    - Query patterns
    - Cost breakdown
    - Performance trends
    - RAG effectiveness
    - Error analysis
    """
    collector = get_analytics_collector()
    return collector.get_full_analytics()


@router.get("/analytics/cost")
async def get_cost_breakdown():
    """Get detailed cost attribution by intent, complexity, model"""
    collector = get_analytics_collector()
    return collector.get_cost_breakdown()


@router.get("/analytics/patterns")
async def get_query_patterns(top_n: int = Query(default=10, le=50)):
    """Get top N common query patterns"""
    collector = get_analytics_collector()
    return {"patterns": collector.get_query_patterns(top_n=top_n)}


@router.get("/analytics/rag")
async def get_rag_effectiveness():
    """Get RAG usage and effectiveness metrics"""
    collector = get_analytics_collector()
    return collector.get_rag_effectiveness()


@router.get("/analytics/errors")
async def get_error_analysis(limit: int = Query(default=10, le=100)):
    """Get error analysis and recent errors"""
    collector = get_analytics_collector()
    return collector.get_error_analysis(limit=limit)


@router.get("/analytics/trends")
async def get_performance_trends(
    window_minutes: int = Query(default=60, le=1440)
):
    """Get performance trends for specified time window"""
    collector = get_analytics_collector()
    return collector.get_performance_trends(window_minutes=window_minutes)
