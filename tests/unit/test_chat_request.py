"""
Unit Tests: Chat Request Schema
Tests for ChatRequest validation from api/router_chat.py
"""

import pytest
from pydantic import ValidationError
from api.router_chat import ChatRequest


class TestChatRequestValidation:
    """Test ChatRequest schema validation"""

    def test_minimal_valid_request(self):
        """Test minimal valid chat request"""
        req = ChatRequest(question="How to harden SSH?")
        assert req.question == "How to harden SSH?"
        assert req.security_level == "balanced"  # Default
        assert req.zt_maturity == "medium"  # Default
        assert req.use_rag is True  # Default
        assert req.rag_top_k == 5  # Default (2026-06: 3→5, recall/ablation gerekçesi)

    def test_empty_question_rejected(self):
        """Test empty question is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(question="")
        assert "at least 1 character" in str(exc_info.value)

    def test_question_too_long_rejected(self):
        """Test question >5000 chars is rejected"""
        with pytest.raises(ValidationError):
            ChatRequest(question="a" * 5001)

    def test_invalid_security_level(self):
        """Test invalid security_level"""
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(question="test", security_level="invalid")
        assert "pattern" in str(exc_info.value).lower()

    def test_valid_security_levels(self):
        """Test all valid security levels"""
        for level in ["minimal", "balanced", "strict"]:
            req = ChatRequest(question="test", security_level=level)
            assert req.security_level == level

    def test_invalid_zt_maturity(self):
        """Test invalid zt_maturity"""
        with pytest.raises(ValidationError):
            ChatRequest(question="test", zt_maturity="invalid")

    def test_valid_zt_maturity_levels(self):
        """Test all valid ZT maturity levels"""
        for level in ["low", "medium", "high"]:
            req = ChatRequest(question="test", zt_maturity=level)
            assert req.zt_maturity == level

    def test_rag_top_k_validation(self):
        """Test rag_top_k range (1-20)"""
        ChatRequest(question="test", rag_top_k=1)  # Min
        ChatRequest(question="test", rag_top_k=20)  # Max

        with pytest.raises(ValidationError):
            ChatRequest(question="test", rag_top_k=0)
        with pytest.raises(ValidationError):
            ChatRequest(question="test", rag_top_k=21)

    def test_rag_min_score_validation(self):
        """Test rag_min_score range (0.0-1.0)"""
        ChatRequest(question="test", rag_min_score=0.0)  # Min
        ChatRequest(question="test", rag_min_score=1.0)  # Max

        with pytest.raises(ValidationError):
            ChatRequest(question="test", rag_min_score=-0.1)
        with pytest.raises(ValidationError):
            ChatRequest(question="test", rag_min_score=1.1)

    def test_timeout_validation(self):
        """Test timeout range (1-300 seconds)"""
        ChatRequest(question="test", timeout=1)  # Min
        ChatRequest(question="test", timeout=300)  # Max

        with pytest.raises(ValidationError):
            ChatRequest(question="test", timeout=0)
        with pytest.raises(ValidationError):
            ChatRequest(question="test", timeout=301)
