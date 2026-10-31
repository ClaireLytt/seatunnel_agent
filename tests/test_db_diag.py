"""Tests for the db-diag agent (46): diagnoser, report, API, CLI."""

from __future__ import annotations

import json
from pathlib import Path

from seatunnel_agent.agents.data.db_diag import (
    diagnose_snapshot,
    parse_snapshot,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "dbdiag_demo" / "snapshot.json"
SNAP = DEMO.read_text("utf-8")


def _diag(text: str = SNAP):
    return diagnose_snapshot(parse_snapshot(text))


# ── diagnoser ────────────────────────────────────────────────────────

def test_demo_fires_all_sections():
    diag = _diag()
    codes = {f.code for f in diag.findings}
    assert codes == {"DB001", "DB002", "DB003", "DB004", "DB005", "DB006"}
    assert diag.sections_seen == ["variables", "status", "lock_waits",
                                  "deadlocks", "slow_queries"]


def test_pool_pressure_grading():
    mid = json.dumps({"variables": {"max_connections": 100},
                      "status": {"threads_connected": 85}})
    high = json.dumps({"variables": {"max_connections": 100},
                       "status": {"threads_connected": 97}})
    ok = json.dumps({"variables": {"max_connections": 100},
                     "status": {"threads_connected": 50}})
    assert _diag(mid).findings[0].severity == "mid"
    assert _diag(high).findings[0].severity == "high"
    assert _diag(ok).findings == []


def test_lock_waits_filter_and_top():
    diag = _diag()
    f = next(f for f in diag.findings if f.code == "DB003")
    assert f.detail["count"] == 2            # the 2s wait is below 5s
    assert f.detail["worst_seconds"] == 42.0
    assert f.detail["top"][0]["blocking"] == "trx 7001"


def test_deadlocks_list_or_int():
    as_list = json.dumps({"deadlocks": [{"a": 1}, {"b": 2}]})
    diag = _diag(as_list)
    f = next(f for f in diag.findings if f.code == "DB004")
    assert f.detail["count"] == 2


def test_slow_queries_sorted_and_truncated():
    diag = _diag()
    f = next(f for f in diag.findings if f.code == "DB005")
    assert f.severity == "high"              # 12.5s >= 10
    assert f.detail["top"][0]["duration_s"] == 12.5


def test_missing_sections_ok():
    diag = _diag(json.dumps({"status": {"threads_running": 4}}))
    assert diag.findings == []


def test_findings_sorted_by_severity():
    sev = [f.severity for f in _diag().findings]
    order = {"high": 0, "mid": 1, "low": 2}
    assert sev == sorted(sev, key=order.__getitem__)


def test_parse_rejects_non_json():
    import pytest

    with pytest.raises(ValueError):
        parse_snapshot("not json")
    with pytest.raises(ValueError):
        parse_snapshot("[1,2]")
    with pytest.raises(ValueError):
        parse_snapshot("  ")


def test_report_both_langs():
    diag = _diag()
    zh = render_markdown(diag, lang="zh")
    en = render_markdown(diag, lang="en")
    assert "数据库运行诊断" in zh and "DB003" in zh
    assert "Database Runtime Diagnosis" in en and "prescription" in en
    assert "slowquery" in en


def test_report_clean():
    md = render_markdown(_diag(json.dumps({"status": {}})), lang="en")
    assert "healthy" in md


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.db_diag import api as db_api

    app = FastAPI()
    app.include_router(db_api.router)
    return TestClient(app)


def test_api_diagnose_inline():
    res = _client().post("/api/dbdiag/diagnose",
                         json={"snapshot_text": SNAP, "report": True,
                               "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert len(body["result"]["findings"]) == 6
    assert "Database Runtime Diagnosis" in body["report"]


def test_api_bad_snapshot_400():
    res = _client().post("/api/dbdiag/diagnose",
                         json={"snapshot_text": "not json"})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("DBDIAG_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/dbdiag/diagnose",
                         json={"snapshot_file": str(DEMO)})
    assert res.status_code == 200
    bad = _client().post("/api/dbdiag/diagnose",
                         json={"snapshot_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.db_diag import advisor_llm

    monkeypatch.setattr(advisor_llm, "incident_note",
                        lambda diag, lang="zh": "DB-NOTE")
    res = _client().post("/api/dbdiag/diagnose",
                         json={"snapshot_text": SNAP, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["incident_note"] == "DB-NOTE"


def test_api_health():
    body = _client().get("/api/dbdiag/health").json()
    assert body == {"status": "ok", "agent": "db_diag"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_dbdiag_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["dbdiag", "-f", str(DEMO), "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "数据库运行诊断" in res.output and "DB001" in res.output


def test_cli_fail_on_high_gate():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["dbdiag", "-f", str(DEMO),
                                   "--fail-on-high"])
    assert res.exit_code == 1
    clean = CliRunner().invoke(cli, [
        "dbdiag", "--text", '{"status": {"threads_running": 2}}',
        "--fail-on-high"])
    assert clean.exit_code == 0, clean.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "db_diag" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.db_diag.tools import db_diag

    out = db_diag(SNAP, lang="en")
    assert "Database Runtime Diagnosis" in out and "DB004" in out
    assert "must not be empty" in db_diag("  ")
    assert "bad input" in db_diag("not json")
