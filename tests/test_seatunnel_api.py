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
