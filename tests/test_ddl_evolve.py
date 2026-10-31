"""Tests for the ddl_evolve agent (evolver / report / CLI / tool / API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from seatunnel_agent.agents.data.ddl_evolve import (
    build_migration,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "ddlevolve_demo"


def _demo_plan(dialect: str = "hive"):
    return build_migration(
        (DEMO / "old.sql").read_text(encoding="utf-8"),
        (DEMO / "new.sql").read_text(encoding="utf-8"), dialect=dialect)


def _by_kind(plan):
    out: dict[str, list] = {}
    for s in plan.steps:
        out.setdefault(s.kind, []).append(s)
    return out


# ----------------------------------------------------------------- evolver

def test_demo_plan_shape():
    plan = _demo_plan()
    assert plan.safe_steps == 5 and plan.unsafe_steps == 3
    by = _by_kind(plan)
    assert set(by) == {"table_added", "table_removed", "column_added",
                       "column_removed", "type_changed",
                       "comment_changed", "partition_changed"}


def test_widening_runs_narrowing_stays_commented():
    old = "CREATE TABLE t (a INT, b BIGINT)"
    new = "CREATE TABLE t (a BIGINT, b INT)"
    plan = build_migration(old, new)
    widen = next(s for s in plan.steps if s.safe)
    narrow = next(s for s in plan.steps if not s.safe)
    assert widen.sql == "ALTER TABLE t CHANGE COLUMN a a BIGINT;"
    assert narrow.sql.startswith("-- ")
    assert "narrowing" in narrow.note


def test_dangerous_statements_are_fully_commented():
    plan = _demo_plan()
    for s in plan.steps:
        if not s.safe:
            assert all(line.startswith("--")
                       for line in s.sql.splitlines())
    script = plan.to_script()
    assert "DROP TABLE tmp.legacy_report" in script
    assert "\nDROP TABLE" not in script       # only the commented spelling


def test_new_table_rendered_with_partitions_and_comments():
    plan = _demo_plan()
    (create,) = _by_kind(plan)["table_added"]
    assert "CREATE TABLE ads.user_summary" in create.sql
    assert "PARTITIONED BY (dt STRING)" in create.sql
    assert "COMMENT '用户ID'" in create.sql


def test_mysql_spellings():
    old = "CREATE TABLE t (a INT)"
    new = "CREATE TABLE t (a INT, b VARCHAR(20) COMMENT 'x')"
    plan = build_migration(old, new, dialect="mysql")
    (add,) = plan.steps
    assert add.sql == ("ALTER TABLE t ADD COLUMN b VARCHAR(20) "
                       "COMMENT 'x';")


def test_rename_becomes_change_column():
    old = "CREATE TABLE t (user_nm STRING COMMENT 'n', x INT)"
    new = "CREATE TABLE t (user_name STRING COMMENT 'n', x INT)"
    plan = build_migration(old, new)
    (step,) = [s for s in plan.steps if s.kind == "column_renamed"]
    assert step.safe
    assert "CHANGE COLUMN user_nm user_name STRING" in step.sql


def test_identical_and_bad_inputs():
    ddl = "CREATE TABLE t (a INT)"
    assert build_migration(ddl, ddl).steps == []
    with pytest.raises(ValueError, match="dialect"):
        build_migration(ddl, ddl, dialect="oracle")
    with pytest.raises(ValueError, match="no CREATE TABLE"):
        build_migration("SELECT 1", "SELECT 2")


# ------------------------------------------------------------------ report

def test_report_both_langs_and_identical():
    plan = _demo_plan()
    zh = render_markdown(plan, lang="zh")
    en = render_markdown(plan, lang="en")
    assert "DDL 迁移脚本" in zh and "```sql" in zh
    assert "DDL Migration" in en and "commented for review" in en
    ddl = "CREATE TABLE t (a INT)"
    same = render_markdown(build_migration(ddl, ddl), lang="en")
    assert "nothing to migrate" in same


# --------------------------------------------------------------------- CLI

def test_cli_markdown_json_and_script_out(tmp_path):
    from seatunnel_agent.cli import cli

    runner = CliRunner()
    args = ["ddlevolve", "--old", str(DEMO / "old.sql"),
            "--new", str(DEMO / "new.sql")]
    res = runner.invoke(cli, args)
    assert res.exit_code == 0, res.output
    assert "DDL 迁移脚本" in res.output
    out = tmp_path / "migrate.sql"
    res = runner.invoke(cli, args + ["--script-out", str(out),
                                     "--format", "json"])
    assert res.exit_code == 0 and '"steps_total": 8' in res.output
    text = out.read_text(encoding="utf-8")
    assert "ALTER TABLE ods.user_info ADD COLUMNS" in text


# -------------------------------------------------------------------- tool

def test_tool_markdown_out():
    from seatunnel_agent.agents.data.ddl_evolve.tools import ddl_evolve

    out = ddl_evolve((DEMO / "old.sql").read_text(encoding="utf-8"),
                     (DEMO / "new.sql").read_text(encoding="utf-8"),
                     lang="en")
    assert "DDL Migration" in out and "ADD COLUMNS" in out
    assert "required" in ddl_evolve("", "CREATE TABLE t (a INT)")
    assert "bad input" in ddl_evolve("SELECT 1", "SELECT 2")


# --------------------------------------------------------------------- API

def _client():
    from fastapi import FastAPI

    from seatunnel_agent.agents.data.ddl_evolve.api import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_api_migrate_and_health():
    client = _client()
    assert client.get("/api/ddlevolve/health").status_code == 200
    resp = client.post("/api/ddlevolve/migrate", json={
        "old_text": (DEMO / "old.sql").read_text(encoding="utf-8"),
        "new_text": (DEMO / "new.sql").read_text(encoding="utf-8"),
        "lang": "en", "report": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["safe_steps"] == 5
    assert "DDL Migration" in body["report"]


def test_api_bad_input_400():
    client = _client()
    resp = client.post("/api/ddlevolve/migrate", json={
        "old_text": "SELECT 1", "new_text": "SELECT 2"})
    assert resp.status_code == 400
