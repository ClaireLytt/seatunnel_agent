"""Tests for the watermark_plan agent (planner / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.sample_profile import parse_rows
from seatunnel_agent.agents.data.watermark_plan import (
    plan_watermark,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "watermarkplan_demo" / "events.csv"


def _demo_plan():
    headers, rows = parse_rows(DEMO.read_text(encoding="utf-8"))
    return plan_watermark(headers, rows)


# ----------------------------------------------------------------- planner

def test_demo_bound_and_metrics():
    plan = _demo_plan()
    assert plan.events == 20
    assert plan.out_of_order_share == pytest.approx(0.3)
    assert plan.p50_s == 2.0 and plan.p99_s == 31.0
    assert plan.max_s == 7783.0
    assert plan.bound_s == 39                 # ceil(31 * 1.25)
    assert plan.residual_share == pytest.approx(0.05)
    assert "INTERVAL '39' SECOND" in plan.sql_clause
    assert "Duration.ofSeconds(39)" in plan.java_snippet


def test_straggler_excluded_from_bound():
    # without the exclusion, the 7783s straggler drags p99 to max at
    # n=20 and the bound explodes past 9000s (the rt_latency lesson)
    plan = _demo_plan()
    assert plan.bound_s < 100
    by = {f.code: f for f in plan.findings}
    assert by["WM003"].value == 1             # routed to the side output
    assert by["WM002"].severity == "medium"   # heavy tail named


def test_clock_skew_grading():
    plan = _demo_plan()
    (f,) = [f for f in plan.findings if f.code == "WM001"]
    assert f.severity == "high" and f.value == pytest.approx(0.05)
    csv = ("event_time,arrival_time\n"
           + "10:00:00,10:00:01\n" * 30
           + "10:00:05,10:00:04\n")
    headers, rows = parse_rows(csv)
    plan2 = plan_watermark(headers, rows)
    (f2,) = [f for f in plan2.findings if f.code == "WM001"]
    assert f2.severity == "medium"            # ~3% < 5%


def test_tight_stream_is_clean():
    csv = "event_time,arrival_time\n" + "".join(
        f"10:00:{i:02d},10:00:{i + 1:02d}\n" for i in range(20))
    headers, rows = parse_rows(csv)
    plan = plan_watermark(headers, rows)
    assert plan.findings == [] and plan.bound_s == 2


def test_bad_inputs():
    headers, rows = parse_rows("event_time,arrival_time\n"
                               "10:00:00,10:00:01\n")
    with pytest.raises(ValueError, match="at least two"):
        plan_watermark(headers, rows)
    h2, r2 = parse_rows("event_time\n10:00:00\n10:00:01\n")
    with pytest.raises(ValueError, match="missing"):
        plan_watermark(h2, r2)
    h3, r3 = parse_rows("event_time,arrival_time\n"
                        "10:00:00,10:00:01\n"
                        "2026-10-30T10:00:02,2026-10-30T10:00:03\n")
    with pytest.raises(ValueError, match="mixes HH:MM"):
        plan_watermark(h3, r3)


# ------------------------------------------------------------------ report

def test_report_both_langs_and_clean():
    plan = _demo_plan()
    zh = render_markdown(plan, lang="zh")
    en = render_markdown(plan, lang="en")
    assert "水位线选型" in zh and "39 秒" in zh
    assert "Watermark Plan" in en and "```java" in en
    csv = "event_time,arrival_time\n" + "".join(
        f"10:00:{i:02d},10:00:{i + 1:02d}\n" for i in range(10))
    headers, rows = parse_rows(csv)
    clean = render_markdown(plan_watermark(headers, rows), lang="en")
    assert "tight" in clean


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ["watermarkplan", "-f", str(DEMO)])
    assert res.exit_code == 0, res.output
    assert "水位线选型" in res.output
    res = runner.invoke(cli, ["watermarkplan", "-f", str(DEMO),
                              "--format", "json"])
    assert res.exit_code == 0 and '"bound_s": 39' in res.output
    res = runner.invoke(cli, ["watermarkplan", "-f", str(DEMO),
                              "--fail-on-high"])
    assert res.exit_code == 1                 # WM001 high in the demo
    res = runner.invoke(cli, ["watermarkplan", "--text",
                              "event_time,arrival_time\n"
                              "10:00:00,10:00:01\n10:00:01,10:00:02",
                              "--fail-on-high"])
    assert res.exit_code == 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.watermark_plan.tools import (
        watermark_plan,
    )

    out = watermark_plan(DEMO.read_text(encoding="utf-8"), lang="en")
    assert "Watermark Plan" in out and "WM002" in out
    assert "must not be empty" in watermark_plan("  ")
    assert "bad input" in watermark_plan("event_time\n10:00\n10:01")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.watermark_plan.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_plan_and_health():
    client = _client()
    assert client.get("/api/watermarkplan/health").status_code == 200
    resp = client.post("/api/watermarkplan/plan", json={
        "data_text": DEMO.read_text(encoding="utf-8"),
        "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["bound_s"] == 39
    assert "Watermark Plan" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/watermarkplan/plan", json={
        "data_text": "event_time\n10:00\n10:01"})
    assert resp.status_code == 400
