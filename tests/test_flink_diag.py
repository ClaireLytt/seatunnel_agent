"""Tests for the flink-diag agent (49): diagnoser, report, API, CLI."""

from __future__ import annotations

import json
from pathlib import Path

from seatunnel_agent.agents.data.flink_diag import (
    diagnose_job,
    parse_job_snapshot,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "flinkdiag_demo" / "snapshot.json"
SNAP = DEMO.read_text("utf-8")


def _diag(text: str = SNAP):
    return diagnose_job(parse_job_snapshot(text))


# ── diagnoser ────────────────────────────────────────────────────────

def test_demo_fires_all_rules():
    diag = _diag()
    codes = {f.code for f in diag.findings}
    assert codes == {"FD001", "FD002", "FD003", "FD004", "FD005", "FD006"}
    assert diag.job == "sync-orders"


def test_checkpoint_blowup_ratio():
    f = next(f for f in _diag().findings if f.code == "FD002")
    assert f.detail["last_ms"] == 95000.0
    assert f.detail["ratio"] == 14.6


def test_alignment_share():
    f = next(f for f in _diag().findings if f.code == "FD003")
    assert f.detail["share_pct"] == 64.2


def test_backpressure_picks_worst_operator():
    f = next(f for f in _diag().findings if f.code == "FD004")
    assert f.detail["operator"] == "join-enrich"
    assert f.severity == "high"


def test_latest_failed_checkpoint_is_high():
    snap = json.dumps({"checkpoints": [
        {"id": 1, "duration_ms": 1000, "failed": False},
        {"id": 2, "duration_ms": 1000, "failed": True}]})
    f = next(f for f in _diag(snap).findings if f.code == "FD001")
    assert f.severity == "high" and f.detail["latest_failed"] is True


def test_restart_grading():
    mid = json.dumps({"restarts": 1})
    high = json.dumps({"restarts": {"count_1h": 5, "last_cause": "OOM"}})
    assert _diag(mid).findings[0].severity == "mid"
    f = _diag(high).findings[0]
    assert f.severity == "high" and f.detail["last_cause"] == "OOM"


def test_healthy_job_clean():
    snap = json.dumps({"job": "ok", "checkpoints": [
        {"id": 1, "duration_ms": 900, "failed": False, "alignment_ms": 10},
        {"id": 2, "duration_ms": 1000, "failed": False,
         "alignment_ms": 10}],
        "operators": [{"name": "s", "backpressure": 0.1,
                       "watermark_lag_ms": 500}]})
    diag = _diag(snap)
    assert diag.findings == []
    assert "healthy" in render_markdown(diag, lang="en")


def test_parse_rejects_bad_input():
    import pytest

    with pytest.raises(ValueError):
        parse_job_snapshot("  ")
    with pytest.raises(ValueError):
        parse_job_snapshot("not json")
    with pytest.raises(ValueError):
        parse_job_snapshot("[1]")


def test_findings_sorted_by_severity():
    sev = [f.severity for f in _diag().findings]
    order = {"high": 0, "mid": 1, "low": 2}
    assert sev == sorted(sev, key=order.__getitem__)


def test_report_both_langs():
    diag = _diag()
    zh = render_markdown(diag, lang="zh")
    en = render_markdown(diag, lang="en")
    assert "Flink 作业诊断" in zh and "FD004" in zh
    assert "Flink Job Diagnosis" in en and "unaligned" in en
    assert "kafkalag" in en and "skew-runtime" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.flink_diag import api as fd_api

    app = FastAPI()
    app.include_router(fd_api.router)
    return TestClient(app)


def test_api_diagnose_inline():
    res = _client().post("/api/flinkdiag/diagnose",
                         json={"snapshot_text": SNAP, "report": True,
                               "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert len(body["result"]["findings"]) == 6
    assert "Flink Job Diagnosis" in body["report"]


def test_api_bad_snapshot_400():
    res = _client().post("/api/flinkdiag/diagnose",
                         json={"snapshot_text": "not json"})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("FLINKDIAG_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/flinkdiag/diagnose",
                         json={"snapshot_file": str(DEMO)})
    assert res.status_code == 200
    bad = _client().post("/api/flinkdiag/diagnose",
                         json={"snapshot_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.flink_diag import advisor_llm

    monkeypatch.setattr(advisor_llm, "ops_note",
                        lambda diag, lang="zh": "FLINK-NOTE")
    res = _client().post("/api/flinkdiag/diagnose",
                         json={"snapshot_text": SNAP, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["ops_note"] == "FLINK-NOTE"


def test_api_health():
    body = _client().get("/api/flinkdiag/health").json()
    assert body == {"status": "ok", "agent": "flink_diag"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_flinkdiag_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["flinkdiag", "-f", str(DEMO),
                                   "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "Flink 作业诊断" in res.output and "join-enrich" in res.output


def test_cli_fail_on_high_gate():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["flinkdiag", "-f", str(DEMO),
                                   "--fail-on-high"])
    assert res.exit_code == 1
    clean = CliRunner().invoke(cli, [
        "flinkdiag", "--text", '{"job": "ok"}', "--fail-on-high"])
    assert clean.exit_code == 0, clean.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "flink_diag" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.flink_diag.tools import flink_diag

    out = flink_diag(SNAP, lang="en")
    assert "Flink Job Diagnosis" in out and "FD003" in out
    assert "must not be empty" in flink_diag("  ")
    assert "bad input" in flink_diag("not json")
