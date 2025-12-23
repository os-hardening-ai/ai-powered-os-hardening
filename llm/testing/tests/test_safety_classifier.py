# tests/test_safety_classifier.py
"""
Unit tests for safety classifier module.

Run with:
    pytest tests/test_safety_classifier.py -v
"""

from __future__ import annotations

import pytest
from steps.safety_classifier import (
    _parse_safety_response,
    _build_safety_prompt,
    run_safety_classifier,
)
from context import RequestContext


class TestParseSafetyResponse:
    """Test suite for JSON parsing logic"""

    def test_valid_json(self):
        """Should parse valid JSON correctly"""
        raw = '{"category": "defensive_security", "reason": "SSH hardening request"}'
        result = _parse_safety_response(raw)

        assert result["category"] == "defensive_security"
        assert result["reason"] == "SSH hardening request"

    def test_markdown_wrapped_json(self):
        """Should handle JSON wrapped in markdown code blocks"""
        raw = '''```json
        {
            "category": "offensive_illegal",
            "reason": "Requesting attack steps"
        }
        ```'''
        result = _parse_safety_response(raw)

        assert result["category"] == "offensive_illegal"
        assert "attack" in result["reason"].lower()

    def test_invalid_json_fallback(self):
        """Should return safe defaults on invalid JSON"""
        raw = "This is not JSON at all"
        result = _parse_safety_response(raw)

        assert result["category"] == "generic_it"
        assert result["reason"] is None

    def test_missing_category_field(self):
        """Should use default category if missing"""
        raw = '{"reason": "Some reason"}'
        result = _parse_safety_response(raw)

        assert result["category"] == "generic_it"

    def test_empty_json(self):
        """Should handle empty JSON object"""
        raw = '{}'
        result = _parse_safety_response(raw)

        assert result["category"] == "generic_it"

    def test_whitespace_handling(self):
        """Should handle extra whitespace in JSON"""
        raw = '''

        {
            "category"  :  "defensive_security"  ,
            "reason"    :  "Test"
        }

        '''
        result = _parse_safety_response(raw)

        assert result["category"] == "defensive_security"


class TestBuildSafetyPrompt:
    """Test suite for prompt generation"""

    def test_prompt_contains_user_question(self):
        """Prompt should include the user's question"""
        ctx = RequestContext(user_question="How to secure SSH?")
        prompt = _build_safety_prompt(ctx)

        assert "How to secure SSH?" in prompt

    def test_prompt_contains_categories(self):
        """Prompt should list all safety categories"""
        ctx = RequestContext(user_question="Test")
        prompt = _build_safety_prompt(ctx)

        assert "defensive_security" in prompt
        assert "offensive_illegal" in prompt
        assert "generic_it" in prompt
        assert "ambiguous" in prompt


class TestRunSafetyClassifier:
    """Integration tests for the full classifier"""

    @pytest.fixture
    def mock_llm_defensive(self):
        """Mock LLM that always returns defensive_security"""
        def llm(prompt: str) -> str:
            return '{"category": "defensive_security", "reason": "Hardening request"}'
        return llm

    @pytest.fixture
    def mock_llm_offensive(self):
        """Mock LLM that always returns offensive_illegal"""
        def llm(prompt: str) -> str:
            return '{"category": "offensive_illegal", "reason": "Attack request"}'
        return llm

    @pytest.fixture
    def mock_llm_invalid(self):
        """Mock LLM that returns invalid response"""
        def llm(prompt: str) -> str:
            return "Invalid response"
        return llm

    def test_defensive_classification(self, mock_llm_defensive):
        """Should classify defensive requests correctly"""
        ctx = RequestContext(user_question="SSH hardening önerileri")

        result_ctx = run_safety_classifier(mock_llm_defensive, ctx)

        assert result_ctx.safety is not None
        assert result_ctx.safety.category == "defensive_security"
        assert result_ctx.final_answer is None  # Should not set final_answer

    def test_offensive_classification(self, mock_llm_offensive):
        """Should detect offensive requests and set final_answer"""
        ctx = RequestContext(user_question="How to hack SSH?")

        result_ctx = run_safety_classifier(mock_llm_offensive, ctx)

        assert result_ctx.safety is not None
        assert result_ctx.safety.category == "offensive_illegal"
        assert result_ctx.final_answer is not None  # Should reject request
        assert "uygun değil" in result_ctx.final_answer.lower()

    def test_invalid_llm_response(self, mock_llm_invalid):
        """Should handle invalid LLM responses gracefully"""
        ctx = RequestContext(user_question="Test question")

        result_ctx = run_safety_classifier(mock_llm_invalid, ctx)

        assert result_ctx.safety is not None
        assert result_ctx.safety.category == "generic_it"  # Default fallback

    def test_context_preservation(self, mock_llm_defensive):
        """Should preserve other context fields"""
        ctx = RequestContext(
            user_question="Test",
            os="ubuntu_22_04",
            role="sysadmin",
            security_level="strict",
        )

        result_ctx = run_safety_classifier(mock_llm_defensive, ctx)

        assert result_ctx.os == "ubuntu_22_04"
        assert result_ctx.role == "sysadmin"
        assert result_ctx.security_level == "strict"


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_very_long_question(self):
        """Should handle very long user questions"""
        long_question = "A" * 10000
        ctx = RequestContext(user_question=long_question)
        prompt = _build_safety_prompt(ctx)

        assert long_question in prompt

    def test_special_characters_in_question(self):
        """Should handle special characters in user input"""
        special_question = 'Test "quotes" and \'apostrophes\' and <html>'
        ctx = RequestContext(user_question=special_question)
        prompt = _build_safety_prompt(ctx)

        assert special_question in prompt

    def test_unicode_characters(self):
        """Should handle unicode characters"""
        unicode_question = "SSH güvenliğini artır 🔒"
        ctx = RequestContext(user_question=unicode_question)

        result = _parse_safety_response(
            '{"category": "defensive_security", "reason": "Güvenlik"}'
        )

        assert result["category"] == "defensive_security"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
