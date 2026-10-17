"""Text2SQL subscriptions CRUD endpoints — ticket #118 seam."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.text2sql.api import router
from seatunnel_agent.agents.data.text2sql.api_subscriptions import _sub_store


@pytest.fixture()
def client(tmp_path) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    _sub_store.path = tmp_path / "subs.json"
    return TestClient(app)


def test_list_empty(client):
    r = client.get("/api/text2sql/subscriptions")
    assert r.status_code == 200
    assert r.json()["subscriptions"] == []


def test_create_and_list(client):
    r = client.post("/api/text2sql/subscriptions", json={
        "name": "daily gmv", "cron": "0 9 * * *",
        "source_type": "metric", "metric": "gmv",
    })
    assert r.status_code == 201
    sub = r.json()["subscription"]
    assert sub["name"] == "daily gmv"
    assert sub["enabled"] is True

    listed = client.get("/api/text2sql/subscriptions").json()["subscriptions"]
    assert len(listed) == 1


def test_create_rejects_empty_name(client):
    r = client.post("/api/text2sql/subscriptions", json={
        "name": "", "cron": "0 9 * * *",
        "source_type": "metric", "metric": "gmv",
    })
    assert r.status_code == 422  # pydantic min_length


def test_delete(client):
    sub = client.post("/api/text2sql/subscriptions", json={
        "name": "bye", "cron": "0 9 * * *",
        "source_type": "metric", "metric": "gmv",
    }).json()["subscription"]
    r = client.delete(f"/api/text2sql/subscriptions/{sub['id']}")
    assert r.status_code == 200
    assert client.get("/api/text2sql/subscriptions").json()["subscriptions"] == []


def test_delete_404(client):
    assert client.delete("/api/text2sql/subscriptions/nope").status_code == 404


def test_patch_enable_disable(client):
    sub = client.post("/api/text2sql/subscriptions", json={
        "name": "toggle", "cron": "0 9 * * *",
        "source_type": "metric", "metric": "gmv",
    }).json()["subscription"]

    r = client.patch(f"/api/text2sql/subscriptions/{sub['id']}",
                     json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    listed = client.get("/api/text2sql/subscriptions").json()["subscriptions"]
    assert listed[0]["enabled"] is False


def test_patch_404(client):
    r = client.patch("/api/text2sql/subscriptions/nope",
                     json={"enabled": False})
    assert r.status_code == 404
