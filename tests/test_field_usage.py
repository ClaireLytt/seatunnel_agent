"""Tests for the field_usage agent (analyzer / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.field_usage import (
    analyze_usage,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "fieldusage_demo"


def _demo_report():
    return analyze_usage(
        (DEMO / "tables.sql").read_text(encoding="utf-8"),
        (DEMO / "queries.sql").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- analyzer

def test_demo_counts_and_findings():
    report = _demo_report()
    assert report.queries_total == 4
    by = {t.table: t for t in report.tables}
    assert by["tmp.old_backup"].reads == 0
    assert by["dwd.orders"].reads == 4
    assert by["dwd.orders"].star_reads == 1
    assert by["dwd.orders"].columns["amount"] == 3
    assert by["dwd.orders"].unused == ["legacy_flag", "note"]
    codes = {(f.code, f.table) for f in report.findings}
    assert ("FU001", "tmp.old_backup") in codes
    assert ("FU002", "dim.users") in codes
    assert ("FU003", "dwd.orders") in codes
    # star-read table gets no FU002 (its column stats are blind)
    assert ("FU002", "dwd.orders") not in codes
    assert report.tables[0].table == "tmp.old_backup"   # coldest first


def test_alias_resolution_and_unqualified():
    ddl = "CREATE TABLE a.t (x INT, y INT); CREATE TABLE b.t (x INT)"
    queries = """
    SELECT q.x FROM a.t q;
    SELECT y FROM a.t;
    SELECT x FROM a.t JOIN b.t ON a.t.y = b.t.x;
    """
    report = analyze_usage(ddl, queries)
    by = {t.table: t for t in report.tables}
    assert by["a.t"].columns["x"] == 1        # qualified via alias
    assert by["a.t"].columns["y"] == 1        # unqualified, single source
    assert report.unresolved_refs >= 1        # ambiguous bare x


def test_top_columns_ranked():
    report = _demo_report()
    assert report.top_columns[0] == ("dwd.orders.amount", 3)


def test_bad_inputs():
    with pytest.raises(ValueError, match="no CREATE TABLE"):
        analyze_usage("SELECT 1", "SELECT 1")
    ddl = "CREATE TABLE t (a INT)"
    with pytest.raises(ValueError, match="workload"):
        analyze_usage(ddl, "   ")
    with pytest.raises(ValueError, match="cannot parse"):
        analyze_usage(ddl, "SELECT FROM WHERE")


# ------------------------------------------------------------------ report

def test_report_both_langs_and_clean():
    report = _demo_report()
    zh = render_markdown(report, lang="zh")
    en = render_markdown(report, lang="en")
    assert "字段使用率盘点" in zh and "FU001" in zh
    assert "Field Usage" in en and "offboarding candidate" in en
    clean = render_markdown(
        analyze_usage("CREATE TABLE t (a INT)", "SELECT a FROM t"),
        lang="en")
    assert "earns its reads" in clean


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_gate():
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    args = ["fieldusage", "--ddl", str(DEMO / "tables.sql"),
            "-q", str(DEMO / "queries.sql")]
    res = runner.invoke(cli, args)
    assert res.exit_code == 0, res.output
    assert "字段使用率盘点" in res.output
    res = runner.invoke(cli, args + ["--format", "json"])
    assert res.exit_code == 0 and '"queries_total": 4' in res.output
    res = runner.invoke(cli, args + ["--fail-on-unused"])
    assert res.exit_code == 1
    assert "tmp.old_backup" in res.output


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.field_usage.tools import field_usage

    out = field_usage((DEMO / "tables.sql").read_text(encoding="utf-8"),
                      (DEMO / "queries.sql").read_text(encoding="utf-8"),
                      lang="en")
    assert "FU001" in out and "tmp.old_backup" in out
    assert "required" in field_usage("", "SELECT 1")
    assert "bad input" in field_usage("SELECT 1", "SELECT 1")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.field_usage.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_analyze_and_health():
    client = _client()
    assert client.get("/api/fieldusage/health").status_code == 200
    resp = client.post("/api/fieldusage/analyze", json={
        "ddl_text": (DEMO / "tables.sql").read_text(encoding="utf-8"),
        "queries_text": (DEMO / "queries.sql").read_text(encoding="utf-8"),
        "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["queries_total"] == 4
    assert "Field Usage" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/fieldusage/analyze", json={
        "ddl_text": "SELECT 1", "queries_text": "SELECT 1"})
    assert resp.status_code == 400
