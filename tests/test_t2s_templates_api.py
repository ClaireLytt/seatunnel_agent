"""Text2SQL templates endpoint — ticket #112 seam."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.text2sql.api import router


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_templates_list_returns_all_presets(client):
    r = client.get("/api/text2sql/templates")
    assert r.status_code == 200
    templates = r.json()["templates"]
    assert len(templates) == 8
    ids = {t["id"] for t in templates}
    assert "mom" in ids
    assert "yoy" in ids
    assert "topn" in ids


def test_template_has_required_fields(client):
    r = client.get("/api/text2sql/templates")
    t = r.json()["templates"][0]
    for field in ("id", "name_en", "name_zh", "description_en", "description_zh", "pattern"):
        assert field in t, f"missing field: {field}"
