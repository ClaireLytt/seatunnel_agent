"""Tests for the schedule-advisor agent (54): advisor, report, API, CLI."""

from __future__ import annotations

import json
from pathlib import Path

from seatunnel_agent.agents.data.schedule_advisor import (
    advise_schedule,
    parse_plan,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "scheduleadvisor_demo" / "plan.json"
PLAN = DEMO.read_text("utf-8")


def _advise(text: str = PLAN):
    return advise_schedule(parse_plan(text))


# ── advisor ──────────────────────────────────────────────────────────

def test_demo_timeline_and_margin():
    result = _advise()
    assert result.finish == "04:05"
    assert result.margin_min == 175.0
    assert result.critical_path == ["ods_load", "dwd_orders",
                                    "dws_orders_daily", "ads_board_kpi"]
    assert result.peak_parallelism == 3


def test_slack_relative_to_sla_task():
    result = _advise()
    by_name = {t.name: t for t in result.tasks}
    assert by_name["dim_users"].slack_min == 35.0
    assert by_name["dwd_orders"].slack_min == 0.0
    # tasks off the SLA ancestry carry no slack figure
    assert by_name["dwd_click_log"].slack_min is None


def test_negative_margin_detected():
    plan = json.loads(PLAN)
    plan["sla"]["deadline"] = "03:00"
    result = _advise(json.dumps(plan))
    assert result.margin_min == -65.0
    md = render_markdown(result, lang="en")
    assert "MISSES THE SLA" in md


def test_default_sla_is_latest_finisher():
    plan = json.loads(PLAN)
    del plan["sla"]
    result = _advise(json.dumps(plan))
    assert result.sla_task == "ads_board_kpi"
    assert result.margin_min is None


def test_cycle_rejected():
    import pytest

    plan = {"tasks": [
        {"name": "a", "duration_min": 10, "deps": ["b"]},
        {"name": "b", "duration_min": 10, "deps": ["a"]}]}
    with pytest.raises(ValueError):
        _advise(json.dumps(plan))


def test_parse_rejects_bad_plans():
    import pytest

    with pytest.raises(ValueError):
        parse_plan("  ")
    with pytest.raises(ValueError):
        parse_plan('{"tasks": []}')
    with pytest.raises(ValueError):
        parse_plan('{"tasks": [{"name": "a", "duration_min": 0}]}')
    with pytest.raises(ValueError):
        parse_plan('{"tasks": [{"name": "a", "duration_min": 5, '
                   '"deps": ["ghost"]}]}')


def test_report_both_langs():
    result = _advise()
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "调度窗口建议" in zh and "关键路径" in zh
    assert "Schedule Advice" in en and "Critical path" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.schedule_advisor import api as sa_api

    app = FastAPI()
    app.include_router(sa_api.router)
    return TestClient(app)


def test_api_advise_inline():
    res = _client().post("/api/scheduleadvisor/advise",
                         json={"plan_text": PLAN, "report": True,
                               "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["finish"] == "04:05"
    assert "Schedule Advice" in body["report"]


def test_api_bad_plan_400():
    res = _client().post("/api/scheduleadvisor/advise",
                         json={"plan_text": "not json"})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("SCHEDULEADVISOR_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/scheduleadvisor/advise",
                         json={"plan_file": str(DEMO)})
    assert res.status_code == 200
    bad = _client().post("/api/scheduleadvisor/advise",
                         json={"plan_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.schedule_advisor import advisor_llm

    monkeypatch.setattr(advisor_llm, "schedule_note",
                        lambda result, lang="zh": "SCHED-NOTE")
    res = _client().post("/api/scheduleadvisor/advise",
                         json={"plan_text": PLAN, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["schedule_note"] == "SCHED-NOTE"


def test_api_health():
    body = _client().get("/api/scheduleadvisor/health").json()
    assert body == {"status": "ok", "agent": "schedule_advisor"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_scheduleadvisor_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, ["scheduleadvisor", "-f", str(DEMO),
                                   "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "调度窗口建议" in res.output and "ads_board_kpi" in res.output


def test_cli_fail_on_breach_gate():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    plan = json.loads(PLAN)
    plan["sla"]["deadline"] = "03:00"
    res = CliRunner().invoke(cli, ["scheduleadvisor", "--text",
                                   json.dumps(plan), "--fail-on-breach"])
    assert res.exit_code == 1
    ok = CliRunner().invoke(cli, ["scheduleadvisor", "-f", str(DEMO),
                                  "--fail-on-breach"])
    assert ok.exit_code == 0, ok.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "schedule_advisor" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.schedule_advisor.tools import (
        schedule_advisor,
    )

    out = schedule_advisor(PLAN, lang="en")
    assert "Schedule Advice" in out and "ods_load" in out
    assert "must not be empty" in schedule_advisor("  ")
    assert "bad input" in schedule_advisor("not json")
