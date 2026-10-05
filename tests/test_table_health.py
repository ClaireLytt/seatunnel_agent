"""Tests for the table health score + governance advisor (health.py)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from seatunnel_agent.text2sql.health import (
    render_health_markdown,
    score_tables,
)
from seatunnel_agent.text2sql.schema import SchemaStore, parse_ddl

_DDL = """
CREATE TABLE dwd.hot_orders(
  order_id string COMMENT '订单ID',
  amount double COMMENT '金额'
) COMMENT '订单明细';

CREATE TABLE ods.zombie_raw(
  x string,
  mobile_no string
);

CREATE TABLE dwd.stale_part(
  a string COMMENT '字段A'
) COMMENT '历史分区表' PARTITIONED BY (dt string COMMENT '日期');
"""

_NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _records() -> list[dict]:
    return [
        {"timestamp": "2026-09-30T10:00:00+00:00",
         "matched_tables": ["dwd.hot_orders"]},
        {"timestamp": "2026-09-29T10:00:00+00:00",
         "matched_tables": ["dwd.hot_orders", "dwd.stale_part"]},
    ] + [
        {"timestamp": "2026-05-01T00:00:00+00:00",
         "matched_tables": ["dwd.hot_orders"]},
    ] * 10


class _FakeChain:
    def __init__(self, n: int) -> None:
        self.upstream_count = n
        self.downstream_count = n


class _FakeGraph:
    """hot_orders is wired into lineage; the others are isolated."""

    def upstream_of(self, table, depth=1):
        return _FakeChain(1 if table == "dwd.hot_orders" else 0)

    def downstream_of(self, table, depth=1):
        return _FakeChain(1 if table == "dwd.hot_orders" else 0)


@pytest.fixture()
def store() -> SchemaStore:
    return SchemaStore(parse_ddl(_DDL))


def test_scores_rank_hot_above_zombie(store) -> None:
    report = score_tables(store, _records(), lineage_graph=_FakeGraph(),
                          now=_NOW)
    by_name = {r["table"]: r for r in report["tables"]}
    assert by_name["dwd.hot_orders"]["score"] > by_name["ods.zombie_raw"]["score"]
    # worst-first ordering
    assert report["tables"][0]["score"] <= report["tables"][-1]["score"]
    # components honor documented weights
    assert report["weights"] == {"heat": 40, "docs": 40, "lineage": 20}
    hot = by_name["dwd.hot_orders"]
    assert hot["components"]["lineage"] == 20
    assert hot["query_count"] == 12


def test_zombie_and_stale_and_pii_findings(store) -> None:
    report = score_tables(store, _records(), lineage_graph=_FakeGraph(),
                          now=_NOW, stale_days=90)
    kinds = {(f["kind"], f["table"]) for f in report["findings"]}
    assert ("zombie_table", "ods.zombie_raw") in kinds
    # stale_part was queried 2 days ago -> not stale
    assert ("stale_partitioned", "dwd.stale_part") not in kinds
    pii = [f for f in report["findings"] if f["kind"] == "pii_exposure"]
    assert pii and pii[0]["table"] == "ods.zombie_raw"
    assert "mobile_no" in pii[0]["columns"]


def test_stale_partitioned_when_never_queried(store) -> None:
    report = score_tables(store, [], lineage_graph=None, now=_NOW)
    kinds = {(f["kind"], f["table"]) for f in report["findings"]}
    assert ("stale_partitioned", "dwd.stale_part") in kinds
    # no graph: no zombie detection, no lineage component
    assert not any(f["kind"] == "zombie_table" for f in report["findings"])
    assert report["weights"] == {"heat": 50, "docs": 50}
    assert all("lineage" not in r["components"] for r in report["tables"])


def test_docs_component(store) -> None:
    report = score_tables(store, [], now=_NOW)
    by_name = {r["table"]: r for r in report["tables"]}
    # fully commented table gets the full docs weight
    assert by_name["dwd.hot_orders"]["components"]["docs"] == 50
    # uncommented table gets zero
    assert by_name["ods.zombie_raw"]["components"]["docs"] == 0


def test_deterministic(store) -> None:
    a = score_tables(store, _records(), lineage_graph=_FakeGraph(), now=_NOW)
    b = score_tables(store, _records(), lineage_graph=_FakeGraph(), now=_NOW)
    assert a == b


def test_render_markdown(store) -> None:
    md = render_health_markdown(
        score_tables(store, _records(), lineage_graph=_FakeGraph(), now=_NOW))
    assert "## 健康分排行" in md and "## 治理建议" in md
    assert "zombie_table" in md


def test_cli_t2s_health(tmp_path) -> None:
    from click.testing import CliRunner

    from seatunnel_agent.cli import cli

    ddl = tmp_path / "ddl.sql"
    ddl.write_text(_DDL, encoding="utf-8")
    result = CliRunner().invoke(cli, [
        "t2s-health", "--ddl", str(ddl),
        "--qlog-dir", str(tmp_path / "nolog"), "-F", "json",
    ])
    assert result.exit_code == 0, result.output
    assert '"table_count": 3' in result.output
