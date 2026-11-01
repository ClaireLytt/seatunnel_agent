"""Tests for the offboard_plan agent (planner / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.offboard_plan import (
    plan_offboard,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "offboardplan_demo" / "pipeline.sql"


def _sql() -> str:
    return DEMO.read_text(encoding="utf-8")


# ----------------------------------------------------------------- planner

def test_leaf_table_clear_to_stage():
    plan = plan_offboard(_sql(), "ads.final_report")
    assert not plan.blocked and plan.downstream == {}
    phases = [s.phase for s in plan.steps]
    assert phases == ["announce", "freeze", "freeze", "archive",
                      "archive", "drop"]
    (drop,) = [s for s in plan.steps if s.phase == "drop"]
    assert not drop.safe
    assert all(line.startswith("--") for line in drop.sql.splitlines())


def test_mid_table_blocked_with_consumers():
    plan = plan_offboard(_sql(), "dws.orders_daily")
    assert plan.blocked
    assert plan.downstream == {"ads.final_report": 1}
    assert plan.steps[0].action == "migrate_consumers"
    assert "ads.final_report" in plan.steps[0].detail


def test_archive_and_deprecation_templates():
    plan = plan_offboard(_sql(), "ads.final_report", grace_days=7,
                         archive_db="cold")
    text = "\n".join(s.sql for s in plan.steps)
    assert "CREATE TABLE cold.final_report_retired AS SELECT * " in text
    assert "'deprecated' = 'true'" in text
    assert "<DATE+7d>" in text


def test_bad_inputs():
    with pytest.raises(ValueError, match="not in the pasted"):
        plan_offboard(_sql(), "nope.table")
    with pytest.raises(ValueError, match="table"):
        plan_offboard(_sql(), "  ")
    with pytest.raises(ValueError, match="grace_days"):
        plan_offboard(_sql(), "ads.final_report", grace_days=-1)


# ------------------------------------------------------------------ report

def test_report_both_langs():
    blocked = render_markdown(plan_offboard(_sql(), "dws.orders_daily"),
                              lang="en")
    assert "BLOCKED" in blocked and "ads.final_report" in blocked
    zh = render_markdown(plan_offboard(_sql(), "ads.final_report"),
                         lang="zh")
    assert "下线方案" in zh and "可进入分阶段下线" in zh
    assert "```sql" in zh


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    args = ["offboardplan", "-f", str(DEMO), "-t", "ads.final_report"]
    res = runner.invoke(cli, args)
    assert res.exit_code == 0, res.output
    assert "下线方案" in res.output
    res = runner.invoke(cli, args + ["--format", "json"])
    assert res.exit_code == 0 and '"blocked": false' in res.output
    res = runner.invoke(cli, ["offboardplan", "-f", str(DEMO),
                              "-t", "dws.orders_daily",
                              "--fail-on-blocked"])
    assert res.exit_code == 1
    res = runner.invoke(cli, args + ["--fail-on-blocked"])
    assert res.exit_code == 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.offboard_plan.tools import (
        offboard_plan,
    )

    out = offboard_plan(_sql(), "dws.orders_daily", lang="en")
    assert "BLOCKED" in out and "Offboarding Plan" in out
    assert "must not be empty" in offboard_plan("  ", "t")
    assert "must not be empty" in offboard_plan(_sql(), " ")
    assert "bad input" in offboard_plan(_sql(), "nope.t")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.offboard_plan.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_plan_and_health():
    client = _client()
    assert client.get("/api/offboardplan/health").status_code == 200
    resp = client.post("/api/offboardplan/plan", json={
        "sql_text": _sql(), "table": "ads.final_report",
        "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["blocked"] is False
    assert "Offboarding Plan" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/offboardplan/plan", json={
        "sql_text": _sql(), "table": "nope.t"})
    assert resp.status_code == 400
