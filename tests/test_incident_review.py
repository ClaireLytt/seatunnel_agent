"""Tests for the incident_review agent (reviewer / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.incident_review import (
    render_markdown,
    review_incident,
)
from seatunnel_agent.agents.data.sample_profile import parse_rows

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "incidentreview_demo" / "events.csv"


def _demo_review():
    headers, rows = parse_rows(DEMO.read_text(encoding="utf-8"))
    return review_incident(headers, rows)


# ---------------------------------------------------------------- reviewer

def test_demo_metrics_and_timeline():
    review = _demo_review()
    assert (review.mttd_min, review.mtta_min, review.mttr_min) == \
        (25.0, 25.0, 150.0)
    assert [e.kind for e in review.events] == \
        ["impact", "alert", "action", "comm", "action", "recovery"]
    assert review.events[0].minute == 0.0


def test_demo_findings():
    review = _demo_review()
    by = {f.code: f for f in review.findings}
    assert set(by) == {"IR001", "IR002", "IR003"}
    assert by["IR003"].value == 50.0 and by["IR003"].detail == "@50min"
    assert by["IR001"].severity == "medium"


def test_high_grades_and_missing_recovery():
    csv = ("time,kind,text\n"
           "00:00,impact,x\n"
           "01:30,alert,y\n"          # 90 min detection -> high
           "03:00,action,z\n")        # 90 min response -> high, no recovery
    headers, rows = parse_rows(csv)
    review = review_incident(headers, rows)
    by = {f.code: f.severity for f in review.findings}
    assert by["IR001"] == "high" and by["IR002"] == "high"
    assert by["IR004"] == "high"
    assert review.mttr_min is None


def test_clean_incident():
    csv = ("time,kind,text\n"
           "10:00,impact,x\n10:05,alert,y\n10:10,action,z\n"
           "10:30,recovery,ok\n")
    headers, rows = parse_rows(csv)
    review = review_incident(headers, rows)
    assert review.findings == []
    assert review.mttr_min == 30.0


def test_iso_times_and_unsorted_rows():
    csv = ("time,kind,text\n"
           "2026-10-30T02:50:00,action,z\n"
           "2026-10-30T02:00:00,impact,x\n"
           "2026-10-30T02:25:00,alert,y\n"
           "2026-10-30T03:00:00,recovery,ok\n")
    headers, rows = parse_rows(csv)
    review = review_incident(headers, rows)
    assert review.events[0].kind == "impact"       # sorted
    assert review.mttd_min == 25.0


def test_bad_inputs():
    headers, rows = parse_rows("time,kind,text\n02:00,boom,x\n")
    with pytest.raises(ValueError, match="kind must be one of"):
        review_incident(headers, rows)
    h2, r2 = parse_rows("time,kind,text\n02:00,alert,x\n")
    with pytest.raises(ValueError, match="no 'impact' event"):
        review_incident(h2, r2)
    h3, r3 = parse_rows("time,kind,text\n"
                        "02:00,impact,x\n2026-10-30T02:25:00,alert,y\n")
    with pytest.raises(ValueError, match="mixes HH:MM"):
        review_incident(h3, r3)


# ------------------------------------------------------------------ report

def test_report_both_langs_and_clean():
    review = _demo_review()
    zh = render_markdown(review, lang="zh")
    en = render_markdown(review, lang="en")
    assert "事故复盘" in zh and "静默窗口" in zh
    assert "Incident Review" in en and "MTTR **150 min**" in en
    headers, rows = parse_rows("time,kind,text\n10:00,impact,x\n"
                               "10:05,alert,y\n10:10,action,z\n"
                               "10:30,recovery,ok\n")
    clean = render_markdown(review_incident(headers, rows), lang="en")
    assert "inside" in clean and "bounds" in clean


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ["incidentreview", "-f", str(DEMO)])
    assert res.exit_code == 0, res.output
    assert "事故复盘" in res.output
    res = runner.invoke(cli, ["incidentreview", "-f", str(DEMO),
                              "--format", "json"])
    assert res.exit_code == 0 and '"mttr_min": 150' in res.output
    # demo tops out at medium -> gate passes
    res = runner.invoke(cli, ["incidentreview", "-f", str(DEMO),
                              "--fail-on-high"])
    assert res.exit_code == 0
    res = runner.invoke(cli, ["incidentreview", "--text",
                              "time,kind,text\n00:00,impact,x\n"
                              "02:00,alert,y",
                              "--fail-on-high"])
    assert res.exit_code == 1


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.incident_review.tools import (
        incident_review,
    )

    out = incident_review(DEMO.read_text(encoding="utf-8"), lang="en")
    assert "Incident Review" in out and "IR003" in out
    assert "must not be empty" in incident_review("  ")
    assert "bad input" in incident_review("time,kind,text\n02:00,boom,x")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.incident_review.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_review_and_health():
    client = _client()
    assert client.get("/api/incidentreview/health").status_code == 200
    resp = client.post("/api/incidentreview/review", json={
        "data_text": DEMO.read_text(encoding="utf-8"),
        "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["mttr_min"] == 150.0
    assert "Incident Review" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/incidentreview/review", json={
        "data_text": "time,kind,text\n02:00,boom,x"})
    assert resp.status_code == 400
