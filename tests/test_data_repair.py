"""Tests for the data-repair agent (40): planner, report, API, CLI."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.agents.data.data_repair import (
    plan_repairs,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "examples" / "datarepair_demo" / "events.csv"
ORDERS = ROOT / "examples" / "sampleprofile_demo" / "orders.csv"
EVENTS_CSV = EVENTS.read_text("utf-8")
ORDERS_CSV = ORDERS.read_text("utf-8")


# ── planner ──────────────────────────────────────────────────────────

def test_dedup_actions_from_duplicates():
    plan = plan_repairs(EVENTS_CSV, table="dwd.pay_events", pk="event_id")
    kinds = [(a.kind, a.rationale.get("layer")) for a in plan.actions]
    assert ("dedup", "row") in kinds
    assert ("dedup", "pk") in kinds
    pk_action = next(a for a in plan.actions
                     if a.rationale.get("layer") == "pk")
    assert "PARTITION BY event_id" in pk_action.sql
    assert "dwd.pay_events" in pk_action.sql


def test_profile_driven_actions():
    plan = plan_repairs(ORDERS_CSV, table="ods.orders")
    kinds = {a.kind for a in plan.actions}
    # orders.csv carries mixed amount, date stragglers, case drift
    assert "format_fix" in kinds
    assert "standardize" in kinds
    std = next(a for a in plan.actions if a.kind == "standardize")
    assert std.column == "status"
    assert "LOWER(TRIM(status))" in std.sql


def test_null_backfill_action():
    csv = "id,v\n1,\n2,\n3,x\n4,\n"
    plan = plan_repairs(csv, table="t")
    backfill = next(a for a in plan.actions if a.kind == "null_backfill")
    assert backfill.column == "v"
    assert "COALESCE(v, <default_value>)" in backfill.sql


def test_numeric_cast_action():
    csv = 'price\n"1,200"\n"3,400"\n"5,600"\n'
    plan = plan_repairs(csv, table="t")
    cast = next(a for a in plan.actions if a.kind == "numeric_cast")
    assert "CAST(REPLACE" in cast.sql


def test_actions_sorted_by_severity():
    plan = plan_repairs(ORDERS_CSV, table="t", pk="order_id")
    sev = [a.severity for a in plan.actions]
    order = {"high": 0, "mid": 1, "low": 2}
    assert sev == sorted(sev, key=order.__getitem__)


def test_clean_rows_no_actions():
    plan = plan_repairs("id,v\n1,a\n2,b\n3,c\n", table="t", pk="id")
    assert plan.actions == []
    assert "clean" in render_markdown(plan, lang="en")


def test_unknown_pk_raises():
    import pytest

    with pytest.raises(ValueError):
        plan_repairs(EVENTS_CSV, pk="nope")


def test_report_both_langs():
    plan = plan_repairs(EVENTS_CSV, table="dwd.pay_events", pk="event_id")
    zh = render_markdown(plan, lang="zh")
    en = render_markdown(plan, lang="en")
    assert "一致性修复方案" in zh and "ROW_NUMBER" in zh
    assert "Consistency Repair Plan" in en and "dedup" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.data_repair import api as dr_api

    app = FastAPI()
    app.include_router(dr_api.router)
    return TestClient(app)


def test_api_plan_inline():
    res = _client().post("/api/datarepair/plan",
                         json={"data_text": EVENTS_CSV, "pk": "event_id",
                               "table": "dwd.pay_events", "report": True,
                               "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert any(a["kind"] == "dedup" for a in body["result"]["actions"])
    assert "Consistency Repair Plan" in body["report"]


def test_api_bad_key_400():
    res = _client().post("/api/datarepair/plan",
                         json={"data_text": EVENTS_CSV, "pk": "missing"})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("DATAREPAIR_API_ALLOWED_DIRS", str(EVENTS.parent))
    res = _client().post("/api/datarepair/plan",
                         json={"data_file": str(EVENTS)})
    assert res.status_code == 200
    bad = _client().post("/api/datarepair/plan",
                         json={"data_file": str(ROOT / "pyproject.toml")})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.data_repair import advisor_llm

    monkeypatch.setattr(advisor_llm, "repair_note",
                        lambda plan, lang="zh": "REPAIR-NOTE")
    res = _client().post("/api/datarepair/plan",
                         json={"data_text": EVENTS_CSV, "llm": True,
                               "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["repair_note"] == "REPAIR-NOTE"


def test_api_health():
    body = _client().get("/api/datarepair/health").json()
    assert body == {"status": "ok", "agent": "data_repair"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_datarepair_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "datarepair", "-f", str(EVENTS), "-t", "dwd.pay_events",
        "--pk", "event_id", "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "一致性修复方案" in res.output and "ROW_NUMBER" in res.output


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "data_repair" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.data_repair.tools import data_repair

    out = data_repair(EVENTS_CSV, table="dwd.pay_events",
                      pk="event_id", lang="en")
    assert "Consistency Repair Plan" in out and "ROW_NUMBER" in out
    assert "must not be empty" in data_repair("  ")
    assert "bad input" in data_repair(EVENTS_CSV, pk="nope")
