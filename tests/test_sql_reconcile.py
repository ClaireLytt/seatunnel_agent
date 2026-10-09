# -*- coding: utf-8 -*-
"""Tests for the SQL caliber reconciliation agent.

Deterministic only — no LLM, no database, no network.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("sqlglot")

from seatunnel_agent.sql_reconcile import (  # noqa: E402
    reconcile_sql,
    render_markdown,
    report_to_dict,
)

SQL_BASE = """
SELECT dt, SUM(pay_amount) AS gmv
FROM dws_trade_pay_df t
WHERE t.dt BETWEEN '2026-09-01' AND '2026-09-30'
  AND t.status = 'paid'
GROUP BY dt
"""


def test_identical_sql_no_findings():
    report = reconcile_sql(SQL_BASE, SQL_BASE)
    assert report.identical
    assert report.findings == []
    assert report.worst_level() is None


def test_alias_change_is_not_a_difference():
    other = SQL_BASE.replace(" t\n", " x\n").replace("t.", "x.")
    report = reconcile_sql(SQL_BASE, other)
    assert report.identical, [f.to_dict() for f in report.findings]


def test_missing_filter_is_critical():
    other = SQL_BASE.replace("  AND t.status = 'paid'\n", "")
    report = reconcile_sql(SQL_BASE, other)
    cats = {f.category for f in report.findings}
    assert "filter" in cats
    assert report.worst_level() == "critical"
    filt = [f for f in report.findings if f.category == "filter"][0]
    assert filt.args["side"] == "A"
    assert "status" in filt.args["pred"]


def test_time_range_difference_is_risk():
    other = SQL_BASE.replace("'2026-09-30'", "'2026-09-29'")
    report = reconcile_sql(SQL_BASE, other)
    assert [f.category for f in report.findings] == ["time_range"]
    assert report.worst_level() == "risk"


def test_source_table_difference():
    other = SQL_BASE.replace("dws_trade_pay_df", "dws_trade_pay_di")
    report = reconcile_sql(SQL_BASE, other)
    cats = {f.category for f in report.findings}
    assert "source" in cats
    assert report.worst_level() == "critical"


def test_join_type_difference():
    a = """SELECT o.dt, SUM(o.amt) FROM orders o
           JOIN users u ON o.uid = u.uid GROUP BY o.dt"""
    b = """SELECT o.dt, SUM(o.amt) FROM orders o
           LEFT JOIN users u ON o.uid = u.uid GROUP BY o.dt"""
    report = reconcile_sql(a, b)
    joins = [f for f in report.findings if f.category == "join"]
    assert joins and joins[0].key == "msg_join_type"
    assert joins[0].severity == "critical"


def test_aggregation_caliber_difference():
    other = SQL_BASE.replace("SUM(pay_amount)", "COUNT(DISTINCT order_id)")
    report = reconcile_sql(SQL_BASE, other)
    assert any(f.category == "aggregation" and f.severity == "critical"
               for f in report.findings)


def test_dedup_mechanism_difference():
    a = "SELECT DISTINCT uid FROM dws_user_df WHERE dt = '2026-09-30'"
    b = "SELECT uid FROM dws_user_df WHERE dt = '2026-09-30'"
    report = reconcile_sql(a, b)
    dedup = [f for f in report.findings if f.category == "dedup"]
    assert dedup and dedup[0].args == {"a": "distinct", "b": "none"}


def test_row_number_dedup_detected():
    a = """SELECT uid FROM (
             SELECT uid, ROW_NUMBER() OVER (PARTITION BY uid ORDER BY ts DESC) rn
             FROM dwd_user_log WHERE dt='2026-09-30') x WHERE rn = 1"""
    report = reconcile_sql(a, a)
    assert report.profile_a.row_number_dedup


def test_parse_error_reported_not_raised():
    report = reconcile_sql("SELECT FROM WHERE", "SELECT 1")
    assert report.parse_error
    assert not report.identical


def test_render_markdown_zh_and_en():
    other = SQL_BASE.replace("  AND t.status = 'paid'\n", "")
    report = reconcile_sql(SQL_BASE, other)
    zh = render_markdown(report, "zh")
    en = render_markdown(report, "en")
    assert "口径对账" in zh and "过滤条件" in zh
    assert "Caliber Reconciliation" in en and "Filters" in en


def test_report_to_dict_roundtrips_json():
    report = reconcile_sql(SQL_BASE, SQL_BASE.replace("'paid'", "'done'"))
    data = report_to_dict(report, "en")
    json.dumps(data)  # must be serializable
    assert data["counts"]["critical"] >= 1
    assert all("message" in f for f in data["findings"])


def test_cli_reconcile_fail_on():
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    runner = CliRunner()
    other = SQL_BASE.replace("  AND t.status = 'paid'\n", "")
    result = runner.invoke(cli, [
        "reconcile", "--sql-a", SQL_BASE, "--sql-b", other,
        "--fail-on", "critical", "--format", "json"])
    assert result.exit_code == 1
    ok = runner.invoke(cli, [
        "reconcile", "--sql-a", SQL_BASE, "--sql-b", SQL_BASE,
        "--fail-on", "critical", "--format", "json"])
    assert ok.exit_code == 0, ok.output
    assert json.loads(ok.output)["identical"] is True
