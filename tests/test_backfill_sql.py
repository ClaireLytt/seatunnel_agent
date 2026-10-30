"""Deterministic core tests for the backfill SQL agent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from seatunnel_agent.agents.data.backfill_sql import (
    generate,
    parse_spec,
    render_markdown,
)
from seatunnel_agent.agents.data.backfill_sql.tools import backfill_sql

DEMO = (Path(__file__).resolve().parents[1] / "examples" / "backfillsql_demo"
        / "spec.json").read_text(encoding="utf-8")


def _spec(**over):
    data = json.loads(DEMO)
    data.update(over)
    return parse_spec(json.dumps(data))


def test_hive_overwrite_one_partition_per_date():
    result = generate(parse_spec(DEMO))
    assert [d.date for d in result.dates] == [
        "2024-05-01", "2024-05-02", "2024-05-03"]
    stmt = result.dates[0].statements
    assert len(stmt) == 1
    assert stmt[0].startswith(
        "INSERT OVERWRITE TABLE dws.sales PARTITION (dt = '2024-05-01')")
    assert "WHERE dt = '2024-05-01'" in stmt[0]
    assert result.warnings == []


def test_prechecks_bound_to_range():
    result = generate(parse_spec(DEMO))
    assert len(result.prechecks) == 2  # target + source_table
    assert "dt BETWEEN '2024-05-01' AND '2024-05-03'" in result.prechecks[0]
    assert "FROM ods.orders" in result.prechecks[1]


def test_compact_date_format():
    result = generate(_spec(date_format="yyyyMMdd"))
    assert result.dates[0].partition_value == "20240501"
    assert "WHERE dt = '20240501'" in result.dates[0].statements[0]


def test_mysql_overwrite_falls_back_to_delete_insert():
    result = generate(_spec(dialect="mysql"))
    stmt = result.dates[0].statements
    assert stmt[0] == "DELETE FROM dws.sales WHERE dt = '2024-05-01';"
    assert stmt[1].startswith("INSERT INTO dws.sales")
    assert result.warnings and "INSERT OVERWRITE" in result.warnings[0]


def test_merge_requires_keys_and_bounds_partition():
    with pytest.raises(ValueError, match="requires 'keys'"):
        _spec(mode="merge")
    result = generate(_spec(mode="merge", dialect="spark",
                            keys=["order_id"]))
    stmt = result.dates[0].statements[0]
    assert stmt.startswith("MERGE INTO dws.sales AS t")
    assert "ON t.order_id = s.order_id AND t.dt = '2024-05-01'" in stmt


def test_hourly_grain():
    result = generate(_spec(date_format="yyyy-MM-dd HH", start="2024-05-01",
                            end="2024-05-01"))
    assert len(result.dates) == 24  # one slot per hour
    assert result.dates[0].partition_value == "2024-05-01 00"
    assert result.dates[-1].partition_value == "2024-05-01 23"
    assert result.dates[5].date == "2024-05-01T05"
    assert "WHERE dt = '2024-05-01 05'" in result.dates[5].statements[0]


def test_hourly_grain_safety():
    with pytest.raises(ValueError, match="hourly range exceeds"):
        _spec(date_format="yyyyMMddHH", start="2024-01-01", end="2024-03-01")
    with pytest.raises(ValueError, match="needs 'HH'"):
        _spec(grain="hour")
    with pytest.raises(ValueError, match="grain must be"):
        _spec(grain="minute")


def test_safety_rules():
    with pytest.raises(ValueError, match="placeholder"):
        _spec(source="SELECT * FROM ods.orders")
    with pytest.raises(ValueError, match="366 days"):
        _spec(start="2020-01-01", end="2022-01-01")
    with pytest.raises(ValueError, match="before start"):
        _spec(start="2024-05-03", end="2024-05-01")
    with pytest.raises(ValueError, match="bad identifier"):
        _spec(table="dws.sales; drop table x")
    with pytest.raises(ValueError, match="missing field"):
        parse_spec('{"table": "t"}')


def test_report_zh_en_and_tool():
    result = generate(parse_spec(DEMO))
    zh = render_markdown(result, lang="zh")
    en = render_markdown(result, lang="en")
    assert "补数 SQL" in zh and "前置校验" in zh
    assert "Backfill SQL" in en and "Pre-flight checks" in en
    assert "```sql" in en
    md = backfill_sql(DEMO, lang="en")
    assert "idempotent" in md
    assert "must not be empty" in backfill_sql(" ")
    assert "bad input" in backfill_sql("{broken")
