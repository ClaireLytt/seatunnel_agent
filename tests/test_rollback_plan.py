"""Tests for the rollback-plan agent (66): planner, report, API, CLI."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.agents.data.rollback_plan import (
    plan_rollback,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "rollbackplan_demo" / "pipeline.sql"
SQL = DEMO.read_text("utf-8")


def _plan(table: str = "dwd.orders", **kw):
    kw.setdefault("partitions", ["dt=2026-10-30"])
    return plan_rollback(SQL, table, **kw)


# ── planner ──────────────────────────────────────────────────────────

def test_demo_levels_and_steps():
    plan = _plan(mode="snapshot", snapshot="snap_orders")
    assert plan.levels == 1
    assert plan.touched == ["dwd.orders", "dws.orders_daily"]
    actions = [(s.level, s.action, s.table) for s in plan.steps]
    assert actions[0] == (0, "restore", "dwd.orders")
    assert actions[1] == (1, "rerun", "dws.orders_daily")
    assert (2, "verify", "dwd.orders") in actions
    assert (2, "verify", "dws.orders_daily") in actions


def test_snapshot_template_carries_partition_filter():
    plan = _plan(mode="snapshot", snapshot="snap_orders")
    restore = plan.steps[0].sql
    assert "INSERT OVERWRITE TABLE dwd.orders" in restore
    assert "snap_orders" in restore
    assert "dt = '2026-10-30'" in restore


def test_rerun_mode_emits_scheduler_hint():
    plan = _plan(mode="rerun")
    assert "clear + backfill dwd.orders" in plan.steps[0].sql


def test_root_from_ods_covers_whole_chain():
    plan = plan_rollback(SQL, "ods.orders_raw",
                         partitions=["dt=2026-10-30"])
    assert plan.levels == 2
    assert "dws.orders_daily" in plan.touched


def test_estimate_sums_level_maxima():
    plan = _plan(durations={"dwd.orders": 30, "dws.orders_daily": 90})
    assert plan.estimated_min == 120.0
    assert _plan().estimated_min is None


def test_leaf_table_has_no_reruns():
    plan = plan_rollback(SQL, "dws.orders_daily",
                         partitions=["dt=2026-10-30"])
    assert plan.levels == 0
    assert [s.action for s in plan.steps] == ["restore", "verify"]


def test_bad_inputs_rejected():
    import pytest

    with pytest.raises(ValueError):
        plan_rollback(SQL, "nope.missing")
    with pytest.raises(ValueError):
        plan_rollback(SQL, "dwd.orders", mode="teleport")
    with pytest.raises(ValueError):
        plan_rollback("  ", "dwd.orders")


def test_report_both_langs():
    plan = _plan(mode="snapshot", snapshot="snap_orders")
    zh = render_markdown(plan, lang="zh")
    en = render_markdown(plan, lang="en")
    assert "回滚编排" in zh and "层内可并行" in zh
    assert "Rollback Plan" in en and "parallel" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.rollback_plan import api as rb_api

    app = FastAPI()
    app.include_router(rb_api.router)
    return TestClient(app)


def test_api_plan_inline():
    res = _client().post("/api/rollbackplan/plan",
                         json={"sql_text": SQL, "table": "dwd.orders",
                               "partitions": ["dt=2026-10-30"],
                               "mode": "snapshot",
                               "snapshot": "snap_orders",
                               "durations": {"dws.orders_daily": 90},
                               "report": True, "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["touched"] == ["dwd.orders",
                                         "dws.orders_daily"]
    assert body["result"]["estimated_min"] == 90.0
    assert "Rollback Plan" in body["report"]


def test_api_unknown_table_400():
    res = _client().post("/api/rollbackplan/plan",
                         json={"sql_text": SQL, "table": "nope.missing"})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("ROLLBACKPLAN_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/rollbackplan/plan",
                         json={"sql_file": str(DEMO),
                               "table": "dwd.orders"})
    assert res.status_code == 200
    bad = _client().post("/api/rollbackplan/plan",
                         json={"sql_file": str(ROOT / "pyproject.toml"),
                               "table": "t"})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.rollback_plan import advisor_llm

    monkeypatch.setattr(advisor_llm, "rollback_note",
                        lambda plan, lang="zh": "RB-NOTE")
    res = _client().post("/api/rollbackplan/plan",
                         json={"sql_text": SQL, "table": "dwd.orders",
                               "llm": True, "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["rollback_note"] == "RB-NOTE"


def test_api_health():
    body = _client().get("/api/rollbackplan/health").json()
    assert body == {"status": "ok", "agent": "rollback_plan"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_rollbackplan_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "rollbackplan", "-f", str(DEMO), "-t", "dwd.orders",
        "-p", "dt=2026-10-30", "--mode", "snapshot",
        "--snapshot", "snap_orders", "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "回滚编排" in res.output and "dws.orders_daily" in res.output


def test_cli_unknown_table_usage_error():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "rollbackplan", "-f", str(DEMO), "-t", "nope.missing"])
    assert res.exit_code == 2


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "rollback_plan" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.rollback_plan.tools import (
        rollback_plan,
    )

    out = rollback_plan(SQL, "dwd.orders", partitions="dt=2026-10-30",
                        lang="en")
    assert "Rollback Plan" in out and "dws.orders_daily" in out
    assert "must not be empty" in rollback_plan("  ", "t")
    assert "must not be empty" in rollback_plan(SQL, " ")
    assert "bad input" in rollback_plan(SQL, "nope.missing")
