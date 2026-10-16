"""Text2SQL schema endpoints over a connected session — ticket #68 seam."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.text2sql.api import router


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture()
def session(client, tmp_path):
    db = tmp_path / "demo.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, amount REAL)")
    con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    con.commit()
    con.close()
    r = client.post("/api/text2sql/connect", json={
        "ds_type": "sqlite", "db_config": {"database": str(db)},
    })
    assert r.status_code == 200
    return r.json()["session_id"], str(db)


def test_schema_list_tables_with_column_counts(client, session):
    sid, _ = session
    r = client.get(f"/api/text2sql/session/{sid}/schema")
    assert r.status_code == 200
    tables = {t["name"]: t for t in r.json()["tables"]}
    assert set(tables) == {"orders", "users"}
    assert tables["orders"]["column_count"] == 2


def test_schema_table_detail(client, session):
    sid, _ = session
    r = client.get(f"/api/text2sql/session/{sid}/schema/orders")
    assert r.status_code == 200
    cols = {c["name"]: c["type"] for c in r.json()["columns"]}
    assert "amount" in cols
    assert client.get(
        f"/api/text2sql/session/{sid}/schema/nope").status_code == 404


def test_filter_narrows_and_widens_from_full_snapshot(client, session):
    sid, _ = session
    r = client.post(f"/api/text2sql/session/{sid}/schema/filter",
                    json={"tables": ["orders"]})
    assert r.status_code == 200
    assert r.json()["table_count"] == 1
    # the agent's live store shrank too
    s = client.get(f"/api/text2sql/session/{sid}")
    assert s.json()["table_count"] == 1
    # widening back works because the full snapshot is kept server-side
    r2 = client.post(f"/api/text2sql/session/{sid}/schema/filter",
                     json={"tables": ["orders", "users"]})
    assert r2.json()["table_count"] == 2
    # unknown table names are rejected, not silently dropped
    bad = client.post(f"/api/text2sql/session/{sid}/schema/filter",
                      json={"tables": ["ghost"]})
    assert bad.status_code == 400


def test_reload_picks_up_new_table(client, session):
    sid, db = session
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE refunds (id INTEGER PRIMARY KEY)")
    con.commit()
    con.close()
    r = client.post(f"/api/text2sql/session/{sid}/schema/reload")
    assert r.status_code == 200
    assert r.json()["table_count"] == 3


def test_schema_endpoints_404_unknown_session(client):
    assert client.get(
        "/api/text2sql/session/nope/schema").status_code == 404
    assert client.post(
        "/api/text2sql/session/nope/schema/reload").status_code == 404
