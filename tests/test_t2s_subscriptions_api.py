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


def test_run_now_executes_end_to_end(client, tmp_path, monkeypatch):
    """复活路径回归:REST run-now 真执行订阅并落盘状态(曾把
    SubscriptionStore 当 schema_store 传,从未成功过)."""
    import sqlite3

    db = tmp_path / "sales.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sales(order_id TEXT, amount REAL, channel TEXT, dt TEXT)")
    conn.execute("INSERT INTO sales VALUES ('o1', 100.0, 'app', '2026-03-01')")
    conn.commit()
    conn.close()
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "schema_ddl.sql").write_text(
        "CREATE TABLE sales(order_id string, amount double, "
        "channel string, dt string);",
        encoding="utf-8",
    )
    (tmp_path / "config" / "metrics.yaml").write_text(
        "metrics:\n  - name: gmv\n    table: sales\n"
        "    expression: SUM(amount)\n    time_column: dt\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SCHEMA_DDL_PATH", "config/schema_ddl.sql")

    r = client.post("/api/text2sql/subscriptions", json={
        "name": "e2e", "cron": "0 9 * * *", "source_type": "metric",
        "metric": "gmv", "ds_type": "sqlite", "database": str(db),
    })
    assert r.status_code == 201, r.text
    sub_id = r.json()["subscription"]["id"]

    r = client.post(f"/api/text2sql/subscriptions/{sub_id}/run")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "success", r.json()
    # run state persisted on the stored subscription
    stored = next(
        s for s in client.get("/api/text2sql/subscriptions").json()["subscriptions"]
        if s["id"] == sub_id
    )
    assert stored["last_status"] == "success"
