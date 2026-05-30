"""
Unit Tests: API Schemas
Tests for Pydantic models and validation in api/schemas.py
"""

import pytest
from pydantic import ValidationError
from api.schemas import LateChunkingOptions, RagSearchRequest, RagSearchResponse, RagSearchResult


class TestLateChunkingOptions:
    """Test LateChunkingOptions schema"""

    def test_default_values(self):
        """Test default values are set correctly"""
        lc = LateChunkingOptions()
        assert lc.enabled is False  # late chunking is opt-in (disabled by default)
        assert lc.coarse_k_factor == 3
        assert lc.window_size == 3
        assert lc.stride == 1

    def test_custom_values(self):
        """Test custom values are accepted"""
        lc = LateChunkingOptions(
            enabled=False,
            coarse_k_factor=5,
            window_size=5,
            stride=2
        )
        assert lc.enabled is False
        assert lc.coarse_k_factor == 5
        assert lc.window_size == 5
        assert lc.stride == 2

    def test_coarse_k_factor_validation(self):
        """Test coarse_k_factor range validation"""
        # Valid range: 1-10
        LateChunkingOptions(coarse_k_factor=1)  # Min
        LateChunkingOptions(coarse_k_factor=10)  # Max

        # Invalid: too low
        with pytest.raises(ValidationError):
            LateChunkingOptions(coarse_k_factor=0)

        # Invalid: too high
        with pytest.raises(ValidationError):
            LateChunkingOptions(coarse_k_factor=11)

    def test_window_size_validation(self):
        """Test window_size range validation"""
        # Valid range: 1-10
        LateChunkingOptions(window_size=1)  # Min
        LateChunkingOptions(window_size=10)  # Max

        # Invalid
        with pytest.raises(ValidationError):
            LateChunkingOptions(window_size=0)
        with pytest.raises(ValidationError):
            LateChunkingOptions(window_size=11)

    def test_stride_validation(self):
        """Test stride range validation"""
        # Valid range: 1-10
        LateChunkingOptions(stride=1)  # Min
        LateChunkingOptions(stride=10)  # Max

        # Invalid
        with pytest.raises(ValidationError):
            LateChunkingOptions(stride=0)


class TestRagSearchRequest:
    """Test RagSearchRequest schema"""

    def test_minimal_valid_request(self):
        """Test minimal valid request"""
        req = RagSearchRequest(query="test query")
        assert req.query == "test query"
        assert req.top_k == 5  # Default
        assert req.source_id is None  # Default

    def test_full_request(self):
        """Test full request with all fields"""
        req = RagSearchRequest(
            query="firewall configuration",
            top_k=10,
            source_id="cis_ubuntu_24_04",
            late_chunking=LateChunkingOptions(enabled=True)
        )
        assert req.query == "firewall configuration"
        assert req.top_k == 10
        assert req.source_id == "cis_ubuntu_24_04"
        assert req.late_chunking.enabled is True

    def test_top_k_validation(self):
        """Test top_k range validation (1-20)"""
        RagSearchRequest(query="test", top_k=1)  # Min
        RagSearchRequest(query="test", top_k=20)  # Max

        # Invalid
        with pytest.raises(ValidationError):
            RagSearchRequest(query="test", top_k=0)
        with pytest.raises(ValidationError):
            RagSearchRequest(query="test", top_k=21)

    def test_empty_query_validation(self):
        """Test that empty query is rejected"""
        with pytest.raises(ValidationError):
            RagSearchRequest(query="")

    def test_missing_query_validation(self):
        """Test that missing query is rejected"""
        with pytest.raises(ValidationError):
            RagSearchRequest()


class TestRagSearchResult:
    """Test RagSearchResult schema"""

    def test_valid_result(self):
        """Test valid search result"""
        result = RagSearchResult(
            id="cis_ubuntu_24_04-p100-c0",
            score=0.85,
            text="SSH configuration...",
            metadata={"source": "CIS", "section": "5.2"}
        )
        assert result.id == "cis_ubuntu_24_04-p100-c0"
        assert result.score == 0.85
        assert "SSH" in result.text
        assert result.metadata["source"] == "CIS"

    def test_score_float_validation(self):
        """Test score is a float"""
        result = RagSearchResult(
            id="test",
            score=0.5,
            text="test",
            metadata={}
        )
        assert isinstance(result.score, float)


class TestRagSearchResponse:
    """Test RagSearchResponse schema"""

    def test_valid_response(self):
        """Test valid search response"""
        results = [
            RagSearchResult(
                id="res1",
                score=0.9,
                text="Result 1",
                metadata={}
            ),
            RagSearchResult(
                id="res2",
                score=0.8,
                text="Result 2",
                metadata={}
            )
        ]
        response = RagSearchResponse(
            query="test query",
            top_k_per_source=5,
            total_returned=2,
            yaml_count=1,
            pdf_count=1,
            results=results,
        )
        assert response.query == "test query"
        assert response.top_k_per_source == 5
        assert response.total_returned == 2
        assert len(response.results) == 2
        assert response.results[0].score == 0.9

    def test_empty_results(self):
        """Test response with empty results"""
        response = RagSearchResponse(
            query="no matches",
            top_k_per_source=5,
            total_returned=0,
            yaml_count=0,
            pdf_count=0,
            results=[],
        )
        assert len(response.results) == 0
