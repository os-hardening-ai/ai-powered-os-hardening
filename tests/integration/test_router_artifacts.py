"""
Integration tests for api.router_artifacts — RuleEngine + ArtifactGenerator uçları.

Gerçek RuleEngine + ArtifactGenerator (tmp YAML fixture) ile; network/LLM yok.
/api/rules/plan, /api/rules/conflicts, /api/rules, /api/artifacts/generate.
"""

from __future__ import annotations

import textwrap

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.router_artifacts as ra
from api.router_artifacts import router
from api.errors import APIError, api_error_handler
from domain.rule_engine.rule_engine import RuleEngine
from domain.artifact_generator.generator import ArtifactGenerator

pytestmark = pytest.mark.integration


RULES_YAML = textwrap.dedent("""
rules:
  - id: "1.1.1"
    title: "Disable cramfs"
    level: 1
    category: "filesystem"
    kernel_module: "cramfs"
    config_files: ["/etc/modprobe.d/cramfs.conf"]
    remediation_script_content: "echo 'install cramfs /bin/false' >> /etc/modprobe.d/cramfs.conf"
  - id: "5.1.1"
    title: "Disable SSH root login"
    level: 1
    category: "ssh"
    config_files: ["/etc/ssh/sshd_config"]
    remediation_script_content: "sed -i 's/^PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config"
  - id: "5.1.2"
    title: "Set SSH MaxAuthTries"
    level: 1
    category: "ssh"
    config_files: ["/etc/ssh/sshd_config"]
    remediation_script_content: "echo 'MaxAuthTries 4' >> /etc/ssh/sshd_config"
""").strip()


@pytest.fixture
def client(tmp_path, monkeypatch):
    p = tmp_path / "rules.yaml"
    p.write_text(RULES_YAML, encoding="utf-8")
    engine = RuleEngine(p)
    # _get_rule_engine(os_target) artık arg alıyor (multi-OS) → *args ile uyumlu monkeypatch.
    monkeypatch.setattr(ra, "_get_rule_engine", lambda *a, **k: engine)
    monkeypatch.setattr(ra, "_get_artifact_gen", lambda *a, **k: ArtifactGenerator())
    app = FastAPI()
    app.add_exception_handler(APIError, api_error_handler)
    app.include_router(router, prefix="/api")
    return TestClient(app, raise_server_exceptions=False)


class TestRulesPlan:
    def test_ordered_plan(self, client):
        r = client.post("/api/rules/plan", json={"rule_ids": ["5.1.2", "1.1.1", "5.1.1"]})
        assert r.status_code == 200
        j = r.json()
        assert j["rule_count"] == 3
        # CIS bölüm-no sırasına dizilmeli
        assert j["ordered_rules"] == ["1.1.1", "5.1.1", "5.1.2"]

    def test_conflict_surfaced(self, client):
        # 5.1.1 ve 5.1.2 aynı sshd_config dosyasını yazıyor → çakışma
        r = client.post("/api/rules/plan", json={"rule_ids": ["5.1.1", "5.1.2"]})
        j = r.json()
        assert any({c["rule_a"], c["rule_b"]} == {"5.1.1", "5.1.2"} for c in j["conflicts"])
        assert j["warnings"]

    def test_empty_rule_ids_rejected_422(self, client):
        assert client.post("/api/rules/plan", json={"rule_ids": []}).status_code == 422


class TestConflicts:
    def test_conflicts_endpoint(self, client):
        r = client.post("/api/rules/conflicts", json={"rule_ids": ["5.1.1", "5.1.2"]})
        assert r.status_code == 200
        assert isinstance(r.json(), list) and len(r.json()) >= 1

    def test_no_conflict_returns_empty(self, client):
        r = client.post("/api/rules/conflicts", json={"rule_ids": ["1.1.1", "5.1.1"]})
        assert r.status_code == 200 and r.json() == []


class TestListRules:
    def test_list_all(self, client):
        r = client.get("/api/rules")
        assert r.status_code == 200
        j = r.json()
        assert j["total"] == 3 and len(j["rules"]) == 3

    def test_filter_by_category(self, client):
        r = client.get("/api/rules?category=ssh")
        assert {x["id"] for x in r.json()["rules"]} == {"5.1.1", "5.1.2"}

    def test_pagination(self, client):
        r = client.get("/api/rules?limit=1&offset=0")
        j = r.json()
        assert len(j["rules"]) == 1 and j["total"] == 3

    def test_script_content_stripped(self, client):
        # büyük script blob'lari liste yanitindan cikarilmali
        r = client.get("/api/rules")
        for rule in r.json()["rules"]:
            assert "remediation_script_content" not in rule
            assert "audit_script_content" not in rule


class TestArtifactGenerate:
    def test_bash_artifact(self, client):
        r = client.post("/api/artifacts/generate", json={
            "rule_ids": ["5.1.1", "5.1.2"], "format": "bash",
            "os_target": "ubuntu_24_04", "security_level": "balanced",
        })
        assert r.status_code == 200
        j = r.json()
        assert j["format"] == "bash"
        assert j["rule_count"] == 2
        assert "PermitRootLogin no" in j["content"]

    def test_ansible_artifact(self, client):
        r = client.post("/api/artifacts/generate", json={
            "rule_ids": ["5.1.1"], "format": "ansible",
        })
        assert r.status_code == 200
        assert r.json()["format"] == "ansible"
        assert "hosts:" in r.json()["content"]

    def test_unknown_rule_ids_404(self, client):
        r = client.post("/api/artifacts/generate", json={"rule_ids": ["9.9.9"]})
        assert r.status_code == 404
        assert "missing" in str(r.json()["error"]["details"])

    def test_partial_unknown_warns_but_succeeds(self, client):
        r = client.post("/api/artifacts/generate", json={
            "rule_ids": ["5.1.1", "9.9.9"], "format": "bash",
        })
        assert r.status_code == 200
        assert any("9.9.9" in w for w in r.json()["warnings"])

    def test_invalid_format_rejected_422(self, client):
        r = client.post("/api/artifacts/generate", json={
            "rule_ids": ["5.1.1"], "format": "exe",
        })
        assert r.status_code == 422
