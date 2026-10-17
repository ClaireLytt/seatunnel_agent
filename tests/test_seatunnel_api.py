"""In-process tests for the SeaTunnel Pipeline Builder REST API (/api/seatunnel).

Seam: the HTTP contract the React page consumes — same pattern as the
uitest / sql_review page API tests.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    from seatunnel_agent.agents.data.seatunnel.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_meta_returns_modes_and_templates(client: TestClient) -> None:
    resp = client.get("/api/seatunnel/meta")
    assert resp.status_code == 200
    data = resp.json()

    # modes: the four legacy agent modes with both language labels
    modes = data["modes"]
    assert [m["key"] for m in modes] == ["nl", "run", "validate", "diagnose"]
    by_key = {m["key"]: m for m in modes}
    assert by_key["nl"]["en"] == "Natural Language"
    assert by_key["nl"]["zh"] == "自然语言描述"
    assert by_key["diagnose"]["en"] == "Diagnose Log"

    # templates: sourced from the built-in template catalog
    from seatunnel_agent.agents.data.seatunnel.templates import TEMPLATES

    templates = data["templates"]
    assert len(templates) == len(TEMPLATES)
    names = [t["name"] for t in templates]
    assert "fake_to_console" in names
    first = templates[names.index("fake_to_console")]
    assert first["description"].startswith("FakeSource")
    assert first["category"] == "testing"
    assert first["parameters"][0]["name"] == "rows"


def test_meta_default_config_path(client: TestClient) -> None:
    data = client.get("/api/seatunnel/meta").json()
    assert data["config_placeholder"] == "examples/fake_to_console.conf"


def test_connect_success_returns_model(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from seatunnel_agent.common import config

    settings = config.Settings(api_key="k", model_name="claude-test-model")
    monkeypatch.setattr(config, "load_settings", lambda: settings)

    resp = client.post("/api/seatunnel/connect")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["model"] == "claude-test-model"


def test_connect_failure_returns_error(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from seatunnel_agent.common import config

    def _boom() -> config.Settings:
        raise ValueError("no API key configured")

    monkeypatch.setattr(config, "load_settings", _boom)

    resp = client.post("/api/seatunnel/connect")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "no API key configured" in data["error"]


def test_connect_failure_clears_stored_settings(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed connect must not leave stale settings behind (legacy parity)."""
    from seatunnel_agent.agents.data.seatunnel import api as st_api
    from seatunnel_agent.common import config

    settings = config.Settings(api_key="k", model_name="m")
    monkeypatch.setattr(config, "load_settings", lambda: settings)
    assert client.post("/api/seatunnel/connect").json()["ok"] is True
    assert st_api.CONNECTION["settings"] is settings

    def _boom() -> config.Settings:
        raise ValueError("gone")

    monkeypatch.setattr(config, "load_settings", _boom)
    assert client.post("/api/seatunnel/connect").json()["ok"] is False
    assert st_api.CONNECTION["settings"] is None
