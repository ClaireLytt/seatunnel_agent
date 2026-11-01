"""Tests for the dup_pipeline agent (detector / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.dup_pipeline import (
    detect_dup_pipelines,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "duppipeline_demo" / "pipelines.sql"


def _by_code(report):
    out: dict[str, list] = {}
    for f in report.findings:
        out.setdefault(f.code, []).append(f)
    return out


# ---------------------------------------------------------------- detector

def test_demo_fires_all_codes():
    report = detect_dup_pipelines(DEMO.read_text(encoding="utf-8"))
    by = _by_code(report)
    assert set(by) == {"DP001", "DP002", "DP003"}
    assert report.targets_total == 4 and report.sources_total == 2


def test_dp001_high_needs_expression_overlap():
    report = detect_dup_pipelines(DEMO.read_text(encoding="utf-8"))
    dp001 = sorted(_by_code(report)["DP001"], key=lambda f: f.severity)
    assert dp001[0].severity == "high"       # twin dws aggregates
    assert dp001[0].overlap == 1.0
    assert set(dp001[0].tables) == {"dws.orders_daily",
                                    "dws.order_summary_bi"}
    assert dp001[1].severity == "medium"     # same input, different math
    assert set(dp001[1].tables) == {"ads.order_counts",
                                    "ads.user_gmv_rank"}


def test_dp002_subset_direction():
    sql = """
    INSERT INTO wide.t SELECT a.x, b.y FROM s1 a JOIN s2 b ON a.i = b.i;
    INSERT INTO narrow.t SELECT x FROM s1;
    """
    report = detect_dup_pipelines(sql)
    (f,) = _by_code(report)["DP002"]
    assert f.tables == ["narrow.t", "wide.t"]   # subset listed first
    assert f.detail == "s1"


def test_dp003_fanout_threshold():
    sql = ";".join(f"INSERT INTO t{i} SELECT x FROM hot" for i in range(3))
    report = detect_dup_pipelines(sql, fanout=3)
    dp3 = _by_code(report)["DP003"]
    assert len(dp3) == 1 and dp3[0].detail == "hot"
    report = detect_dup_pipelines(sql, fanout=4)
    assert "DP003" not in _by_code(report)


def test_clean_pipelines_no_findings():
    sql = """
    INSERT INTO a.t SELECT x FROM s1;
    INSERT INTO b.t SELECT y FROM s2;
    """
    assert detect_dup_pipelines(sql).findings == []


def test_bad_inputs():
    with pytest.raises(ValueError, match="empty"):
        detect_dup_pipelines("  ")
    with pytest.raises(ValueError, match="no write statements"):
        detect_dup_pipelines("SELECT 1")
    with pytest.raises(ValueError, match="fanout"):
        detect_dup_pipelines("INSERT INTO t SELECT x FROM s", fanout=1)


# ------------------------------------------------------------------ report

def test_report_both_langs_and_clean():
    report = detect_dup_pipelines(DEMO.read_text(encoding="utf-8"))
    zh = render_markdown(report, lang="zh")
    en = render_markdown(report, lang="en")
    assert "重复建设检测" in zh and "DP001" in zh
    assert "Duplicate Pipelines" in en and "built twice" in en
    clean = render_markdown(
        detect_dup_pipelines("INSERT INTO t SELECT x FROM s"), lang="en")
    assert "No duplicate builds" in clean


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ["duppipeline", "-f", str(DEMO)])
    assert res.exit_code == 0, res.output
    assert "重复建设检测" in res.output
    res = runner.invoke(cli, ["duppipeline", "-f", str(DEMO),
                              "--format", "json"])
    assert res.exit_code == 0 and '"targets_total": 4' in res.output
    res = runner.invoke(cli, ["duppipeline", "-f", str(DEMO),
                              "--fail-on-high"])
    assert res.exit_code == 1
    res = runner.invoke(cli, ["duppipeline", "--text",
                              "INSERT INTO t SELECT x FROM s",
                              "--fail-on-high"])
    assert res.exit_code == 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.dup_pipeline.tools import dup_pipeline

    out = dup_pipeline(DEMO.read_text(encoding="utf-8"), lang="en")
    assert "DP001" in out and "dws.orders_daily" in out
    assert "must not be empty" in dup_pipeline("  ")
    assert "bad input" in dup_pipeline("SELECT 1")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.dup_pipeline.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_detect_and_health():
    client = _client()
    assert client.get("/api/duppipeline/health").status_code == 200
    resp = client.post("/api/duppipeline/detect",
                       json={"sql_text": DEMO.read_text(encoding="utf-8"),
                             "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["counts"]["high"] == 1
    assert "Duplicate Pipelines" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/duppipeline/detect",
                       json={"sql_text": "SELECT 1"})
    assert resp.status_code == 400
