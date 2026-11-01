"""Tests for the compact_plan agent (planner / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.compact_plan import (
    plan_compaction,
    render_markdown,
)
from seatunnel_agent.agents.data.sample_profile import parse_rows

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "compactplan_demo" / "files.csv"


def _demo_plan(**kw):
    headers, rows = parse_rows(DEMO.read_text(encoding="utf-8"))
    return plan_compaction(headers, rows, **kw)


# ----------------------------------------------------------------- planner

def test_demo_candidates_ranked_by_files_freed():
    plan = _demo_plan()
    assert plan.partitions == 7 and plan.files_total == 3802
    assert plan.files_freed == 3758
    assert [c.partition for c in plan.candidates[:3]] == \
        ["dt=2026-10-28", "dt=2026-10-29", "dt=2026-10-30"]
    top = plan.candidates[0]
    assert top.files_after == 12 and top.files_freed == 1438


def test_tiny_but_few_and_healthy_partitions_left_alone():
    plan = _demo_plan()
    tables = {c.table for c in plan.candidates}
    # dim.users: avg 4.5MB but only 4 files; dws: avg 52MB — both skipped
    assert "dim.users" not in tables and "dws.orders_daily" not in tables


def test_findings_graded():
    plan = _demo_plan()
    codes = {(f.code, f.table) for f in plan.findings}
    assert ("CP001", "ods.click_log") in codes
    assert ("CP001", "dwd.orders") in codes
    assert ("CP002", "ods.click_log") in codes
    cp2 = [f for f in plan.findings if f.code == "CP002"]
    assert len(cp2) == 2                      # the two 1000+ partitions
    assert all(f.severity == "high" for f in cp2)


def test_thresholds_configurable():
    headers, rows = parse_rows(DEMO.read_text(encoding="utf-8"))
    plan = plan_compaction(headers, rows, small_mb=1.0)
    assert plan.candidates == []              # nothing averages under 1MB
    assert all(f.code != "CP001" for f in plan.findings)


def test_bad_inputs():
    headers, rows = parse_rows("table,partition\nt,p\n")
    with pytest.raises(ValueError, match="missing"):
        plan_compaction(headers, rows)
    h2, r2 = parse_rows(DEMO.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="small_mb"):
        plan_compaction(h2, r2, small_mb=300, target_mb=256)
    h3, r3 = parse_rows("table,partition,file_count,total_mb\nt,p,-1,5\n")
    with pytest.raises(ValueError, match="negative"):
        plan_compaction(h3, r3)


# ------------------------------------------------------------------ report

def test_report_both_langs_and_clean():
    plan = _demo_plan()
    zh = render_markdown(plan, lang="zh")
    en = render_markdown(plan, lang="en")
    assert "小文件治理" in zh and "CONCATENATE" in zh
    assert "Compaction Plan" in en and "NameNode pressure point" in en
    headers, rows = parse_rows(
        "table,partition,file_count,total_mb\nt,p,4,900\n")
    clean = render_markdown(plan_compaction(headers, rows), lang="en")
    assert "No partition needs compaction" in clean


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ["compactplan", "-f", str(DEMO)])
    assert res.exit_code == 0, res.output
    assert "小文件治理" in res.output
    res = runner.invoke(cli, ["compactplan", "-f", str(DEMO),
                              "--format", "json"])
    assert res.exit_code == 0 and '"files_freed": 3758' in res.output
    res = runner.invoke(cli, ["compactplan", "-f", str(DEMO),
                              "--fail-on-high"])
    assert res.exit_code == 1
    res = runner.invoke(cli, ["compactplan", "--text",
                              "table,partition,file_count,total_mb\n"
                              "t,p,4,900",
                              "--fail-on-high"])
    assert res.exit_code == 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.compact_plan.tools import compact_plan

    out = compact_plan(DEMO.read_text(encoding="utf-8"), lang="en")
    assert "CP002" in out and "ods.click_log" in out
    assert "must not be empty" in compact_plan("  ")
    assert "bad input" in compact_plan("table,partition\nt,p")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.compact_plan.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_plan_and_health():
    client = _client()
    assert client.get("/api/compactplan/health").status_code == 200
    resp = client.post("/api/compactplan/plan", json={
        "data_text": DEMO.read_text(encoding="utf-8"),
        "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["files_freed"] == 3758
    assert "Compaction Plan" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/compactplan/plan",
                       json={"data_text": "table,partition\nt,p"})
    assert resp.status_code == 400
