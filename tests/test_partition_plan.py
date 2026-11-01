"""Tests for the partition_plan agent (planner / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.partition_plan import (
    plan_partitions,
    render_markdown,
)
from seatunnel_agent.agents.data.sample_profile import parse_rows

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "partitionplan_demo"


def _demo_plan():
    headers, rows = parse_rows(
        (DEMO / "sample.csv").read_text(encoding="utf-8"))
    return plan_partitions(
        headers, rows,
        (DEMO / "queries.sql").read_text(encoding="utf-8"))


# ----------------------------------------------------------------- planner

def test_demo_recommends_the_date_column():
    plan = _demo_plan()
    assert plan.queries_total == 5
    assert plan.partition_by == "PARTITIONED BY (order_date)"
    best = plan.candidates[0]
    assert best.column == "order_date"
    assert best.verdict == "recommend" and best.reason == "time_filtered"
    assert best.filter_hits == 2


def test_pp003_counts_unprunable_queries():
    plan = _demo_plan()
    (f,) = [f for f in plan.findings if f.code == "PP003"]
    assert f.detail == "1"                    # the GROUP BY-only query


def test_single_value_and_high_cardinality_unsuitable():
    csv = "k,v\n" + "\n".join(f"same,{i}" for i in range(10))
    headers, rows = parse_rows(csv)
    plan = plan_partitions(headers, rows, "SELECT v FROM t WHERE k = 'x'")
    by = {c.column: c for c in plan.candidates}
    assert by["k"].verdict == "unsuitable"
    assert by["k"].reason == "single_value"


def test_hot_id_column_gets_buckets_and_pp002():
    rows = ["user_id,note"] + [f"{i},x" for i in range(6000)]
    headers, parsed = parse_rows("\n".join(rows))
    plan = plan_partitions(headers, parsed,
                           "SELECT note FROM t WHERE user_id = 5")
    by = {c.column: c for c in plan.candidates}
    assert by["user_id"].verdict == "unsuitable"
    assert by["user_id"].reason == "too_many"
    assert plan.cluster_by == "CLUSTERED BY (user_id) INTO 8 BUCKETS"
    codes = {f.code for f in plan.findings}
    assert "PP001" in codes and "PP002" in codes
    assert plan.partition_by == ""


def test_bad_inputs():
    headers, rows = parse_rows("a,b\n1,2\n")
    with pytest.raises(ValueError, match="cannot parse"):
        plan_partitions(headers, rows, "SELECT FROM WHERE")
    with pytest.raises(ValueError, match="no statements"):
        plan_partitions(headers, rows, "-- just a comment")
    with pytest.raises(ValueError, match="sample needs"):
        plan_partitions([], [], "SELECT 1")


# ------------------------------------------------------------------ report

def test_report_both_langs():
    plan = _demo_plan()
    zh = render_markdown(plan, lang="zh")
    en = render_markdown(plan, lang="en")
    assert "分区键选型" in zh and "PARTITIONED BY (order_date)" in zh
    assert "Partition Plan" in en and "canonical key" in en


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    args = ["partitionplan", "-f", str(DEMO / "sample.csv"),
            "-q", str(DEMO / "queries.sql")]
    res = runner.invoke(cli, args)
    assert res.exit_code == 0, res.output
    assert "分区键选型" in res.output
    res = runner.invoke(cli, args + ["--format", "json"])
    assert res.exit_code == 0 and '"queries_total": 5' in res.output
    # demo has only the low PP003 -> the medium gate passes
    res = runner.invoke(cli, args + ["--fail-on-medium"])
    assert res.exit_code == 0


def test_cli_fail_on_medium(tmp_path):
    from seatunnel_agent.cli import cli

    sample = tmp_path / "s.csv"
    sample.write_text("user_id,note\n" +
                      "\n".join(f"{i},x" for i in range(6000)),
                      encoding="utf-8")
    queries = tmp_path / "q.sql"
    queries.write_text("SELECT note FROM t WHERE user_id = 5",
                       encoding="utf-8")
    res = CliRunner().invoke(cli, ["partitionplan", "-f", str(sample),
                                   "-q", str(queries),
                                   "--fail-on-medium"])
    assert res.exit_code == 1


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.partition_plan.tools import (
        partition_plan,
    )

    out = partition_plan(
        (DEMO / "sample.csv").read_text(encoding="utf-8"),
        (DEMO / "queries.sql").read_text(encoding="utf-8"), lang="en")
    assert "PARTITIONED BY (order_date)" in out
    assert "required" in partition_plan("", "SELECT 1")
    assert "bad input" in partition_plan("a,b\n1,2", "SELECT FROM")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.partition_plan.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_plan_and_health():
    client = _client()
    assert client.get("/api/partitionplan/health").status_code == 200
    resp = client.post("/api/partitionplan/plan", json={
        "data_text": (DEMO / "sample.csv").read_text(encoding="utf-8"),
        "queries_text": (DEMO / "queries.sql").read_text(encoding="utf-8"),
        "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["partition_by"] == "PARTITIONED BY (order_date)"
    assert "Partition Plan" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/partitionplan/plan", json={
        "data_text": "a,b\n1,2", "queries_text": "SELECT FROM"})
    assert resp.status_code == 400
