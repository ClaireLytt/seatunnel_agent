"""Tests for the cdc-diag agent (51): diagnoser, report, API, CLI."""

from __future__ import annotations

import json
from pathlib import Path

from seatunnel_agent.agents.data.cdc_diag import (
    diagnose_cdc,
    parse_cdc_snapshot,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "cdcdiag_demo" / "snapshot.json"
SNAP = DEMO.read_text("utf-8")


def _diag(text: str = SNAP):
    return diagnose_cdc(parse_cdc_snapshot(text))


# ── diagnoser ────────────────────────────────────────────────────────

def test_demo_findings():
    diag = _diag()
    codes = {f.code for f in diag.findings}
    assert codes == {"CD001", "CD003", "CD004", "CD005"}


def test_files_behind_grading():
    f = next(f for f in _diag().findings if f.code == "CD001")
    assert f.detail["files_behind"] == 3 and f.severity == "high"
    one = json.dumps({"source": {"binlog_file": "b.000002", "position": 1},
                      "consumer": {"binlog_file": "b.000001",
                                   "position": 5}})
    f1 = next(f for f in _diag(one).findings if f.code == "CD001")
    assert f1.severity == "mid"


def test_byte_lag_same_file():
    snap = json.dumps({
        "source": {"binlog_file": "b.000005", "position": 50_000_000},
        "consumer": {"binlog_file": "b.000005", "position": 10_000_000}})
    f = next(f for f in _diag(snap).findings if f.code == "CD002")
    assert f.detail["byte_lag"] == 40_000_000 and f.severity == "mid"


def test_consumer_ahead_is_broken_resume():
    snap = json.dumps({
        "source": {"binlog_file": "b.000005", "position": 100},
        "consumer": {"binlog_file": "b.000007", "position": 1}})
    f = next(f for f in _diag(snap).findings if f.code == "CD006")
    assert f.severity == "high"
    same_file_ahead = json.dumps({
        "source": {"binlog_file": "b.000005", "position": 100},
        "consumer": {"binlog_file": "b.000005", "position": 999}})
    assert any(f.code == "CD006" for f in _diag(same_file_ahead).findings)


def test_retention_risk_share():
    f = next(f for f in _diag().findings if f.code == "CD004")
    assert f.detail["behind_h"] == 14.0
    assert f.detail["share_pct"] == 58.3


def test_error_classification():
    f = next(f for f in _diag().findings if f.code == "CD005")
    assert set(f.detail["classes"]) == {"duplicate_key", "schema_change",
                                        "connection"}
    assert f.severity == "high"          # schema change present


def test_healthy_sync_clean():
    snap = json.dumps({
        "source": {"binlog_file": "b.000005", "position": 1000,
                   "retention_hours": 24},
        "consumer": {"binlog_file": "b.000005", "position": 990,
                     "last_event_ts": "2026-10-31 12:00:00",
                     "now": "2026-10-31 12:00:30"}})
    diag = _diag(snap)
    assert diag.findings == []
    assert "healthy" in render_markdown(diag, lang="en")


def test_parse_rejects_bad_input():
    import pytest

    with pytest.raises(ValueError):
        parse_cdc_snapshot("  ")
    with pytest.raises(ValueError):
        parse_cdc_snapshot("not json")
    with pytest.raises(ValueError):
        parse_cdc_snapshot("[1]")


def test_report_both_langs():
    diag = _diag()
    zh = render_markdown(diag, lang="zh")
    en = render_markdown(diag, lang="en")
    assert "CDC 同步异常诊断" in zh and "CD004" in zh
    assert "CDC Sync Diagnosis" in en and "retention" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.cdc_diag import api as cd_api

    app = FastAPI()
    app.include_router(cd_api.router)
    return TestClient(app)


def test_api_diagnose_inline():
    res = _client().post("/api/cdcdiag/diagnose",
                         json={"snapshot_text": SNAP, "report": True,
                               "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert len(body["result"]["findings"]) == 4
    assert "CDC Sync Diagnosis" in body["report"]


def test_api_bad_snapshot_400():
    res = _client().post("/api/cdcdiag/diagnose",
                         json={"snapshot_text": "not json"})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("CDCDIAG_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/cdcdiag/diagnose",
                         json={"snapshot_file": str(DEMO)})
    assert res.status_code == 200
    bad = _client().post("/api/cdcdiag/diagnose",
                         json={"snapshot_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.cdc_diag import advisor_llm

    monkeypatch.setattr(advisor_llm, "incident_note",
                        lambda diag, lang="zh": "CDC-NOTE")
    res = _client().post("/api/cdcdiag/diagnose",
                         json={"snapshot_text": SNAP, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["incident_note"] == "CDC-NOTE"


def test_api_health():
    body = _client().get("/api/cdcdiag/health").json()
    assert body == {"status": "ok", "agent": "cdc_diag"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_cdcdiag_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["cdcdiag", "-f", str(DEMO),
                                   "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "CDC 同步异常诊断" in res.output and "CD001" in res.output


def test_cli_fail_on_high_gate():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["cdcdiag", "-f", str(DEMO),
                                   "--fail-on-high"])
    assert res.exit_code == 1
    clean = CliRunner().invoke(cli, [
        "cdcdiag", "--text", '{"source": {}}', "--fail-on-high"])
    assert clean.exit_code == 0, clean.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "cdc_diag" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.cdc_diag.tools import cdc_diag

    out = cdc_diag(SNAP, lang="en")
    assert "CDC Sync Diagnosis" in out and "CD006" not in out
    assert "must not be empty" in cdc_diag("  ")
    assert "bad input" in cdc_diag("not json")
