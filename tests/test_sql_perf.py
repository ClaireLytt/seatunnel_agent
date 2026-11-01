"""Deterministic core tests for the execution-plan analyzer."""

from __future__ import annotations

from pathlib import Path

import pytest

from seatunnel_agent.agents.data.sql_perf import (
    analyze,
    parse_plan,
    render_markdown,
)
from seatunnel_agent.agents.data.sql_perf.tools import sql_perf

DEMO = (Path(__file__).resolve().parents[1] / "examples" / "sqlperf_demo"
        / "plan.txt").read_text(encoding="utf-8")


def test_demo_plan_facts():
    report = parse_plan(DEMO)
    assert report.joins == {"SortMergeJoin": 1}
    assert report.exchanges == 3
    by = {s.table: s for s in report.scans}
    orders = by["ods.orders"]
    assert orders.columns == 4
    assert orders.partition_filters == ""          # full-partition read
    assert orders.pushed_filters == "IsNotNull(user_id)"
    users = by["ods.users"]
    assert "dt#14 = 2024-05-01" in (users.partition_filters or "")
    assert users.pushed_filters == ""              # cast blocked pushdown


def test_demo_findings():
    report = analyze(DEMO)
    codes = [(f.code, f.detail) for f in report.findings]
    assert ("PF002", "ods.orders") in codes        # empty PartitionFilters
    assert ("PF003", "ods.users") in codes         # pushdown missed
    assert any(c == "PF005" for c, _ in codes)     # SMJ broadcast hint
    # severity order: high first
    sevs = [f.severity for f in report.findings]
    assert sevs == sorted(sevs, key=("high", "medium", "info").index)
    assert report.counts()["high"] == 1


def test_cartesian_and_reshuffle_rules():
    plan = """
    CartesianProduct
    +- Exchange hashpartitioning(a#1, 200)
    +- Exchange hashpartitioning(a#1, 200)
    +- Exchange hashpartitioning(b#2, 200)
    +- Exchange hashpartitioning(b#2, 200)
    +- FileScan parquet db.t[a#1] PartitionFilters: [p], PushedFilters: [f]
    """
    report = analyze(plan)
    codes = {f.code for f in report.findings}
    assert "PF001" in codes            # cartesian
    assert "PF004" in codes            # 3 exchanges, 1 join
    assert "PF002" not in codes and "PF003" not in codes


def test_wide_scan_hint():
    cols = ",".join(f"c{i}#1{i}" for i in range(25))
    plan = f"FileScan parquet db.wide[{cols}] PartitionFilters: [p], PushedFilters: [f]"
    report = analyze(plan)
    assert any(f.code == "PF006" for f in report.findings)


def test_bad_inputs():
    with pytest.raises(ValueError, match="empty plan"):
        parse_plan("  ")
    with pytest.raises(ValueError, match="no plan operators"):
        parse_plan("SELECT * FROM t WHERE dt = '2024-05-01'")


def test_report_zh_en_and_tool():
    report = analyze(DEMO)
    zh = render_markdown(report, lang="zh")
    en = render_markdown(report, lang="en")
    assert "执行计划分析" in zh and "分区裁剪" not in zh  # section名为扫描明细
    assert "扫描明细" in zh and "处方" in zh
    assert "Execution Plan Analysis" in en and "what to do" in en
    assert "`ods.orders`" in en
    md = sql_perf(DEMO, lang="en")
    assert "PF002" in md
    assert "must not be empty" in sql_perf(" ")
    assert "bad input" in sql_perf("just some prose")


def test_api_before_plan_diff():
    """before_text adds the diff; an unparseable before plan is a 400."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.sql_perf import api as sp_api

    optimized = (Path(__file__).resolve().parents[1] / "examples"
                 / "sqlperf_demo" / "plan_optimized.txt"
                 ).read_text(encoding="utf-8")
    app = FastAPI()
    app.include_router(sp_api.router)
    client = TestClient(app)
    res = client.post("/api/sqlperf/analyze", json={
        "text": optimized, "before_text": DEMO, "report": True,
        "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    resolved = {f["code"] for f in body["result"]["diff"]["resolved"]}
    assert "PF002" in resolved and "Plan Diff" in body["report"]
    res = client.post("/api/sqlperf/analyze", json={
        "text": optimized, "before_text": "just some prose"})
    assert res.status_code == 400 and "before plan" in res.text


def test_single_partition_exchange_pf007():
    plan = (
        "== Physical Plan ==\n"
        "+- Sort [amount ASC NULLS FIRST], true, 0\n"
        "   +- Exchange rangepartitioning(amount ASC, 1), "
        "ENSURE_REQUIREMENTS\n"
        "      +- Exchange SinglePartition, ENSURE_REQUIREMENTS\n"
        "         +- FileScan parquet ods.orders[amount] "
        "PartitionFilters: [isnotnull(dt), (dt = 1)], "
        "PushedFilters: [IsNotNull(amount)]\n")
    report = analyze(plan)
    assert report.single_exchanges == 1
    assert any(f.code == "PF007" and f.severity == "medium"
               for f in report.findings)
    # a broadcast SinglePartition exchange is not a funnel
    optimized = (Path(__file__).resolve().parents[1] / "examples"
                 / "sqlperf_demo" / "plan_optimized.txt"
                 ).read_text(encoding="utf-8")
    opt = analyze(optimized)
    assert opt.single_exchanges == 0
    assert not any(f.code == "PF007" for f in opt.findings)
