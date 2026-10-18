"""In-process tests for the Data Comparison REST API (ticket 02).

Seam: the HTTP contract of /api/datacompare (session create, meta,
per-side connect, tables listing) — never the internals of the
registry or the executors. Real connections are exercised against
file-backed SQLite fixtures.
"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    from seatunnel_agent.agents.data.data_comparison.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _make_db(path, tables: dict[str, list[tuple]]) -> str:
    conn = sqlite3.connect(path)
    for name, rows in tables.items():
        conn.execute(f"CREATE TABLE {name} (id INTEGER, val TEXT)")
        conn.executemany(f"INSERT INTO {name} VALUES (?, ?)", rows)
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture()
def db_a(tmp_path):
    return _make_db(tmp_path / "a.db",
                    {"orders": [(1, "x"), (2, "y")], "users": [(1, "u")]})


@pytest.fixture()
def db_b(tmp_path):
    return _make_db(tmp_path / "b.db", {"orders": [(1, "x")]})


def _session(client: TestClient) -> str:
    r = client.post("/api/datacompare/session")
    assert r.status_code == 200
    sid = r.json()["session_id"]
    assert isinstance(sid, str) and sid
    return sid


def _connect(client, sid, side, **kw):
    body = {"session_id": sid, "side": side, "ds_type": "sqlite",
            "host": "", "port": "", "db": "", "username": "",
            "password": "", "lang": "en"}
    body.update(kw)
    return client.post("/api/datacompare/connect", json=body)


# ── meta ────────────────────────────────────────────────────────────


def test_meta_lists_datasources(client):
    r = client.get("/api/datacompare/meta")
    assert r.status_code == 200
    data = r.json()
    by_key = {d["key"]: d for d in data["datasources"]}
    assert by_key["sqlite"]["label"] == "SQLite"
    assert by_key["sqlite"]["needs_host"] is False
    assert by_key["sqlite"]["needs_auth"] is False
    assert by_key["mysql"]["needs_host"] is True
    assert by_key["mysql"]["needs_auth"] is True
    assert by_key["mysql"]["default_port"] == 3306
    assert by_key["hive"]["needs_auth"] is False
    assert by_key["hive"]["default_db"] == "default"
    assert data["sample_strategies"] == ["TOP N", "RANDOM", "STRATIFIED"]
    assert "15" in data["schedule_intervals"]


# ── session ─────────────────────────────────────────────────────────


def test_session_create_issues_unique_ids(client):
    assert _session(client) != _session(client)


# ── connect ─────────────────────────────────────────────────────────


def test_connect_sqlite_success_per_side(client, db_a, db_b):
    sid = _session(client)

    ra = _connect(client, sid, "a", db=db_a).json()
    assert ra["ok"] is True
    assert ra["tables"] == ["orders", "users"]
    assert ra["status"].startswith("✅ SQLite")
    assert "2 tables loaded" in ra["status"]
    assert ra["resolved"]["database"] == db_a

    rb = _connect(client, sid, "b", db=db_b).json()
    assert rb["ok"] is True
    assert rb["tables"] == ["orders"]

    # side A untouched by side B's connect
    ta = client.get("/api/datacompare/tables",
                    params={"session_id": sid, "side": "a"}).json()
    assert ta["tables"] == ["orders", "users"]


def test_connect_failure_missing_host(client, monkeypatch):
    monkeypatch.delenv("MYSQL_HOST", raising=False)
    sid = _session(client)
    r = _connect(client, sid, "a", ds_type="mysql")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    assert "MYSQL_HOST" in data["error"]


def test_connect_failure_bad_port(client):
    sid = _session(client)
    data = _connect(client, sid, "a", ds_type="mysql",
                    host="example.invalid", port="not-a-number").json()
    assert data["ok"] is False
    assert "Port" in data["error"] or "端口" in data["error"]


def test_connect_unknown_session_404(client, db_a):
    r = _connect(client, "deadbeef", "a", db=db_a)
    assert r.status_code == 404


def test_connect_invalid_side_422(client, db_a):
    sid = _session(client)
    r = _connect(client, sid, "c", db=db_a)
    assert r.status_code == 422


def test_connect_unknown_ds_type(client):
    sid = _session(client)
    data = _connect(client, sid, "a", ds_type="nosuchdb").json()
    assert data["ok"] is False


# ── tables ──────────────────────────────────────────────────────────


def test_tables_before_connect_empty(client):
    sid = _session(client)
    r = client.get("/api/datacompare/tables",
                   params={"session_id": sid, "side": "b"})
    assert r.status_code == 200
    assert r.json()["tables"] == []


def test_tables_unknown_session_404(client):
    r = client.get("/api/datacompare/tables",
                   params={"session_id": "nope", "side": "a"})
    assert r.status_code == 404


# ── ticket 03: core comparison actions ──────────────────────────────


@pytest.fixture()
def connected(client, db_a, db_b) -> str:
    """Session with both sides connected to the SQLite fixtures."""
    sid = _session(client)
    assert _connect(client, sid, "a", db=db_a).json()["ok"] is True
    assert _connect(client, sid, "b", db=db_b).json()["ok"] is True
    return sid


def _action(client, sid, action, **kw):
    body = {"session_id": sid, "table_a": "orders", "table_b": "orders",
            "lang": "en"}
    body.update(kw)
    return client.post(f"/api/datacompare/compare/{action}", json=body)


def test_compare_schema_identical_card(client, connected):
    r = _action(client, connected, "schema")
    assert r.status_code == 200
    html = r.json()["html"]
    assert "Schema Comparison" in html
    assert "Schemas are identical" in html


def test_compare_schema_diff_card(client, connected, tmp_path):
    # side B gets a table with an extra column -> "added" row in the card
    db_c = tmp_path / "c.db"
    conn = sqlite3.connect(db_c)
    conn.execute("CREATE TABLE orders (id INTEGER, val TEXT, extra REAL)")
    conn.commit()
    conn.close()
    assert _connect(client, connected, "b", db=str(db_c)).json()["ok"] is True
    html = _action(client, connected, "schema").json()["html"]
    assert "Added" in html
    assert "extra" in html


def test_compare_count_card_with_threshold(client, connected):
    # a.orders=2 rows, b.orders=1 row -> delta -1 (-50%)
    html = _action(client, connected, "count", threshold="10%").json()["html"]
    assert "Row Count Comparison" in html
    assert "<b>2</b>" in html and "<b>1</b>" in html
    assert "Delta: +1 (+50.0%)" in html
    assert "FAIL" in html

    html2 = _action(client, connected, "count", threshold="60%").json()["html"]
    assert "PASS" in html2


def test_compare_sample_keyed_card(client, connected):
    html = _action(client, connected, "sample",
                   key_columns="id").json()["html"]
    assert "Key-Based Diff" in html
    assert "Removed rows" in html and "-1" in html


def test_compare_aggregate_card(client, connected):
    html = _action(client, connected, "aggregate").json()["html"]
    assert "Aggregate Comparison" in html


def test_compare_guard_not_connected(client):
    sid = _session(client)
    html = _action(client, sid, "schema").json()["html"]
    assert html == "Please connect both data sources first"


def test_compare_guard_tables_missing(client, connected):
    html = _action(client, connected, "schema", table_a="").json()["html"]
    assert html == "Please select tables on both sides"


def test_compare_guard_where_ddl(client, connected):
    html = _action(client, connected, "count",
                   where="1=1; DROP TABLE x").json()["html"]
    assert "forbidden keyword" in html


def test_compare_unknown_session_404(client):
    r = _action(client, "nope", "schema")
    assert r.status_code == 404


def test_compare_error_is_card_not_500(client, connected):
    html = _action(client, connected, "count",
                   table_b="no_such_table").json()["html"]
    assert "❌" in html
