"""In-process tests for the Data Comparison REST API (ticket 02).

Seam: the HTTP contract of /api/datacompare (session create, meta,
per-side connect, tables listing) — never the internals of the
registry or the executors. Real connections are exercised against
file-backed SQLite fixtures.
"""

from __future__ import annotations

import json
import sqlite3
import threading

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


# ── presets (ticket 05) ─────────────────────────────────────────────


@pytest.fixture()
def presets_tmp(tmp_path, monkeypatch):
    """Point the API's presets store (and its key file) at tmp_path."""
    from seatunnel_agent.agents.data.data_comparison import api as api_mod
    from seatunnel_agent.agents.data.data_comparison import presets as presets_mod
    from seatunnel_agent.agents.data.data_comparison.presets import (
        ConnectionPresetsStore,
    )

    monkeypatch.setattr(presets_mod, "_KEY_PATH", tmp_path / "dc_secret.key")
    monkeypatch.setattr(presets_mod, "_cached_key", None)
    store = ConnectionPresetsStore(tmp_path / "dc_connections.json")
    monkeypatch.setattr(api_mod, "_PRESETS_STORE", store)
    return store


def _save_preset(client, **kw):
    body = {"name": "prod-mysql", "ds_type": "mysql", "host": "db.example",
            "port": 3306, "database": "sales", "username": "u",
            "password": "s3cret", "environment": "prod"}
    body.update(kw)
    return client.post("/api/datacompare/presets", json=body)


def test_presets_list_empty(client, presets_tmp):
    r = client.get("/api/datacompare/presets")
    assert r.status_code == 200
    assert r.json()["presets"] == []


def test_presets_save_load_delete_round_trip(client, presets_tmp):
    r = _save_preset(client)
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # list shows summary fields only — never the password
    listed = client.get("/api/datacompare/presets").json()["presets"]
    assert [(p["name"], p["environment"]) for p in listed] == [
        ("prod-mysql", "prod")]
    assert "password" not in listed[0]

    # load returns the full connection (password decrypted to fill the form)
    full = client.get("/api/datacompare/presets/prod-mysql").json()
    assert full["ds_type"] == "mysql"
    assert full["host"] == "db.example"
    assert full["port"] == 3306
    assert full["database"] == "sales"
    assert full["username"] == "u"
    assert full["password"] == "s3cret"
    assert full["environment"] == "prod"

    r = client.delete("/api/datacompare/presets/prod-mysql")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert client.get("/api/datacompare/presets").json()["presets"] == []


def test_presets_save_same_name_replaces(client, presets_tmp):
    _save_preset(client)
    _save_preset(client, host="other.example", environment="staging")
    listed = client.get("/api/datacompare/presets").json()["presets"]
    assert len(listed) == 1
    full = client.get("/api/datacompare/presets/prod-mysql").json()
    assert full["host"] == "other.example"
    assert full["environment"] == "staging"


def test_presets_save_empty_name_rejected(client, presets_tmp):
    r = _save_preset(client, name="   ")
    assert r.status_code == 400


def test_presets_load_unknown_404(client, presets_tmp):
    assert client.get("/api/datacompare/presets/nope").status_code == 404


def test_presets_delete_unknown_404(client, presets_tmp):
    assert client.delete("/api/datacompare/presets/nope").status_code == 404

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


def test_compare_count_where_filters_rows(client, connected):
    """Options semantics: WHERE narrows the counted rows on both sides.

    Unfiltered, a.orders=2 vs b.orders=1 fails a 10% threshold; with
    WHERE id = 1 both sides count exactly one row, so the same
    threshold passes — proving the clause reaches the SQL.
    """
    unfiltered = _action(client, connected, "count",
                         threshold="10%").json()["html"]
    assert "FAIL" in unfiltered

    filtered = _action(client, connected, "count", threshold="10%",
                       where="id = 1").json()["html"]
    assert "Count (A): <b>1</b>" in filtered
    assert "Count (B): <b>1</b>" in filtered
    assert "Match" in filtered
    assert "FAIL" not in filtered


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


# ── ticket 04: compound actions with progress ───────────────────────


def _frames(text: str) -> list[dict]:
    """Parse SSE 'data: {json}' frames from a buffered response body."""
    return [json.loads(line[6:]) for line in text.splitlines()
            if line.startswith("data: ")]


def _compound(client, sid, action, **kw):
    body = {"session_id": sid, "table_a": "orders", "table_b": "orders",
            "lang": "en"}
    body.update(kw)
    return client.post(f"/api/datacompare/compare/{action}", json=body)


def test_compare_all_streams_progress_then_done(client, connected):
    r = _compound(client, connected, "all")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    frames = _frames(r.text)
    progress = [f for f in frames if f["event"] == "progress"]
    assert progress, "expected at least one progress frame"
    for f in progress:
        assert 0 < f["value"] <= 1
        assert isinstance(f["desc"], str)
    assert frames[-1]["event"] == "done"
    html = frames[-1]["html"]
    assert "Comparison Summary" in html
    assert "Schema Comparison" in html
    assert "Row Count Comparison" in html
    assert "Column Profile Comparison" in html


def test_compare_all_stores_last_report(client, connected):
    from seatunnel_agent.agents.data.data_comparison.registry import (
        get_registry,
    )

    _compound(client, connected, "all")
    session = get_registry().get(connected)
    assert session is not None and session.last_report is not None
    assert session.last_report.schema is not None
    assert session.last_report.row_count is not None


def test_compare_all_guard_not_connected(client):
    sid = _session(client)
    frames = _frames(_compound(client, sid, "all").text)
    assert frames == [
        {"event": "done",
         "html": "Please connect both data sources first"}]


def test_compare_all_guard_where_ddl(client, connected):
    frames = _frames(_compound(client, connected, "all",
                               where="1=1; DROP TABLE x").text)
    assert frames[-1]["event"] == "done"
    assert "forbidden keyword" in frames[-1]["html"]


def test_compare_all_409_when_running(client, connected, monkeypatch):
    from seatunnel_agent.agents.data.data_comparison import compound

    started = threading.Event()
    release = threading.Event()
    orig = compound.profile_inner

    def slow(*args, **kwargs):
        started.set()
        assert release.wait(10)
        return orig(*args, **kwargs)

    monkeypatch.setattr(compound, "profile_inner", slow)

    result: dict = {}

    def run() -> None:
        result["r"] = _compound(client, connected, "all")

    th = threading.Thread(target=run)
    th.start()
    try:
        assert started.wait(10), "first run never started"
        r2 = _compound(client, connected, "all")
        assert r2.status_code == 409
        # the guard also covers the other compound actions of the session
        r3 = _compound(client, connected, "batch-count")
        assert r3.status_code == 409
    finally:
        release.set()
        th.join(30)
    assert result["r"].status_code == 200
    assert _frames(result["r"].text)[-1]["event"] == "done"


def test_compare_all_unknown_session_404(client):
    assert _compound(client, "nope", "all").status_code == 404


def test_batch_count_progress_per_table_and_card(client, connected):
    r = _compound(client, connected, "batch-count")
    assert r.status_code == 200
    frames = _frames(r.text)
    progress = [f for f in frames if f["event"] == "progress"]
    # one common table (orders) -> one per-table progress frame
    assert len(progress) == 1
    assert "orders" in progress[0]["desc"]
    assert progress[0]["value"] == 1.0
    assert frames[-1]["event"] == "done"
    assert "Batch Row Count" in frames[-1]["html"]


def test_batch_full_streams_and_renders_card(client, connected):
    r = _compound(client, connected, "batch-full", threshold="60%")
    assert r.status_code == 200
    frames = _frames(r.text)
    assert any(f["event"] == "progress" for f in frames)
    assert frames[-1]["event"] == "done"
    html = frames[-1]["html"]
    assert "Batch Full Comparison" in html
    assert "orders" in html


def test_batch_guard_not_connected(client):
    sid = _session(client)
    frames = _frames(_compound(client, sid, "batch-count").text)
    assert frames == [
        {"event": "done",
         "html": "Please connect both data sources first"}]


def test_profile_card(client, connected):
    r = _compound(client, connected, "profile")
    assert r.status_code == 200
    html = r.json()["html"]
    assert "Column Profile Comparison" in html


def test_profile_guard_not_connected(client):
    sid = _session(client)
    html = _compound(client, sid, "profile").json()["html"]
    assert html == "Please connect both data sources first"
