"""Text2SQL boards CRUD + pin endpoints — ticket #117 seam."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.text2sql.api import router
from seatunnel_agent.agents.data.text2sql.api_boards import _board_store


@pytest.fixture()
def client(tmp_path) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    _board_store.path = tmp_path / "boards.json"
    return TestClient(app)


def test_list_empty(client):
    r = client.get("/api/text2sql/boards")
    assert r.status_code == 200
    assert r.json()["boards"] == []


def test_create_and_list(client):
    r = client.post("/api/text2sql/boards", json={"name": "my board"})
    assert r.status_code == 201
    board = r.json()["board"]
    assert board["name"] == "my board"
    assert "id" in board

    listed = client.get("/api/text2sql/boards").json()["boards"]
    assert len(listed) == 1


def test_create_duplicate_rejected(client):
    client.post("/api/text2sql/boards", json={"name": "dup"})
    r = client.post("/api/text2sql/boards", json={"name": "dup"})
    assert r.status_code == 400


def test_delete(client):
    board = client.post("/api/text2sql/boards", json={"name": "bye"}).json()["board"]
    r = client.delete(f"/api/text2sql/boards/{board['id']}")
    assert r.status_code == 200
    assert client.get("/api/text2sql/boards").json()["boards"] == []


def test_delete_404(client):
    assert client.delete("/api/text2sql/boards/nope").status_code == 404


def test_pin(client):
    board = client.post("/api/text2sql/boards", json={"name": "dash"}).json()["board"]
    r = client.post(f"/api/text2sql/boards/{board['id']}/pin",
                    json={"title": "top orders", "sql": "SELECT * FROM orders LIMIT 10"})
    assert r.status_code == 200
    item = r.json()["item"]
    assert item["title"] == "top orders"

    listed = client.get("/api/text2sql/boards").json()["boards"]
    assert len(listed[0]["items"]) == 1


def test_pin_404(client):
    r = client.post("/api/text2sql/boards/nope/pin",
                    json={"title": "x", "sql": "SELECT 1"})
    assert r.status_code == 400  # ValueError from store
