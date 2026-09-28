"""Tests for the DQC module: rule parsing/validation, check SQL, evaluation
math (incl. history-based fluctuation), sqlite end-to-end, report, CLI."""

from __future__ import annotations

import sqlite3

import pytest

pytest.importorskip("yaml")

from seatunnel_agent.data_quality import (
    render_report,
    run_checks,
    validate_rules,
)
from seatunnel_agent.data_quality.rules import parse_rules_text
from seatunnel_agent.data_quality.runner import (
    DQCHistory,
    build_check_sql,
    push_failures,
)
from seatunnel_agent.text2sql.executor import DatabaseConfig, create_executor
from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl

_DDL = """
CREATE TABLE orders(
  id string COMMENT '主键',
  amount double COMMENT '金额',
  status string COMMENT '状态',
  dt string COMMENT '日期'
) COMMENT '订单';
"""

_RULES = """
version: 1
rules:
  - table: orders
    checks:
      - type: row_count
        min: 2
        max_change_pct: 50
      - type: null_rate
        column: amount
        max_pct: 30
      - type: unique
        columns: [id]
      - type: enum_domain
        column: status
        allowed: [paid, refund]
"""


@pytest.fixture()
def orders_db(tmp_path) -> str:
    db = tmp_path / "orders.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE orders(id TEXT, amount REAL, status TEXT, dt TEXT)")
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?)", [
        ("a", 10.0, "paid", "2026-03-01"),
        ("b", None, "paid", "2026-03-01"),     # 1/4 null -> 25% < 30%
        ("c", 5.0, "refund", "2026-03-01"),
        ("c", 6.0, "shipped", "2026-03-01"),   # dup id + enum violation
    ])
    conn.commit()
    conn.close()
    return str(db)


@pytest.fixture()
def schema_store() -> SchemaStore:
    return SchemaStore(parse_ddl(_DDL))


# ── parsing & validation ────────────────────────────────────────────


def test_parse_rules_ok() -> None:
    rules, errors = parse_rules_text(_RULES)
    assert errors == []
    assert len(rules) == 1 and len(rules[0].checks) == 4


def test_parse_rules_errors() -> None:
    bad = """
rules:
  - checks: [{type: row_count, min: 1}]
  - table: t
    checks: [{type: weird}]
  - table: t2
    checks: [{type: null_rate, column: c}]
  - table: t3
    checks: [{type: enum_domain, column: c, allowed: ["a'b"]}]
"""
    rules, errors = parse_rules_text(bad)
    assert rules == []
    assert any("缺少 table" in e for e in errors)
    assert any("type 只支持" in e for e in errors)
    assert any("max_pct" in e for e in errors)
    assert any("单引号" in e for e in errors)


def test_validate_rules_against_schema(schema_store) -> None:
    rules, _ = parse_rules_text(
        "rules:\n  - table: nope\n    checks: [{type: row_count, min: 1}]\n"
        "  - table: orders\n    checks: [{type: null_rate, column: ghost, max_pct: 1}]\n"
    )
    errors = validate_rules(rules, schema_store)
    assert any("白名单" in e for e in errors)
    assert any("ghost" in e for e in errors)


# ── check SQL builders ───────────────────────────────────────────────


def test_build_check_sql_golden() -> None:
    rules, _ = parse_rules_text(_RULES)
    rule = rules[0]
    sqls = [build_check_sql(rule, c) for c in rule.checks]
    assert sqls[0] == "SELECT COUNT(*) AS cnt FROM orders"
    assert "SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) * 100.0" in sqls[1]
    assert "GROUP BY id HAVING COUNT(*) > 1" in sqls[2]
    assert "status IS NOT NULL AND status NOT IN ('paid', 'refund')" in sqls[3]


def test_build_check_sql_where_macro() -> None:
    from datetime import date

    from seatunnel_agent.text2sql.subscriptions import builtin_params

    rules, _ = parse_rules_text(
        "rules:\n  - table: orders\n    where: \"dt = '${yesterday}'\"\n"
        "    checks: [{type: row_count, min: 1}]\n"
    )
    sql = build_check_sql(rules[0], rules[0].checks[0])
    expected = builtin_params(date.today())["yesterday"]
    assert f"WHERE dt = '{expected}'" in sql


# ── end-to-end on sqlite ─────────────────────────────────────────────


def test_run_checks_sqlite(orders_db, schema_store, tmp_path) -> None:
    rules, _ = parse_rules_text(_RULES)
    executor = create_executor(
        DatabaseConfig(ds_type="sqlite", host="", port=0, database=orders_db))
    history = DQCHistory(tmp_path / "hist.jsonl")

    results = run_checks(rules, executor, schema_store=schema_store,
                         history=history, ds_type="sqlite")
    by_type = {r.check_type: r for r in results}
    assert by_type["row_count"].status == "pass"       # 4 >= 2, first run
    assert by_type["null_rate"].status == "pass"       # 25% < 30%
    assert by_type["unique"].status == "fail"          # dup id 'c'
    assert "重复" in by_type["unique"].detail
    assert by_type["enum_domain"].status == "fail"     # 'shipped'
    assert "枚举域" in by_type["enum_domain"].detail

    report = render_report(results)
    assert "❌ 不通过 2" in report
    assert "unique" in report


def test_row_count_fluctuation(orders_db, schema_store, tmp_path) -> None:
    rules, _ = parse_rules_text(
        "rules:\n  - table: orders\n"
        "    checks: [{type: row_count, max_change_pct: 10}]\n"
    )
    executor = create_executor(
        DatabaseConfig(ds_type="sqlite", host="", port=0, database=orders_db))
    history = DQCHistory(tmp_path / "hist.jsonl")

    first = run_checks(rules, executor, schema_store, history, "sqlite")
    assert first[0].status == "pass"  # no baseline yet

    # shrink the table by >10% -> fluctuation alert on the next run
    conn = sqlite3.connect(orders_db)
    conn.execute("DELETE FROM orders WHERE id = 'a'")
    conn.commit()
    conn.close()
    second = run_checks(rules, executor, schema_store, history, "sqlite")
    assert second[0].status == "fail"
    assert "波动" in second[0].detail


def test_run_checks_whitelist_rejection(orders_db, tmp_path) -> None:
    rules, _ = parse_rules_text(
        "rules:\n  - table: other\n    checks: [{type: row_count, min: 1}]\n"
    )
    store = SchemaStore(parse_ddl(_DDL))  # 'other' not whitelisted
    executor = create_executor(
        DatabaseConfig(ds_type="sqlite", host="", port=0, database=orders_db))
    results = run_checks(rules, executor, store,
                         DQCHistory(tmp_path / "h.jsonl"), "sqlite")
    assert results[0].status == "error"
    assert "rejected" in results[0].detail


def test_push_failures(monkeypatch) -> None:
    from seatunnel_agent.data_quality.runner import CheckResult

    pushed: list = []
    import seatunnel_agent.text2sql.subscriptions as subs
    monkeypatch.setattr(
        subs, "push_feishu",
        lambda url, title, body, ok=True, **kw: (pushed.append((title, ok)), (True, "ok"))[1],
    )
    ok, msg = push_failures(
        [CheckResult(table="t", check_type="unique", status="pass")], "https://h")
    assert ok and msg == "no push needed" and pushed == []

    push_failures(
        [CheckResult(table="t", check_type="unique", status="fail", detail="dup")],
        "https://h",
    )
    assert pushed and pushed[0][1] is False


# ── CLI ──────────────────────────────────────────────────────────────


def test_cli_dqc(orders_db, tmp_path, monkeypatch) -> None:
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    monkeypatch.setenv("DQC_HISTORY_PATH", str(tmp_path / "hist.jsonl"))
    ddl = tmp_path / "ddl.sql"
    ddl.write_text(_DDL, encoding="utf-8")
    rules = tmp_path / "rules.yaml"
    rules.write_text(_RULES, encoding="utf-8")
    runner = CliRunner()

    r = runner.invoke(cli, ["dqc", "validate", "-r", str(rules), "--ddl", str(ddl)])
    assert r.exit_code == 0, r.output
    assert "校验通过" in r.output

    r = runner.invoke(cli, [
        "dqc", "run", "-r", str(rules), "--ddl", str(ddl),
        "--ds-type", "sqlite", "--database", orders_db,
    ])
    assert r.exit_code == 1  # violations -> CI gate
    assert "不通过 2" in r.output

    r = runner.invoke(cli, [
        "dqc", "run", "-r", str(rules), "--ddl", str(ddl),
        "--ds-type", "sqlite", "--database", orders_db,
        "--no-fail-on-violation",
    ])
    assert r.exit_code == 0, r.output
