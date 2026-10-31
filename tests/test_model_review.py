"""Tests for the model_review agent (reviewer / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.model_review import (
    render_markdown,
    review_model,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "modelreview_demo" / "warehouse.sql"


def _codes(report):
    return {f.code for f in report.findings}


# ---------------------------------------------------------------- reviewer

def test_demo_fires_the_designed_codes():
    report = review_model(DEMO.read_text(encoding="utf-8"))
    assert _codes(report) == {"MR001", "MR002", "MR003", "MR004", "MR005"}
    assert report.roles == {"dim": 1, "fact": 3}
    assert report.counts()["high"] == 1


def test_clean_star_schema_has_no_findings():
    ddl = """
    CREATE TABLE dim.users (
      user_id BIGINT, user_name STRING
    ) STORED AS ORC;
    CREATE TABLE dwd.orders (
      order_id BIGINT, user_id BIGINT, amount DECIMAL(16,2)
    ) PARTITIONED BY (dt STRING) STORED AS ORC;
    CREATE TABLE dws.orders_daily (
      user_id BIGINT, gmv DECIMAL(18,2)
    ) PARTITIONED BY (dt STRING) STORED AS ORC;
    """
    assert review_model(ddl).findings == []


def test_mr007_fact_without_any_id():
    ddl = ("CREATE TABLE dwd.events (event_name STRING, val BIGINT) "
           "PARTITIONED BY (dt STRING)")
    report = review_model(ddl)
    assert "MR007" in _codes(report)


def test_mr006_wide_table_any_role():
    cols = ", ".join(f"c{i} STRING" for i in range(12))
    ddl = f"CREATE TABLE misc.flat ({cols})"
    report = review_model(ddl, wide_limit=10)
    (f,) = report.findings
    assert f.code == "MR006" and f.detail == "12"
    assert report.roles == {"other": 1}


def test_raw_layer_is_exempt():
    ddl = ("CREATE TABLE ods.raw_log (line STRING, remark STRING);"
           "CREATE TABLE stg.tmp_x (note_name STRING)")
    assert review_model(ddl).findings == []


def test_mr004_needs_two_facts():
    ddl = """
    CREATE TABLE dwd.a (x_id BIGINT, city STRING)
      PARTITIONED BY (dt STRING);
    CREATE TABLE dwd.b (y_id BIGINT, city STRING)
      PARTITIONED BY (dt STRING);
    """
    report = review_model(ddl)
    (f,) = [f for f in report.findings if f.code == "MR004"]
    assert f.detail == "city" and "dwd.a" in f.table and "dwd.b" in f.table


def test_bad_inputs():
    with pytest.raises(ValueError, match="empty"):
        review_model("  ")
    with pytest.raises(ValueError, match="no CREATE TABLE"):
        review_model("SELECT 1")
    with pytest.raises(ValueError, match="wide_limit"):
        review_model("CREATE TABLE t (a INT)", wide_limit=0)


# ------------------------------------------------------------------ report

def test_report_both_langs_and_clean():
    report = review_model(DEMO.read_text(encoding="utf-8"))
    zh = render_markdown(report, lang="zh")
    en = render_markdown(report, lang="en")
    assert "建模体检" in zh and "MR001" in zh
    assert "Model Review" in en and "dim.users" in en
    clean = render_markdown(
        review_model("CREATE TABLE dim.d (d_id BIGINT)"), lang="en")
    assert "star schema holds" in clean


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ["modelreview", "-f", str(DEMO)])
    assert res.exit_code == 0, res.output
    assert "建模体检" in res.output
    res = runner.invoke(cli, ["modelreview", "-f", str(DEMO),
                              "--format", "json"])
    assert res.exit_code == 0 and '"tables_total": 4' in res.output
    res = runner.invoke(cli, ["modelreview", "-f", str(DEMO),
                              "--fail-on-high"])
    assert res.exit_code == 1
    res = runner.invoke(cli, ["modelreview", "--text",
                              "CREATE TABLE dim.d (d_id BIGINT)",
                              "--fail-on-high"])
    assert res.exit_code == 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.model_review.tools import model_review

    out = model_review(DEMO.read_text(encoding="utf-8"), lang="en")
    assert "MR001" in out and "dim.users" in out
    assert "must not be empty" in model_review("  ")
    assert "bad input" in model_review("SELECT 1")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.model_review.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_review_and_health():
    client = _client()
    assert client.get("/api/modelreview/health").status_code == 200
    resp = client.post("/api/modelreview/review",
                       json={"sql_text": DEMO.read_text(encoding="utf-8"),
                             "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["counts"]["high"] == 1
    assert "Model Review" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/modelreview/review",
                       json={"sql_text": "SELECT 1"})
    assert resp.status_code == 400
