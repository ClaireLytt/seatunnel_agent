"""Tests for the quality-trace agent (38): tracer, report, API, CLI."""

from __future__ import annotations

from pathlib import Path

from seatunnel_agent.agents.data.quality_trace import (
    build_graph_from_sql,
    render_markdown,
    trace_quality,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "qualitytrace_demo" / "pipeline.sql"
SQL = DEMO.read_text("utf-8")


def _trace(table="dws.orders_daily", column="gmv", symptom="gmv doubled",
           sql: str = SQL):
    graph, warnings = build_graph_from_sql(sql)
    return trace_quality(graph, warnings, table,
                         column=column, symptom=symptom)


# ── tracer ───────────────────────────────────────────────────────────

def test_demo_suspect_ranking():
    result = _trace()
    assert result.upstream_tables == 3
    names = [s.table for s in result.suspects]
    assert names[0] == "dwd.orders"          # 1 hop, on the taint path
    assert names[1] == "ods.orders_raw"      # 2 hops, on the taint path
    assert names[2] == "dim.users"           # 1 hop but off-path: dampened
    assert result.suspects[0].score > result.suspects[1].score


def test_taint_path_and_mutation_points():
    result = _trace()
    top = result.suspects[0]
    assert top.column_hits == ["amount"]
    assert any("SUM" in e for e in top.expressions)
    second = result.suspects[1]
    assert any("CAST" in e for e in second.expressions)


def test_verify_sql_uses_tainted_column():
    result = _trace()
    assert "MAX(amount)" in result.suspects[0].verify_sql
    assert "FROM dim.users" in result.suspects[-1].verify_sql


def test_trace_without_column_scores_by_distance():
    result = _trace(column="")
    by_name = {s.table: s for s in result.suspects}
    # without a column, both 1-hop ancestors tie on the distance term
    assert by_name["dwd.orders"].distance == 1
    assert by_name["dim.users"].distance == 1
    assert by_name["ods.orders_raw"].score < by_name["dim.users"].score


def test_unknown_table_raises():
    import pytest

    graph, warnings = build_graph_from_sql(SQL)
    with pytest.raises(ValueError):
        trace_quality(graph, warnings, "nope.missing")


def test_empty_sql_raises():
    import pytest

    with pytest.raises(ValueError):
        build_graph_from_sql("   ")


def test_table_without_upstream():
    result = _trace(table="ods.orders_raw", column="")
    assert result.upstream_tables == 0
    md = render_markdown(result, lang="en")
    assert "no upstream" in md


def test_report_both_langs():
    result = _trace()
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "质量根因追踪" in zh and "`dwd.orders`" in zh
    assert "Quality Root-Cause Trace" in en and "Verification SQL" in en
    assert "gmv doubled" in en


# ── API ──────────────────────────────────────────────────────────────

def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.quality_trace import api as qt_api

    app = FastAPI()
    app.include_router(qt_api.router)
    return TestClient(app)


def test_api_trace_inline():
    res = _client().post("/api/qualitytrace/trace",
                         json={"sql_text": SQL, "table": "dws.orders_daily",
                               "column": "gmv", "report": True,
                               "lang": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["suspects"][0]["table"] == "dwd.orders"
    assert "Quality Root-Cause Trace" in body["report"]


def test_api_unknown_table_400():
    res = _client().post("/api/qualitytrace/trace",
                         json={"sql_text": SQL, "table": "nope.missing"})
    assert res.status_code == 400


def test_api_empty_table_400():
    res = _client().post("/api/qualitytrace/trace",
                         json={"sql_text": SQL, "table": "  "})
    assert res.status_code == 400


def test_api_file_whitelist(monkeypatch):
    monkeypatch.setenv("QUALITYTRACE_API_ALLOWED_DIRS", str(DEMO.parent))
    res = _client().post("/api/qualitytrace/trace",
                         json={"sql_file": str(DEMO),
                               "table": "dws.orders_daily"})
    assert res.status_code == 200
    bad = _client().post("/api/qualitytrace/trace",
                         json={"sql_file": str(ROOT / "pyproject.toml"),
                               "table": "t"})
    assert bad.status_code == 403


def test_api_llm_section(monkeypatch):
    from seatunnel_agent.agents.data.quality_trace import advisor_llm

    monkeypatch.setattr(advisor_llm, "trace_note",
                        lambda result, lang="zh": "TRACE-NOTE")
    res = _client().post("/api/qualitytrace/trace",
                         json={"sql_text": SQL, "table": "dws.orders_daily",
                               "llm": True, "report": True})
    assert res.status_code == 200
    assert res.json()["result"]["trace_note"] == "TRACE-NOTE"


def test_api_health():
    body = _client().get("/api/qualitytrace/health").json()
    assert body == {"status": "ok", "agent": "quality_trace"}


# ── CLI / manifest / tool ────────────────────────────────────────────

def test_cli_qualitytrace_runs():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "qualitytrace", "-f", str(DEMO), "-t", "dws.orders_daily",
        "-c", "gmv", "--lang", "zh"])
    assert res.exit_code == 0, res.output
    assert "质量根因追踪" in res.output and "dwd.orders" in res.output


def test_cli_unknown_table_usage_error():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    res = CliRunner().invoke(cli, [
        "qualitytrace", "-f", str(DEMO), "-t", "nope.missing"])
    assert res.exit_code == 2


def test_manifest_discovered():
    from seatunnel_agent.hub.registry import workspace_manifests

    names = {m.name for m in workspace_manifests("data")}
    assert "quality_trace" in names


def test_mcp_tool_markdown():
    from seatunnel_agent.agents.data.quality_trace.tools import quality_trace

    out = quality_trace(SQL, "dws.orders_daily", column="gmv", lang="en")
    assert "Quality Root-Cause Trace" in out and "dwd.orders" in out
    assert "must not be empty" in quality_trace("  ", "t")
    assert "must not be empty" in quality_trace(SQL, " ")
    assert "bad input" in quality_trace(SQL, "nope.missing")
