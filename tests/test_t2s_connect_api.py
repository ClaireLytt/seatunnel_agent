"""Text2SQL connect/session endpoints — ticket #64 seam (REST surface).

Connect holds the agent server-side and returns a session id; credentials
travel once. Session status is queryable; unknown ids 404.
"""

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
def demo_db(tmp_path) -> str:
    path = tmp_path / "demo.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, amount REAL)")
    con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    con.commit()
    con.close()
    return str(path)


def test_datasources_lists_dialects_with_env_defaults(client, monkeypatch):
    monkeypatch.setenv("MYSQL_HOST", "db.internal")
    monkeypatch.setenv("MYSQL_PORT", "3307")
    r = client.get("/api/text2sql/datasources")
    assert r.status_code == 200
    items = {d["ds_type"]: d for d in r.json()["datasources"]}
    assert "sqlite" in items and "mysql" in items
    assert items["mysql"]["defaults"]["host"] == "db.internal"
    assert items["mysql"]["defaults"]["port"] == "3307"
    # credentials never leak through defaults
    assert "password" not in items["mysql"]["defaults"]


def test_connect_returns_session_with_tables(client, demo_db):
    r = client.post("/api/text2sql/connect", json={
        "ds_type": "sqlite",
        "db_config": {"database": demo_db},
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["session_id"]
    assert data["ds_type"] == "sqlite"
    assert data["table_count"] == 2
    assert sorted(t.lower() for t in data["tables"]) == ["orders", "users"]

    # session is queryable afterwards — no credentials resent
    sid = data["session_id"]
    s = client.get(f"/api/text2sql/session/{sid}")
    assert s.status_code == 200
    assert s.json()["table_count"] == 2


def test_connect_rejects_unknown_ds_type(client):
    r = client.post("/api/text2sql/connect",
                    json={"ds_type": "nope", "db_config": {}})
    assert r.status_code == 400


def test_connect_rejects_empty_sqlite(client, tmp_path):
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    r = client.post("/api/text2sql/connect", json={
        "ds_type": "sqlite",
        "db_config": {"database": str(empty)},
    })
    assert r.status_code == 400  # no tables loaded


def test_session_unknown_id_404(client):
    assert client.get("/api/text2sql/session/doesnotexist").status_code == 404


def test_session_metrics_health(client, tmp_path, monkeypatch):
    import sqlite3 as _sq
    from datetime import date, timedelta

    monkeypatch.setenv("API_KEY", "test")  # agent 构造要求,health 本身零 LLM
    db = tmp_path / "h.db"
    con = _sq.connect(db)
    con.execute("CREATE TABLE sales (order_id TEXT, amount REAL, dt TEXT)")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    con.execute("INSERT INTO sales VALUES ('o1', 100.0, ?)", (yesterday,))
    con.commit()
    con.close()
    metrics_yaml = (
        "metrics:\n"
        "  - name: gmv\n"
        "    table: sales\n"
        "    expression: SUM(amount)\n"
        "    time_column: dt\n"
    )
    r = client.post("/api/text2sql/connect", json={
        "ds_type": "sqlite",
        "db_config": {"database": str(db)},
        "metrics_yaml": metrics_yaml,
    })
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    monkeypatch.chdir(tmp_path)  # qlog/订阅文件相对 cwd 解析

    h = client.get(f"/api/text2sql/session/{sid}/metrics/health")
    assert h.status_code == 200, h.text
    rows = h.json()["rows"]
    assert rows and rows[0]["metric"] == "gmv"
    assert rows[0]["latest_day"] == yesterday
    assert rows[0]["status"] in ("green", "yellow")

    assert client.get(
        "/api/text2sql/session/nope/metrics/health"
    ).status_code == 404
