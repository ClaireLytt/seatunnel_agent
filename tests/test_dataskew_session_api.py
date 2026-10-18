"""REST tests for the /api/skew session surface (ticket 01).

Covers the React-page endpoints added for the dataskew migration:
session/connect/status, analyze (static + llm fallback shape), verify,
consistency, splitkey, runtime, history, presets. Live-DB paths use the
repo's SQLite demo database (config/uitest_demo.db), same as the retired
uitest fixture ``connect_skew_sqlite``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEMO_DB = ROOT / "config" / "uitest_demo.db"

GROUP_SQL = "SELECT status, COUNT(*) FROM dc_test_orders_a GROUP BY status"


@pytest.fixture()
def api_client(monkeypatch, tmp_path):
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.data_skew.api import router

    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "history.jsonl"))
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture()
def session_id(api_client) -> str:
    r = api_client.post("/api/skew/session")
    assert r.status_code == 200
    return r.json()["session_id"]


@pytest.fixture()
def connected(api_client, session_id) -> str:
    assert DEMO_DB.is_file(), f"demo db missing: {DEMO_DB}"
    r = api_client.post("/api/skew/connect", json={
        "session_id": session_id, "ds_type": "sqlite",
        "database": str(DEMO_DB), "lang": "en"})
    assert r.status_code == 200, r.text
    assert r.json()["connected"] is True
    return session_id


def test_session_status_lifecycle(api_client, connected):
    r = api_client.get("/api/skew/status", params={"session_id": connected})
    assert r.json()["connected"] is True and r.json()["ds_type"] == "sqlite"
    r = api_client.post("/api/skew/disconnect", json={"session_id": connected})
    assert r.json()["connected"] is False
    r = api_client.get("/api/skew/status", params={"session_id": connected})
    assert r.json()["connected"] is False


def test_unknown_session_404(api_client):
    r = api_client.get("/api/skew/status", params={"session_id": "nope"})
    assert r.status_code == 404


def test_connect_failure_structured(api_client, session_id):
    r = api_client.post("/api/skew/connect", json={
        "session_id": session_id, "ds_type": "sqlite",
        "database": "no/such/file.db", "lang": "en"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "dsk_conn_fail"


def test_analyze_static(api_client):
    r = api_client.post("/api/skew/analyze", json={
        "sql": "SELECT COUNT(DISTINCT user_id) FROM t", "mode": "static",
        "lang": "en"})
    assert r.status_code == 200
    data = r.json()
    assert "Data Skew" in data["report"] or "report" in data
    assert data["optimized_sql"] == ""
    assert data["llm_unavailable"] is False


def test_verify_needs_connection(api_client, session_id):
    r = api_client.post("/api/skew/verify", json={
        "session_id": session_id, "sql": GROUP_SQL, "lang": "en"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "dsk_verify_need_conn"
    assert r.json()["detail"]["message"]


def test_verify_appends_probe_section(api_client, connected):
    r = api_client.post("/api/skew/verify", json={
        "session_id": connected, "sql": GROUP_SQL,
        "report": "## base report\nhello", "dialect": "spark",
        "sample": 0, "lang": "en"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "base report" in data["report"]
    assert len(data["report"]) > len("## base report\nhello")
    assert data["status"]


def test_verify_empty_sql(api_client, connected):
    r = api_client.post("/api/skew/verify", json={
        "session_id": connected, "sql": "  ", "lang": "en"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "dsk_empty_sql"


def test_consistency_needs_optimized(api_client, connected):
    r = api_client.post("/api/skew/consistency", json={
        "session_id": connected, "sql": GROUP_SQL, "optimized": "",
        "lang": "en"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "cst_need_opt"


def test_consistency_runs(api_client, connected):
    r = api_client.post("/api/skew/consistency", json={
        "session_id": connected, "sql": GROUP_SQL, "optimized": GROUP_SQL,
        "report": "## base", "lang": "en"})
    assert r.status_code == 200, r.text
    assert "base" in r.json()["report"]


def test_splitkey_empty_conf(api_client, connected):
    r = api_client.post("/api/skew/splitkey", json={
        "session_id": connected, "conf": "", "lang": "en"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "spk_empty_conf"


def test_runtime_history_server_needs_url(api_client):
    r = api_client.post("/api/skew/runtime/history-server", json={
        "url": "", "app_id": "", "lang": "en"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "rt_need_url"


def test_runtime_eventlog_bad_file_structured(api_client):
    r = api_client.post(
        "/api/skew/runtime/eventlog",
        files={"file": ("bad.log", b"not an event log")},
        data={"lang": "en"})
    assert r.status_code == 400
    assert "code" in r.json()["detail"]


def test_history_records(api_client):
    api_client.post("/api/skew/analyze", json={
        "sql": "SELECT 1", "mode": "static", "lang": "en"})
    r = api_client.get("/api/skew/history")
    assert r.status_code == 200
    recs = r.json()["records"]
    assert recs and recs[0]["sql"] == "SELECT 1"


def test_presets_list_shape(api_client):
    r = api_client.get("/api/skew/presets")
    assert r.status_code == 200
    for p in r.json()["presets"]:
        assert set(p) == {"name", "ds_type", "supported"}


def test_presets_get_unknown_404(api_client):
    assert api_client.get(
        "/api/skew/presets/__no_such_preset__").status_code == 404
