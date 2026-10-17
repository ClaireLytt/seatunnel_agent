"""Text2SQL favorites CRUD endpoints — ticket #107 seam."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.text2sql.api import router
from seatunnel_agent.agents.data.text2sql.api_shared import fav_store


@pytest.fixture()
def client(tmp_path) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    fav_store.path = tmp_path / "favs.json"
    return TestClient(app)


def test_list_empty(client):
    r = client.get("/api/text2sql/favorites")
    assert r.status_code == 200
    assert r.json()["favorites"] == []


def test_save_and_list(client):
    r = client.post("/api/text2sql/favorites", json={
        "name": "top orders", "sql": "SELECT * FROM orders LIMIT 10",
        "question": "show top orders", "ds_type": "hive",
    })
    assert r.status_code == 201
    fav = r.json()["favorite"]
    assert fav["name"] == "top orders"
    assert "id" in fav

    listed = client.get("/api/text2sql/favorites").json()["favorites"]
    assert len(listed) == 1
    assert listed[0]["id"] == fav["id"]


def test_rename(client):
    fav = client.post("/api/text2sql/favorites", json={
        "name": "old", "sql": "SELECT 1",
    }).json()["favorite"]

    r = client.patch(f"/api/text2sql/favorites/{fav['id']}", json={"name": "new"})
    assert r.status_code == 200

    listed = client.get("/api/text2sql/favorites").json()["favorites"]
    assert listed[0]["name"] == "new"


def test_rename_404(client):
    r = client.patch("/api/text2sql/favorites/nope", json={"name": "x"})
    assert r.status_code == 404


def test_delete(client):
    fav = client.post("/api/text2sql/favorites", json={
        "name": "bye", "sql": "SELECT 1",
    }).json()["favorite"]

    r = client.delete(f"/api/text2sql/favorites/{fav['id']}")
    assert r.status_code == 200
    assert client.get("/api/text2sql/favorites").json()["favorites"] == []


def test_delete_404(client):
    assert client.delete("/api/text2sql/favorites/nope").status_code == 404


def test_save_respects_max_capacity(client):
    for i in range(205):
        client.post("/api/text2sql/favorites", json={
            "name": f"q{i}", "sql": f"SELECT {i}",
        })
    listed = client.get("/api/text2sql/favorites").json()["favorites"]
    assert len(listed) == 200
