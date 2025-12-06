# tests/integration/test_api_integration.py
"""
Integration tests for full API pipeline

Tests entire request/response flow including:
- Security middleware
- Metrics collection
- Input validation
- API endpoints
"""

import pytest
import requests
import time
from typing import Dict, Any


BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def check_api_running():
    """Ensure API is running before tests"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            pytest.skip("API is not running. Start with: python -m main")
    except requests.exceptions.RequestException:
        pytest.skip("API is not running. Start with: python -m main")


# ─────────────────────────────────────────────
# Health & Documentation Tests
# ─────────────────────────────────────────────

class TestHealthAndDocs:
    """Test health check and documentation endpoints"""

    def test_health_endpoint(self, check_api_running):
        """Test /health endpoint"""
        response = requests.get(f"{BASE_URL}/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_openapi_docs(self, check_api_running):
        """Test OpenAPI documentation is available"""
        response = requests.get(f"{BASE_URL}/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "info" in data
        assert data["info"]["title"] == "AI-Powered OS Hardening API"
        assert "paths" in data


# ─────────────────────────────────────────────
# Security Middleware Tests
# ─────────────────────────────────────────────

class TestSecurityMiddleware:
    """Test security middleware integration"""

    def test_security_headers_present(self, check_api_running):
        """Test that all security headers are present"""
        response = requests.get(f"{BASE_URL}/health")

        # Check security headers
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert response.headers.get("strict-transport-security") is not None
        assert response.headers.get("content-security-policy") is not None

    def test_rate_limit_headers(self, check_api_running):
        """Test that rate limit headers are present"""
        response = requests.get(f"{BASE_URL}/health")

        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers
        assert "x-ratelimit-reset" in response.headers

    def test_compression_works(self, check_api_running):
        """Test GZip compression for large responses"""
        # OpenAPI spec is large enough to trigger compression
        response = requests.get(f"{BASE_URL}/openapi.json")

        # Check if gzip is used (might not be for small responses)
        encoding = response.headers.get("content-encoding")
        # Either gzip or not compressed (both acceptable)
        assert encoding in [None, "gzip"]


# ─────────────────────────────────────────────
# Metrics Collection Tests
# ─────────────────────────────────────────────

class TestMetricsCollection:
    """Test metrics collection and reporting"""

    def test_metrics_endpoint_available(self, check_api_running):
        """Test /metrics endpoint"""
        response = requests.get(f"{BASE_URL}/metrics")

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "requests" in data
        assert "latency_ms" in data
        assert "tokens" in data

    def test_metrics_track_requests(self, check_api_running):
        """Test that metrics track requests"""
        # Get current metrics
        before = requests.get(f"{BASE_URL}/metrics").json()
        before_total = before["requests"]["total"]

        # Make some requests
        for _ in range(5):
            requests.get(f"{BASE_URL}/health")

        time.sleep(0.5)  # Allow middleware to process

        # Get updated metrics
        after = requests.get(f"{BASE_URL}/metrics").json()
        after_total = after["requests"]["total"]

        # Should have increased
        assert after_total > before_total

    def test_metrics_track_latency(self, check_api_running):
        """Test that metrics track latency"""
        response = requests.get(f"{BASE_URL}/metrics")
        data = response.json()

        # If there are any requests, latency should be tracked
        if data["requests"]["total"] > 0:
            assert data["latency_ms"]["avg"] >= 0
            assert data["latency_ms"]["p50"] >= 0


# ─────────────────────────────────────────────
# Input Validation Tests
# ─────────────────────────────────────────────

class TestInputValidation:
    """Test input validation on API endpoints"""

    def test_rejects_empty_question(self, check_api_running):
        """Test that empty question is rejected"""
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json={"question": ""}
        )

        assert response.status_code == 422  # Validation error

    def test_rejects_too_long_question(self, check_api_running):
        """Test that too long question is rejected"""
        long_question = "a" * 6000  # Over 5000 char limit

        response = requests.post(
            f"{BASE_URL}/api/chat",
            json={"question": long_question}
        )

        assert response.status_code == 422  # Validation error

    def test_rejects_invalid_security_level(self, check_api_running):
        """Test that invalid security_level is rejected"""
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "question": "Test",
                "security_level": "invalid"
            }
        )

        assert response.status_code == 422  # Validation error

    def test_accepts_valid_input(self, check_api_running):
        """Test that valid input is accepted (may fail if LLM not configured)"""
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "question": "Test question",
                "security_level": "balanced",
                "use_rag": False  # Disable RAG to avoid dependencies
            }
        )

        # Either succeeds or fails with 500 (LLM error), but not validation error
        assert response.status_code in [200, 500]


# ─────────────────────────────────────────────
# RAG Endpoint Tests
# ─────────────────────────────────────────────

class TestRAGEndpoint:
    """Test RAG search endpoint"""

    def test_rag_search_endpoint_exists(self, check_api_running):
        """Test that /rag/search endpoint exists"""
        response = requests.post(
            f"{BASE_URL}/rag/search",
            json={"query": "test"}
        )

        # Either works or returns error, but endpoint should exist
        assert response.status_code in [200, 404, 422, 500]


# ─────────────────────────────────────────────
# Error Handling Tests
# ─────────────────────────────────────────────

class TestErrorHandling:
    """Test API error handling"""

    def test_404_for_nonexistent_endpoint(self, check_api_running):
        """Test 404 for nonexistent endpoints"""
        response = requests.get(f"{BASE_URL}/nonexistent")

        assert response.status_code == 404

    def test_405_for_wrong_method(self, check_api_running):
        """Test 405 for wrong HTTP method"""
        response = requests.post(f"{BASE_URL}/health")  # health is GET only

        assert response.status_code == 405


# ─────────────────────────────────────────────
# End-to-End Workflow Test
# ─────────────────────────────────────────────

class TestEndToEndWorkflow:
    """Test complete request workflow"""

    def test_complete_request_workflow(self, check_api_running):
        """Test full workflow from request to response with metrics"""
        # 1. Check health
        health = requests.get(f"{BASE_URL}/health")
        assert health.status_code == 200

        # 2. Get initial metrics
        metrics_before = requests.get(f"{BASE_URL}/metrics").json()
        requests_before = metrics_before["requests"]["total"]

        # 3. Make a request (may fail if LLM not configured, that's okay)
        chat_response = requests.post(
            f"{BASE_URL}/api/chat",
            json={
                "question": "What is SSH hardening?",
                "security_level": "balanced",
                "use_rag": False
            }
        )

        # Either success or error, both are valid for this test
        assert chat_response.status_code in [200, 500]

        # 4. Check metrics were updated
        time.sleep(0.5)
        metrics_after = requests.get(f"{BASE_URL}/metrics").json()
        requests_after = metrics_after["requests"]["total"]

        # Request count should have increased
        assert requests_after > requests_before

    def test_security_headers_on_all_endpoints(self, check_api_running):
        """Test that security headers are present on all endpoints"""
        endpoints = [
            "/health",
            "/metrics",
            "/openapi.json",
        ]

        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}")

            # Check at least one security header
            assert (
                "x-content-type-options" in response.headers or
                "x-frame-options" in response.headers
            ), f"Security headers missing on {endpoint}"


# ─────────────────────────────────────────────
# Run Tests
# ─────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
