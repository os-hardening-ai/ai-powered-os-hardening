"""
API wiring tests for the agentic endpoints (/api/agent/plan, /api/agent/harden).

A minimal FastAPI app mounts only router_agent; the rule engine is backed by a
tmp YAML fixture and the LLM is disabled (deterministic). This validates the
HTTP contract without standing up the full application/services.
"""

from __future__ import annotations

import textwrap

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.router_agent as ra
from api.router_agent import router as agent_router
from api.errors import APIError, api_error_handler
from domain.rule_engine.rule_engine import RuleEngine

pytestmark = pytest.mark.integration


RULES_YAML = textwrap.dedent("""
rules:
  - id: "1.1.1"
    title: "Disable SSH root login"
    level: 1
    category: "ssh"
    zt_principle: "least_privilege"
    nist_ref: "AC-6"
    config_files: ["/etc/ssh/sshd_config"]
    remediation_script_content: "sed -i 's/^PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config"
  - id: "1.2.1"
    title: "Password minimum length"
    level: 1
    category: "password"
    remediation_script_content: "echo 'PASS_MIN_LEN 14' >> /etc/login.defs"
""").strip()


@pytest.fixture
def client(tmp_path, monkeypatch):
    p = tmp_path / "rules.yaml"
    p.write_text(RULES_YAML, encoding="utf-8")
    engine = RuleEngine(p)
    # Inject fixture engine + disable LLM (deterministic planning)
    monkeypatch.setattr(ra, "_get_rule_engine", lambda *a, **k: engine)
    monkeypatch.setattr(ra, "_get_small_llm", lambda: None)

    app = FastAPI()
    app.add_exception_handler(APIError, api_error_handler)
    app.include_router(agent_router, prefix="/api")
    # /agent/harden artık RBAC korumalı (require_role) → testte sysadmin'e override et.
    from api.auth import get_current_user
    from api.auth_models import AuthenticatedUser, Role
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser("test", Role.SYSADMIN)
    return TestClient(app)


class TestPlanEndpoint:
    def test_plan_returns_ordered_items(self, client):
        r = client.post("/api/agent/plan", json={
            "goal": "SSH ve parola sıkılaştır",
            "os_target": "ubuntu_24_04",
            "security_level": "balanced",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["goal"] == "SSH ve parola sıkılaştır"
        assert len(data["items"]) == 2
        assert [i["order"] for i in data["items"]] == [1, 2]
        assert data["items"][0]["rule_id"] == "1.1.1"

    def test_plan_validation_rejects_empty_goal(self, client):
        r = client.post("/api/agent/plan", json={"goal": ""})
        assert r.status_code == 422  # pydantic min_length


class TestHardenEndpoint:
    def test_harden_generates_script(self, client):
        r = client.post("/api/agent/harden", json={
            "goal": "SSH sıkılaştır",
            "security_level": "balanced",
            "format": "bash",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["format"] == "bash"
        assert "PermitRootLogin no" in data["artifact_content"]
        assert data["rule_count"] == 2
        step_names = [s["name"] for s in data["steps"]]
        assert "plan" in step_names and "generate" in step_names and "verify" in step_names

    def test_harden_ansible_format(self, client):
        r = client.post("/api/agent/harden", json={"goal": "hepsi", "format": "ansible"})
        assert r.status_code == 200
        assert "hosts: all" in r.json()["artifact_content"]
