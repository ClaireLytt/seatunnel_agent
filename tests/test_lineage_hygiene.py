"""Tests for the warehouse-hygiene agent (lineage_hygiene).

Deterministic only — no LLM, no database, no network.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from seatunnel_agent.agents.data.lineage_hygiene import (
    analyze_sql_text,
    render_markdown,
)
from seatunnel_agent.cli import cli

runner = CliRunner()

SQL = """
CREATE TABLE ods.a (id BIGINT, x STRING, unused STRING);
CREATE TABLE dw.kept (id BIGINT, x STRING);
CREATE TABLE dw.orphan (id BIGINT);
CREATE TABLE lonely.t (id BIGINT);
CREATE TABLE ads.final (id BIGINT);
INSERT INTO dw.kept SELECT id, x FROM ods.a;
INSERT INTO dw.orphan SELECT id FROM ods.a;
INSERT INTO ads.final SELECT id FROM dw.kept;
"""


# ─────────────────────── analyzer ───────────────────────

def test_orphan_outputs_found_and_marts_exempt():
    r = analyze_sql_text(SQL)
    orphans = {i.table for i in r.orphan_outputs}
    assert "dw.orphan" in orphans
    assert "ads.final" not in orphans          # final marts are endpoints
    assert "dw.kept" not in orphans            # it feeds ads.final


def test_dead_columns_only_on_read_tables():
    r = analyze_sql_text(SQL)
    dead = {(i.table, i.column) for i in r.dead_columns}
    assert ("ods.a", "unused") in dead
    # dw.orphan's id is unread too, but the whole table is already an
    # orphan — no per-column noise for unread tables
    assert not any(t == "dw.orphan" for t, _ in dead)


def test_dangling_definitions():
    r = analyze_sql_text(SQL)
    assert [i.table for i in r.dangling_defs] == ["lonely.t"]


def test_partition_columns_never_dead():
    sql = ("CREATE TABLE ods.p (id BIGINT) PARTITIONED BY (dt STRING);\n"
           "CREATE TABLE dw.o (id BIGINT);\n"
           "INSERT INTO dw.o SELECT id FROM ods.p;")
    r = analyze_sql_text(sql)
    assert not any(i.column == "dt" for i in r.dead_columns)


def test_clean_warehouse_reports_clean():
    sql = ("CREATE TABLE ods.a (id BIGINT);\n"
           "CREATE TABLE ads.f (id BIGINT);\n"
           "INSERT INTO ads.f SELECT id FROM ods.a;")
    r = analyze_sql_text(sql)
    assert r.counts()["total"] == 0
    assert "干净" in render_markdown(r, "zh")
    assert "clean" in render_markdown(r, "en")


def test_report_lists_every_kind():
    md = render_markdown(analyze_sql_text(SQL), "en")
    assert "dw.orphan" in md and "unused" in md and "lonely.t" in md


# ─────────────────────── CLI ───────────────────────

def test_cli_hygiene_markdown_and_json():
    res = runner.invoke(cli, ["hygiene", "--sql", SQL, "--lang", "en"])
    assert res.exit_code == 0, res.output
    assert "orphan" in res.output

    res = runner.invoke(cli, ["hygiene", "--sql", SQL, "-F", "json"])
    data = json.loads(res.output)
    assert data["counts"]["orphan_outputs"] == 1


@pytest.mark.parametrize("gate,code", [
    ("orphans", 1), ("dead", 1), ("dangling", 1), ("any", 1)])
def test_cli_hygiene_fail_on(gate, code):
    res = runner.invoke(cli, ["hygiene", "--sql", SQL, "--fail-on", gate])
    assert res.exit_code == code


def test_cli_hygiene_gate_passes_clean():
    sql = ("CREATE TABLE ods.a (id BIGINT);\n"
           "CREATE TABLE ads.f (id BIGINT);\n"
           "INSERT INTO ads.f SELECT id FROM ods.a;")
    res = runner.invoke(cli, ["hygiene", "--sql", sql, "--fail-on", "any"])
    assert res.exit_code == 0, res.output


# ─────────────────────── REST API ───────────────────────

def _api_client():
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.lineage_hygiene.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_scan_inline():
    r = _api_client().post("/api/hygiene/scan",
                           json={"sql": SQL, "lang": "en", "report": True})
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["counts"]["dangling_defs"] == 1
    assert "lonely.t" in data["report"]


def test_api_requires_input():
    assert _api_client().post("/api/hygiene/scan", json={}).status_code == 400


def test_api_dir_outside_whitelist(monkeypatch, tmp_path):
    monkeypatch.setenv("HYGIENE_API_ALLOWED_DIRS", str(tmp_path / "only"))
    r = _api_client().post("/api/hygiene/scan",
                           json={"dir": "examples/pii_demo"})
    assert r.status_code == 403


# ─────────────────────── MCP ───────────────────────

def test_mcp_warehouse_hygiene_tool(monkeypatch, tmp_path):
    monkeypatch.setenv("SEATUNNEL_MCP_AUDIT_PATH", str(tmp_path / "a.jsonl"))
    from seatunnel_agent.agents.data.mcp_toolbox.core import (
        build_tool_functions,
    )
    tools = build_tool_functions(include_db=False)
    out = tools["warehouse_hygiene"](SQL, lang="en")
    assert "dw.orphan" in out
    assert "不能为空" in tools["warehouse_hygiene"]("  ")
