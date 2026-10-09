"""Tests for migration DDL generation (schema_drift/migrate.py)."""

from __future__ import annotations

import pytest

from seatunnel_agent.schema_drift import (
    diff_scripts,
    generate_migration,
    parse_schema_script,
    render_migration_sql,
)

_OLD = """
CREATE TABLE ods.orders(
  order_id STRING COMMENT '订单ID',
  amount DOUBLE COMMENT '金额',
  status INT COMMENT '状态',
  legacy_flag STRING COMMENT '历史标记'
) COMMENT '订单' PARTITIONED BY (dt STRING);

CREATE TABLE ods.gone(x STRING);
"""

_NEW = """
CREATE TABLE ods.orders(
  order_id STRING COMMENT '订单ID',
  amount DECIMAL(18,2) COMMENT '金额',
  status BIGINT COMMENT '状态',
  channel STRING COMMENT '渠道'
) COMMENT '订单' PARTITIONED BY (dt STRING);

CREATE TABLE ods.brand_new(y STRING);
"""


@pytest.fixture()
def plan_and_report():
    report = diff_scripts(_OLD, _NEW, dialect="hive")
    new_schemas, warn = parse_schema_script(_NEW, "hive")
    assert not warn
    return generate_migration(report, new_schemas), report


def test_added_column_is_auto(plan_and_report) -> None:
    plan, _ = plan_and_report
    adds = [s for s in plan.statements if s.kind == "column_added"]
    assert adds and adds[0].auto
    assert "ADD COLUMNS (channel" in adds[0].sql  # hive syntax


def test_widening_type_change_auto_breaking_manual(plan_and_report) -> None:
    plan, report = plan_and_report
    changes = {s.sql: s for s in plan.statements if s.kind == "type_changed"}
    # INT -> BIGINT widens (auto); DOUBLE -> DECIMAL is risk/breaking per
    # classify_type_change — assert auto mirrors severity in every case
    sev = {(f.table, f.column): f.severity
           for f in report.findings if f.kind == "type_changed"}
    assert changes, "expected type_changed statements"
    for s in changes.values():
        col = s.sql.split("CHANGE COLUMN ")[1].split()[0]
        assert s.auto == (sev[(s.table, col)] != "breaking")
        assert s.sql.startswith(f"ALTER TABLE {s.table} CHANGE COLUMN")


def test_destructive_changes_never_auto(plan_and_report) -> None:
    plan, _ = plan_and_report
    for s in plan.statements:
        if s.kind in ("column_removed", "table_removed", "partition_changed"):
            assert not s.auto, s


def test_mysql_dialect_syntax() -> None:
    report = diff_scripts(
        "CREATE TABLE t(a INT);",
        "CREATE TABLE t(a BIGINT, b VARCHAR(10));",
        dialect="mysql",
    )
    new_schemas, _ = parse_schema_script(
        "CREATE TABLE t(a BIGINT, b VARCHAR(10));", "mysql")
    plan = generate_migration(report, new_schemas)
    sqls = " ".join(s.sql for s in plan.statements)
    assert "ADD COLUMN b" in sqls and "MODIFY COLUMN a BIGINT" in sqls
    assert "ADD COLUMNS (" not in sqls


def test_render_script_separates_manual(plan_and_report) -> None:
    plan, _ = plan_and_report
    script = render_migration_sql(plan)
    assert "MANUAL REVIEW" in script
    # destructive statements only appear commented out
    for line in script.splitlines():
        if "DROP" in line:
            assert line.lstrip().startswith("--"), line
    # deterministic
    assert script == render_migration_sql(plan)


def test_rename_without_new_schemas_is_manual() -> None:
    report = diff_scripts(
        "CREATE TABLE t(user_name STRING COMMENT '姓名');",
        "CREATE TABLE t(username STRING COMMENT '姓名');",
        dialect="hive",
    )
    renames = [f for f in report.findings if f.kind == "column_renamed"]
    if not renames:  # differ may classify as remove+add; both acceptable
        pytest.skip("differ did not classify as rename")
    plan = generate_migration(report, new_schemas=None)
    s = [x for x in plan.statements if x.kind == "column_renamed"][0]
    assert not s.auto and "<TYPE>" in s.sql


def test_cli_emit_ddl(tmp_path) -> None:
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    old = tmp_path / "old.sql"
    new = tmp_path / "new.sql"
    out = tmp_path / "migration.sql"
    old.write_text(_OLD, encoding="utf-8")
    new.write_text(_NEW, encoding="utf-8")
    result = CliRunner().invoke(cli, [
        "schemadiff", "--old", str(old), "--new", str(new),
        "--emit-ddl", str(out),
    ])
    assert result.exit_code == 0, result.output
    script = out.read_text(encoding="utf-8")
    assert "ALTER TABLE ods.orders ADD COLUMNS (channel" in script
