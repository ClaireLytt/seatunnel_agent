"""Tests for the unified NL catalog search (catalog.py + t2s-search CLI)."""

from __future__ import annotations

import pytest

pytest.importorskip("yaml")

from seatunnel_agent.text2sql.catalog import (
    render_catalog_markdown,
    search_catalog,
)
from seatunnel_agent.text2sql.metrics import MetricStore
from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl
from seatunnel_agent.text2sql.values import ValueIndex

_DDL = """
CREATE TABLE dwd.dwd_trade_order_di(
  order_id string COMMENT '订单ID',
  pay_amount double COMMENT '支付金额',
  channel string COMMENT '渠道',
  province string COMMENT '省份',
  dt string COMMENT '日期'
) COMMENT '交易订单明细';

CREATE TABLE dim.dim_user(
  user_id string COMMENT '用户ID',
  address string COMMENT '收货地址',
  city string COMMENT '城市'
) COMMENT '用户维表';
"""

_METRICS = """
metrics:
  - name: gmv
    display_name: GMV
    aliases: [成交总额, 交易额]
    description: 支付金额合计
    table: dwd.dwd_trade_order_di
    expression: SUM(pay_amount)
    time_column: dt
    dimensions: [channel]
"""


@pytest.fixture()
def assets() -> tuple[SchemaStore, MetricStore, ValueIndex]:
    store = SchemaStore(parse_ddl(_DDL))
    metric_store, errors = MetricStore.from_text(_METRICS, store)
    assert not errors, errors
    index = ValueIndex({
        "dim.dim_user": {"city": ("上海", "杭州", "华东新区")},
    })
    return store, metric_store, index


def test_search_hits_all_three_kinds(assets) -> None:
    store, metric_store, index = assets
    out = search_catalog(
        "成交总额 华东新区 收货地址", store,
        metric_store=metric_store, value_index=index,
    )
    assert [m["metric"] for m in out["metrics"]][:1] == ["gmv"]
    assert any(t["table"] == "dim.dim_user" for t in out["tables"])
    assert out["value_hits"] == [
        {"value": "华东新区", "table": "dim.dim_user", "column": "city"}]


def test_search_without_optional_stores(assets) -> None:
    store, _, _ = assets
    out = search_catalog("订单 支付金额", store)
    assert out["metrics"] == [] and out["value_hits"] == []
    assert out["tables"][0]["table"] == "dwd.dwd_trade_order_di"


def test_search_empty_query(assets) -> None:
    store, _, _ = assets
    out = search_catalog("   ", store)
    assert out == {"query": "", "tables": [], "metrics": [], "value_hits": []}


def test_render_markdown(assets) -> None:
    store, metric_store, index = assets
    md = render_catalog_markdown(search_catalog(
        "成交总额", store, metric_store=metric_store, value_index=index))
    assert "## 指标" in md and "gmv" in md
    md_empty = render_catalog_markdown(search_catalog(
        "zzz_nothing_matches_zzz", store))
    assert "没有匹配的资产" in md_empty


def test_cli_t2s_search(tmp_path) -> None:
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    ddl = tmp_path / "ddl.sql"
    ddl.write_text(_DDL, encoding="utf-8")
    metrics = tmp_path / "metrics.yaml"
    metrics.write_text(_METRICS, encoding="utf-8")
    result = CliRunner().invoke(cli, [
        "t2s-search", "成交总额", "--ddl", str(ddl),
        "--metrics", str(metrics), "-F", "json",
    ])
    assert result.exit_code == 0, result.output
    assert '"gmv"' in result.output
