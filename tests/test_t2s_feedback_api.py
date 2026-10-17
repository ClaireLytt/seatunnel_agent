"""Text2SQL feedback endpoint — ticket #109 seam."""

from __future__ import annotations

import sqlite3

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


@pytest.fixture()
def session(client, tmp_path):
    db = tmp_path / "demo.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, amount REAL)")
    con.commit()
    con.close()
    r = client.post("/api/text2sql/connect", json={
        "ds_type": "sqlite", "db_config": {"database": str(db)},
    })
    assert r.status_code == 200
    return r.json()["session_id"]


def test_feedback_positive_saves_favorite(client, session):
    r = client.post("/api/text2sql/feedback", json={
        "session_id": session,
        "question": "top orders",
        "sql": "SELECT * FROM orders LIMIT 10",
        "positive": True,
    })
    assert r.status_code == 200
    assert r.json()["positive"] is True

    favs = client.get("/api/text2sql/favorites").json()["favorites"]
    assert any(f["question"] == "top orders" for f in favs)


def test_feedback_negative(client, session):
    r = client.post("/api/text2sql/feedback", json={
        "session_id": session,
        "question": "bad query",
        "sql": "SELECT bad FROM orders",
        "positive": False,
    })
    assert r.status_code == 200
    assert r.json()["positive"] is False


def test_feedback_unknown_session(client):
    r = client.post("/api/text2sql/feedback", json={
        "session_id": "nonexistent",
        "question": "q",
        "sql": "SELECT 1",
        "positive": True,
    })
    assert r.status_code == 404
