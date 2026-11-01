"""Tests for the timezone_audit agent (auditor / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.sample_profile import parse_rows
from seatunnel_agent.agents.data.timezone_audit import (
    audit_timezones,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "timezoneaudit_demo" / "rows.csv"


def _demo_audit():
    headers, rows = parse_rows(DEMO.read_text(encoding="utf-8"))
    return audit_timezones(headers, rows)


# ----------------------------------------------------------------- auditor

def test_demo_fires_all_codes():
    audit = _demo_audit()
    assert len(audit.columns) == 2            # note column ignored
    codes = {(f.code, f.column) for f in audit.findings}
    assert ("TZ001", "created_at") in codes
    assert ("TZ002", "event_ts") in codes
    assert ("TZ003", "created_at") in codes
    assert ("TZ004", "created_at") in codes


def test_offset_and_unit_tallies():
    audit = _demo_audit()
    by = {c.name: c for c in audit.columns}
    assert by["created_at"].offsets == {"+08:00": 10, "Z": 11}
    assert by["created_at"].hour_modes == [2, 10]
    assert by["created_at"].sentinel == 1
    assert by["event_ts"].kinds == {"s": 11, "ms": 10}


def test_consistent_column_is_clean():
    csv = "created_at\n" + "".join(
        f"2026-10-{i:02d}T10:00:00+08:00\n" for i in range(1, 15))
    headers, rows = parse_rows(csv)
    audit = audit_timezones(headers, rows)
    assert audit.findings == []


def test_naive_vs_offset_counts_as_tz001():
    csv = ("created_at\n2026-10-01T10:00:00\n"
           "2026-10-02T10:00:00+08:00\n")
    headers, rows = parse_rows(csv)
    audit = audit_timezones(headers, rows)
    (f,) = [f for f in audit.findings if f.code == "TZ001"]
    assert "naive" in f.detail


def test_non_time_columns_skipped_and_bad_inputs():
    headers, rows = parse_rows("name,qty\nalice,3\nbob,5\n")
    with pytest.raises(ValueError, match="no timestamp-shaped"):
        audit_timezones(headers, rows)
    with pytest.raises(ValueError, match="at least one row"):
        audit_timezones([], [])


def test_timeish_name_wins_low_parse_share():
    # a time-named column qualifies even when most values are junk
    csv = "event_ts,v\nnot-a-time,1\n1730000000,2\n"
    headers, rows = parse_rows(csv)
    audit = audit_timezones(headers, rows)
    assert audit.columns[0].name == "event_ts"
    assert audit.columns[0].values == 1


# ------------------------------------------------------------------ report

def test_report_both_langs_and_clean():
    audit = _demo_audit()
    zh = render_markdown(audit, lang="zh")
    en = render_markdown(audit, lang="en")
    assert "时间戳体检" in zh and "差一千倍" in zh
    assert "Timezone Audit" in en and "direct evidence" in en
    csv = "created_at\n" + "".join(
        f"2026-10-{i:02d}T10:00:00Z\n" for i in range(1, 12))
    headers, rows = parse_rows(csv)
    clean = render_markdown(audit_timezones(headers, rows), lang="en")
    assert "consistent" in clean


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ["timezoneaudit", "-f", str(DEMO)])
    assert res.exit_code == 0, res.output
    assert "时间戳体检" in res.output
    res = runner.invoke(cli, ["timezoneaudit", "-f", str(DEMO),
                              "--format", "json"])
    assert res.exit_code == 0 and '"columns_audited": 2' in res.output
    res = runner.invoke(cli, ["timezoneaudit", "-f", str(DEMO),
                              "--fail-on-high"])
    assert res.exit_code == 1
    res = runner.invoke(cli, ["timezoneaudit", "--text",
                              "created_at\n2026-10-01T10:00:00Z\n"
                              "2026-10-02T11:00:00Z",
                              "--fail-on-high"])
    assert res.exit_code == 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.timezone_audit.tools import (
        timezone_audit,
    )

    out = timezone_audit(DEMO.read_text(encoding="utf-8"), lang="en")
    assert "TZ002" in out and "event_ts" in out
    assert "must not be empty" in timezone_audit("  ")
    assert "bad input" in timezone_audit("name,qty\na,1")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.timezone_audit.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_audit_and_health():
    client = _client()
    assert client.get("/api/timezoneaudit/health").status_code == 200
    resp = client.post("/api/timezoneaudit/audit", json={
        "data_text": DEMO.read_text(encoding="utf-8"),
        "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["columns_audited"] == 2
    assert "Timezone Audit" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/timezoneaudit/audit",
                       json={"data_text": "name,qty\na,1"})
    assert resp.status_code == 400
