"""
Black-box Tests: API Endpoints
Functional testing without knowledge of internal implementation
"""

import pytest


@pytest.mark.blackbox
@pytest.mark.api
class TestHealthEndpoint:
    """Test /health endpoint"""

    def test_health_check_returns_ok(self, client):
        """Test health check returns status ok"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.blackbox
@pytest.mark.api
@pytest.mark.rag
class TestRagSearchEndpoint:
    """Test /rag/search endpoint"""

    def test_basic_search_returns_results(self, client):
        """Test basic RAG search returns results"""
        payload = {
            "query": "firewall configuration",
            "top_k": 3
        }
        response = client.post("/rag/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_search_returns_correct_number_of_results(self, client):
        """Test top_k parameter works"""
        payload = {"query": "SSH security", "top_k": 5}
        response = client.post("/rag/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 5  # May return fewer

    def test_search_rejects_empty_query(self, client):
        """Test empty query is rejected"""
        payload = {"query": "", "top_k": 3}
        response = client.post("/rag/search", json=payload)
        assert response.status_code == 422


@pytest.mark.blackbox
@pytest.mark.api
@pytest.mark.llm
class TestChatEndpoint:
    """Test /api/chat endpoint"""

    def test_chat_returns_answer(self, client):
        """Test chat endpoint returns an answer"""
        payload = {"question": "What is SSH?"}
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert len(data["answer"]) > 0

    def test_chat_detects_intent(self, client):
        """Test intent is detected"""
        payload = {"question": "Thank you"}
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "intent" in data
        assert data["intent"] is not None

    def test_chat_validates_security_level(self, client):
        """Test invalid security_level is rejected"""
        payload = {"question": "test", "security_level": "invalid"}
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 422


@pytest.mark.blackbox
@pytest.mark.api
class TestMetricsEndpoint:
    """Test /metrics endpoint"""

    def test_metrics_returns_stats(self, client):
        """Test metrics endpoint returns statistics"""
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "requests" in data
        assert "latency_ms" in data
