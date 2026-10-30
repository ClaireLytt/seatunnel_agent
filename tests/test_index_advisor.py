"""Deterministic core tests for the index advisor."""

from __future__ import annotations

from pathlib import Path

import pytest

from seatunnel_agent.agents.data.index_advisor import (
    analyze_workload,
    parse_ddl_types,
    recommend,
    render_markdown,
)
from seatunnel_agent.agents.data.index_advisor.tools import index_advisor

DEMO_DIR = Path(__file__).resolve().parents[1] / "examples" / "indexadvisor_demo"
QUERIES = (DEMO_DIR / "queries.sql").read_text(encoding="utf-8")
DDL = (DEMO_DIR / "ddl.sql").read_text(encoding="utf-8")


def _advice():
    return recommend(analyze_workload(QUERIES), ddl_text=DDL)


def test_workload_column_stats():
    advice = analyze_workload(QUERIES)
    by = {t.table: t for t in advice.tables}
    orders = by["ods.orders"]
    assert orders.statements == 3
    assert orders.columns["dt"].eq == 2          # two '=' filters
    assert orders.columns["dt"].range == 1       # the BETWEEN
    assert orders.columns["status"].eq == 2
    assert orders.columns["user_id"].join == 1   # join with users
    assert orders.columns["user_id"].eq == 1     # the lookup by id
    users = by["ods.users"]
    assert users.columns["region"].join == 1     # join with dim.regions
    assert users.columns["region"].group == 1
    assert users.columns["updated_at"].range == 1


def test_recommendations_and_ddl():
    by = {t.table: t for t in _advice().tables}
    orders = by["ods.orders"]
    assert orders.partition_col == "dt"          # date-like + most eq
    assert orders.bucket_col == "user_id"        # hottest join key
    # composite: eq columns by frequency (dt excluded as partition),
    # then the hottest range column
    assert orders.index_cols == ["status", "user_id", "amount"]
    assert any(d.startswith("PARTITIONED BY (dt)") for d in orders.ddl)
    assert any("CLUSTERED BY (user_id)" in d for d in orders.ddl)
    users = by["ods.users"]
    # updated_at is TIMESTAMP in the DDL → counts as date-like, but it
    # has no equality hits so it must not become the partition column
    assert users.partition_col is None
    assert users.bucket_col == "region"


def test_ddl_types_parse():
    types = parse_ddl_types(DDL)
    assert types["ods.users"]["updated_at"] == "timestamp"
    assert types["ods.orders"]["amount"] == "double"


def test_unparseable_statement_skipped_not_guessed():
    advice = analyze_workload(
        "SELECT 1 FROM t WHERE a = 1;\nTHIS IS NOT SQL AT ALL !!;")
    assert advice.statements == 2
    assert len(advice.skipped) == 1
    assert "THIS IS NOT SQL" in advice.skipped[0]


def test_bad_inputs():
    with pytest.raises(ValueError, match="no SQL statements"):
        analyze_workload("   ")


def test_report_zh_en_and_tool():
    advice = _advice()
    zh = render_markdown(advice, lang="zh")
    en = render_markdown(advice, lang="en")
    assert "索引 / 分区推荐" in zh and "DDL 片段" in zh
    assert "Index / Partition Recommendation" in en
    assert "PARTITIONED BY (dt);" in en
    md = index_advisor(QUERIES, ddl=DDL, lang="en")
    assert "CLUSTERED BY (user_id)" in md
    assert "must not be empty" in index_advisor(" ")
