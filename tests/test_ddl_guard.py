"""Tests for the migration-guard agent (ddl_guard).

Deterministic only — no LLM, no database, no network.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from seatunnel_agent.agents.data.ddl_guard import (
    render_markdown,
    scan_sql_text,
)
from seatunnel_agent.cli import cli

runner = CliRunner()

MIGRATION = """
CREATE TABLE dw.orders (
  order_id BIGINT COMMENT 'id',
  note VARCHAR(256) COMMENT 'n',
  legacy_flag INT COMMENT 'l'
) PARTITIONED BY (dt STRING COMMENT 'p');

ALTER TABLE dw.orders ADD COLUMNS (channel STRING COMMENT 'c');
ALTER TABLE dw.orders DROP COLUMN legacy_flag;
ALTER TABLE dw.orders CHANGE COLUMN note note VARCHAR(64);
ALTER TABLE dw.orders RENAME TO dw.orders_v2;
DROP TABLE dw.retired_tmp;
TRUNCATE TABLE dw.scratch;
"""

SAFE = """
ALTER TABLE dw.orders ADD COLUMNS (channel STRING COMMENT 'c');
"""


# ─────────────────────── guard ───────────────────────

def test_dangerous_ops_graded():
    r = scan_sql_text(MIGRATION)
    kinds = {(f.kind, f.table) for f in r.findings}
    assert ("drop_column", "dw.orders") in kinds
    assert ("type_narrowing", "dw.orders") in kinds    # varchar 256 -> 64
    assert ("rename_table", "dw.orders") in kinds
    assert ("drop_table", "dw.retired_tmp") in kinds
    assert ("truncate_table", "dw.scratch") in kinds
    sev = {f.kind: f.severity for f in r.findings}
    assert sev["drop_column"] == "high"
    assert sev["type_narrowing"] == "high"
    assert sev["rename_table"] == "medium"


def test_reversibility_tracked():
    r = scan_sql_text(MIGRATION)
    by_kind = {f.kind: f for f in r.findings}
    # drop_column type is known from the CREATE in the same input
    assert by_kind["drop_column"].reversible is True
    # dropped table has no CREATE in the input, truncate never reverses
    assert by_kind["drop_table"].reversible is False
    assert by_kind["truncate_table"].reversible is False
    assert r.counts()["irreversible"] == 2


def test_undo_script_reverses_in_order():
    r = scan_sql_text(MIGRATION)
    undo = r.undo_sql
    # re-add of the dropped column carries its recovered type
    assert "ADD COLUMNS (legacy_flag INT)" in undo
    # rename reversed, add reversed, narrowing restored to the old type
    assert "ALTER TABLE dw.orders_v2 RENAME TO dw.orders;" in undo
    assert "ALTER TABLE dw.orders DROP COLUMN channel;" in undo
    assert "CHANGE COLUMN note note VARCHAR(256);" in undo
    # irreversible steps stay visible as comments
    assert "IRREVERSIBLE" in undo
    # reverse execution order: the last migration step is undone first
    assert undo.index("TRUNCATE") < undo.index("RENAME TO dw.orders")


def test_not_null_without_default_flagged():
    sql = "ALTER TABLE t MODIFY COLUMN c BIGINT NOT NULL;"
    r = scan_sql_text(sql)
    assert any(f.kind == "not_null_no_default" for f in r.findings)
    sql_ok = "ALTER TABLE t MODIFY COLUMN c BIGINT NOT NULL DEFAULT 0;"
    r2 = scan_sql_text(sql_ok)
    assert not any(f.kind == "not_null_no_default" for f in r2.findings)


def test_safe_migration_reports_clean():
    r = scan_sql_text(SAFE)
    assert r.counts()["total"] == 0
    assert r.undo_sql                       # ADD still contributes its undo
    assert "安全" in render_markdown(r, "zh")
    assert "safe" in render_markdown(r, "en")


def test_int_narrowing_needs_known_old_type():
    sql = ("CREATE TABLE t (n BIGINT COMMENT 'n');\n"
           "ALTER TABLE t MODIFY COLUMN n INT;")
    r = scan_sql_text(sql)
    assert any(f.kind == "type_narrowing" for f in r.findings)
    # widening is a plain type change, not narrowing
    sql2 = ("CREATE TABLE t (n INT COMMENT 'n');\n"
            "ALTER TABLE t MODIFY COLUMN n BIGINT;")
    r2 = scan_sql_text(sql2)
    assert not any(f.kind == "type_narrowing" for f in r2.findings)
    assert any(f.kind == "type_change" for f in r2.findings)


# ─────────────────────── CLI ───────────────────────

def test_cli_ddlguard_report_gate_and_undo(tmp_path):
    res = runner.invoke(cli, ["ddlguard", "--sql", MIGRATION, "--lang", "en"])
    assert res.exit_code == 0, res.output
    assert "Rollback script" in res.output

    res = runner.invoke(cli, ["ddlguard", "--sql", MIGRATION, "-F", "json"])
    data = json.loads(res.output)
    assert data["counts"]["high"] >= 3

    undo = tmp_path / "undo.sql"
    res = runner.invoke(cli, ["ddlguard", "--sql", MIGRATION,
                              "--fail-on", "high", "-u", str(undo)])
    assert res.exit_code == 1                 # gate fires…
    assert undo.exists()                      # …but the rollback still lands
    assert "RENAME TO dw.orders;" in undo.read_text(encoding="utf-8")

    res = runner.invoke(cli, ["ddlguard", "--sql", SAFE,
                              "--fail-on", "medium"])
    assert res.exit_code == 0, res.output


# ─────────────────────── REST API ───────────────────────

def _api_client():
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from seatunnel_agent.agents.data.ddl_guard.api import router
    app = fastapi.FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_scan_inline():
    r = _api_client().post("/api/ddlguard/scan",
                           json={"sql": MIGRATION, "lang": "en",
                                 "report": True})
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["counts"]["high"] >= 3
    assert "rollback" in data["result"]["undo_sql"]
    assert "drop table" in data["report"]


def test_api_requires_input():
    assert _api_client().post("/api/ddlguard/scan",
                              json={}).status_code == 400


# ─────────────────────── MCP / orchestrator wiring ───────────────────────

def test_tool_discovered_everywhere():
    from seatunnel_agent.agents.data.mcp_toolbox.core import (
        build_tool_functions,
    )
    fns = build_tool_functions(include_db=False)
    assert "ddl_guard" in fns
    out = fns["ddl_guard"](MIGRATION, lang="en")
    assert "Rollback script" in out
    assert "不能为空" in fns["ddl_guard"]("")

    from seatunnel_agent.agents.ai.orchestrator.catalog import build_catalog
    from seatunnel_agent.agents.ai.orchestrator.router import suggest
    cat = build_catalog()
    assert cat["ddl_guard"].page == "/ddlguard"
    s = suggest("上线前帮我看看这份迁移脚本能不能回滚", cat)
    assert s and s[0].tool == "ddl_guard"
