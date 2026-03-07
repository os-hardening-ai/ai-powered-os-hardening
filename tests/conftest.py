"""
Pytest Configuration and Shared Fixtures
AI-Powered OS Hardening Test Suite
"""

import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def app():
    """FastAPI application instance (session-scoped)"""
    from main import app
    return app


@pytest.fixture(scope="function")
def client(app) -> TestClient:
    """Test client for API testing"""
    with TestClient(app) as test_client:
        yield test_client


def pytest_configure(config):
    Path("tests/reports").mkdir(exist_ok=True, parents=True)


def pytest_collection_modifyitems(config, items):
    """Auto-assign markers based on test file path"""
    path_markers = {
        "unit": pytest.mark.unit,
        "integration": pytest.mark.integration,
        "blackbox": pytest.mark.blackbox,
        "whitebox": pytest.mark.whitebox,
        "e2e": pytest.mark.e2e,
        "performance": pytest.mark.performance,
    }
    node_markers = {
        "api": pytest.mark.api,
        "pipeline": pytest.mark.llm,
        "rag": pytest.mark.rag,
    }
    for item in items:
        path = str(item.fspath)
        for keyword, marker in path_markers.items():
            if keyword in path:
                item.add_marker(marker)
                break
        node = str(item.nodeid)
        for keyword, marker in node_markers.items():
            if keyword in path or keyword in node:
                item.add_marker(marker)


def pytest_report_header(config):
    return [
        "AI-Powered OS Hardening - Test Suite",
        "=" * 60,
    ]


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if exitstatus == 0:
        terminalreporter.write_sep("=", "ALL TESTS PASSED", green=True, bold=True)
    else:
        terminalreporter.write_sep("=", "SOME TESTS FAILED", red=True, bold=True)
