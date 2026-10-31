"""Tests for the sql_diff agent (differ / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.sql_diff import diff_sql, render_markdown

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "sqldiff_demo"

OLD = """
INSERT INTO dws.orders_daily
SELECT o.order_date, o.user_id, SUM(o.amount) AS gmv, COUNT(*) AS order_cnt
FROM dwd.orders o
JOIN dim.users u ON o.user_id = u.user_id
WHERE o.order_date >= '2026-01-01'
GROUP BY o.order_date, o.user_id;
"""

NEW = """
INSERT OVERWRITE TABLE dws.orders_daily
SELECT o.order_date, o.user_id, SUM(o.pay_amount) AS gmv
FROM dwd.orders o
WHERE o.order_date >= '2026-01-01' AND o.status = 'PAID'
GROUP BY o.order_date, o.user_id;
"""


def _kinds(report):
    return {f.kind for f in report.findings}


# ------------------------------------------------------------------ differ

def test_diff_grades_the_demo_changes():
    report = diff_sql(OLD, NEW)
    kinds = _kinds(report)
    assert {"write_mode_changed", "column_removed", "column_expr_changed",
            "source_removed", "filter_changed"} <= kinds
    counts = report.counts()
    assert counts["breaking"] == 2 and counts["risk"] == 3


def test_formatting_aliases_ordering_never_count():
    old = "insert into t select a,   b as bb from s where a>1"
    new = "INSERT INTO t\nSELECT a,\n  b AS bb\nFROM s\nWHERE a > 1"
    assert diff_sql(old, new).identical


def test_statement_added_and_removed():
    old = "INSERT INTO a SELECT x FROM s; INSERT INTO b SELECT x FROM s"
    new = "INSERT INTO a SELECT x FROM s; INSERT INTO c SELECT x FROM s"
    report = diff_sql(old, new)
    by_kind = {f.kind: f for f in report.findings}
    assert by_kind["statement_removed"].target == "b"
    assert by_kind["statement_removed"].severity == "breaking"
    assert by_kind["statement_added"].target == "c"
    assert by_kind["statement_added"].severity == "info"


def test_column_added_and_aggregation_changed():
    old = "INSERT INTO t SELECT a, SUM(v) AS s FROM x GROUP BY a"
    new = "INSERT INTO t SELECT a, b, SUM(v) AS s FROM x GROUP BY a, b"
    kinds = _kinds(diff_sql(old, new))
    assert "column_added" in kinds and "aggregation_changed" in kinds


def test_source_added_join_kind():
    old = "INSERT INTO t SELECT a FROM x"
    new = "INSERT INTO t SELECT a FROM x LEFT JOIN y ON x.id = y.id"
    report = diff_sql(old, new)
    (f,) = [f for f in report.findings if f.kind == "source_added"]
    assert f.subject == "y" and f.new == "left"


def test_bare_selects_pair_by_position():
    report = diff_sql("SELECT a FROM t", "SELECT a, b FROM t")
    (f,) = report.findings
    assert f.kind == "column_added" and f.target == "<select#1>"


def test_select_star_warns():
    report = diff_sql("INSERT INTO t SELECT * FROM s",
                      "INSERT INTO t SELECT * FROM s")
    assert report.identical
    assert any("SELECT *" in w for w in report.warnings)


def test_bad_inputs():
    with pytest.raises(ValueError, match="empty"):
        diff_sql("  ", "SELECT 1")
    with pytest.raises(ValueError, match="cannot parse"):
        diff_sql("INSERT INTO t SELECT FROM WHERE", "SELECT 1")


# ------------------------------------------------------------------ report

def test_report_both_langs_and_identical():
    report = diff_sql(OLD, NEW)
    zh = render_markdown(report, lang="zh")
    en = render_markdown(report, lang="en")
    assert "SQL 语义对比" in zh and "dws.orders_daily" in zh
    assert "SQL Semantic Diff" in en and "output column dropped" in en
    same = render_markdown(diff_sql("SELECT 1", "SELECT 1"), lang="en")
    assert "No semantic difference" in same


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    old, new = str(DEMO / "old.sql"), str(DEMO / "new.sql")
    res = runner.invoke(cli, ["sqldiff", "--old", old, "--new", new])
    assert res.exit_code == 0, res.output
    assert "SQL 语义对比" in res.output
    res = runner.invoke(cli, ["sqldiff", "--old", old, "--new", new,
                              "--format", "json"])
    assert res.exit_code == 0 and '"identical": false' in res.output
    res = runner.invoke(cli, ["sqldiff", "--old", old, "--new", new,
                              "--fail-on-breaking"])
    assert res.exit_code == 1
    res = runner.invoke(cli, ["sqldiff", "--old", old, "--new", old,
                              "--fail-on-breaking"])
    assert res.exit_code == 0


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.sql_diff.tools import sql_diff

    out = sql_diff(OLD, NEW, lang="en")
    assert "dws.orders_daily" in out and "flipped" in out
    assert "required" in sql_diff("", NEW)
    assert "bad input" in sql_diff("INSERT INTO t SELECT FROM", NEW)


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.sql_diff.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_diff_and_health():
    client = _client()
    assert client.get("/api/sqldiff/health").status_code == 200
    resp = client.post("/api/sqldiff/diff",
                       json={"old_text": OLD, "new_text": NEW,
                             "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["counts"]["breaking"] == 2
    assert "SQL Semantic Diff" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/sqldiff/diff",
                       json={"old_text": "INSERT INTO t SELECT FROM",
                             "new_text": "SELECT 1"})
    assert resp.status_code == 400
