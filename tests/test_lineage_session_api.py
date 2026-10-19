"""REST tests for the /api/lineage session surface (ticket 01).

Covers the React-page endpoints added for the lineage migration:
session/build (graph parked server-side), session-aware query/search/
path/sla/check/snapshot reuse, GET /snapshots, SLA chain mermaid, and the
SSE /analyze/stream no-settings structured final frame. Uses the
committed demo data (examples/lineage_demo).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = str(ROOT / "examples" / "lineage_demo")


@pytest.fixture()
def api_client(monkeypatch, tmp_path):
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.data_lineage.api import router

    monkeypatch.setenv("LINEAGE_API_ALLOWED_DIRS", DEMO_DIR)
    monkeypatch.chdir(ROOT)
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture()
def session_id(api_client) -> str:
    r = api_client.post("/api/lineage/session")
    assert r.status_code == 200
    return r.json()["session_id"]


@pytest.fixture()
def built(api_client, session_id) -> str:
    r = api_client.post("/api/lineage/build", json={
        "session_id": session_id, "sql_dir": DEMO_DIR})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["stats"]["tables"] > 0
    assert data["tables"], "table list empty"
    return session_id


def test_build_requires_session(api_client):
    r = api_client.post("/api/lineage/build", json={"sql_dir": DEMO_DIR})
    assert r.status_code == 400


def test_build_unknown_session_404(api_client):
    r = api_client.post("/api/lineage/build", json={
        "session_id": "nope", "sql_dir": DEMO_DIR})
    assert r.status_code == 404


def test_query_needs_built_graph(api_client, session_id):
    r = api_client.post("/api/lineage/query", json={
        "session_id": session_id, "table": "whatever"})
    assert r.status_code == 400
    assert r.json()["detail"] == {"code": "need_graph"}


def test_query_reuses_session_graph(api_client, built):
    tables = api_client.post("/api/lineage/build", json={
        "session_id": built, "sql_dir": DEMO_DIR}).json()["tables"]
    r = api_client.post("/api/lineage/query", json={
        "session_id": built, "table": tables[0]})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["report"] and "mermaid" in data


def test_search_over_session(api_client, built):
    r = api_client.post("/api/lineage/search", json={
        "session_id": built, "keyword": "d"})
    assert r.status_code == 200
    assert isinstance(r.json()["matches"], list)


def test_sla_response_carries_chain_mermaid(api_client, built):
    tables = api_client.post("/api/lineage/build", json={
        "session_id": built, "sql_dir": DEMO_DIR}).json()["tables"]
    r = api_client.post("/api/lineage/sla_impact", json={
        "session_id": built, "table": tables[0], "delay_hours": 1})
    assert r.status_code == 200, r.text
    assert "mermaid" in r.json()


def test_snapshots_listing(api_client, built, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # snapshots land under ./logs
    r = api_client.post("/api/lineage/snapshot", json={
        "session_id": built, "name": "t1"})
    assert r.status_code == 200, r.text
    r = api_client.get("/api/lineage/snapshots")
    assert r.status_code == 200
    snaps = r.json()["snapshots"]
    assert any(s.get("name") == "t1" for s in snaps)


def test_health_check_over_session(api_client, built):
    r = api_client.post("/api/lineage/check", json={"session_id": built})
    assert r.status_code == 200
    assert "markdown" in r.json()


def test_whitelist_403_outside(api_client, session_id, tmp_path):
    r = api_client.post("/api/lineage/build", json={
        "session_id": session_id, "sql_dir": str(tmp_path)})
    assert r.status_code == 403


def test_analyze_stream_no_settings_structured(api_client, built, monkeypatch):
    # force load_settings to fail so the stream ends with the structured
    # no_settings final frame (deterministic — no LLM call)
    import seatunnel_agent.agents.data.data_lineage.api as api_mod

    def boom():
        raise RuntimeError("no key")

    monkeypatch.setattr(api_mod, "load_settings", boom)
    with api_client.stream("POST", "/api/lineage/analyze/stream", json={
            "session_id": built, "question": "which tables feed x?"}) as r:
        assert r.status_code == 200
        body = "".join(chunk for chunk in r.iter_text())
    frames = [json.loads(line[6:]) for line in body.splitlines()
              if line.startswith("data: ")]
    assert frames[-1]["type"] == "final"
    assert frames[-1]["error"] == "no_settings"
