# -*- coding: utf-8 -*-
"""Lineage integration into the SQL Review and Data Comparison agents."""

from __future__ import annotations

import json

import pytest

from seatunnel_agent.data_comparison.lineage_link import (
    TOOL_DEFINITION,
    execute_lineage_link_tool,
    trace_common_upstream,
)
from seatunnel_agent.data_lineage.graph import LineageGraph
from seatunnel_agent.sql_review import lineage_context
from seatunnel_agent.sql_review.tools import (
    TOOL_DEFINITIONS,
    SQLReviewRuntime,
    execute_review_tool,
)


@pytest.fixture()
def graph() -> LineageGraph:
    g = LineageGraph()
    g.add_node("zz.ods_orders", layer="ods")
    g.add_node("zz.ods_users", layer="ods")
    g.add_node("zz.dwd_order_detail", layer="dwd")
    g.add_node("zz.dws_city_gmv_df", layer="dws")
    g.add_node("zz.dws_shop_gmv_df", layer="dws")
    g.add_node("zz.ads_gmv_report", layer="ads", is_sla=True, sla_time="09:00")
    g.add_edge("zz.ods_orders", "zz.dwd_order_detail")
    g.add_edge("zz.ods_users", "zz.dwd_order_detail")
    g.add_edge("zz.dwd_order_detail", "zz.dws_city_gmv_df")
    g.add_edge("zz.dwd_order_detail", "zz.dws_shop_gmv_df")
    g.add_edge("zz.dws_city_gmv_df", "zz.ads_gmv_report")
    return g


@pytest.fixture(autouse=True)
def _clean_lineage_cache(monkeypatch):
    monkeypatch.delenv("LINEAGE_SQL_DIR", raising=False)
    monkeypatch.delenv("LINEAGE_SEATUNNEL_DIR", raising=False)
    lineage_context.reset_lineage_cache()
    yield
    lineage_context.reset_lineage_cache()


# ---------------------------------------------------------------------------
# SQL Review: lineage_impact tool
# ---------------------------------------------------------------------------

def test_lineage_impact_registered():
    assert "lineage_impact" in [t["name"] for t in TOOL_DEFINITIONS]


def test_lineage_impact_downstream_with_sla(graph):
    rt = SQLReviewRuntime(
        sql="INSERT OVERWRITE TABLE zz.dws_city_gmv_df SELECT 1",
        lineage_graph=graph,
    )
    out = json.loads(execute_review_tool("lineage_impact", {}, rt))
    assert out["success"] is True
    entry = out["impact"]["zz.dws_city_gmv_df"]
    assert entry["found"] is True
    tables = [d["table"] for d in entry["downstream"]]
    assert tables == ["zz.ads_gmv_report"]
    assert entry["downstream"][0]["is_sla"] is True
    assert entry["sla_affected"] == [{"table": "zz.ads_gmv_report", "sla_time": "09:00"}]


def test_lineage_impact_explicit_table_override(graph):
    rt = SQLReviewRuntime(sql="SELECT 1", lineage_graph=graph)
    out = json.loads(execute_review_tool(
        "lineage_impact", {"table": "zz.dwd_order_detail", "depth": 1}, rt
    ))
    entry = out["impact"]["zz.dwd_order_detail"]
    tables = [d["table"] for d in entry["downstream"]]
    assert tables == ["zz.dws_city_gmv_df", "zz.dws_shop_gmv_df"]


def test_lineage_impact_no_write_target(graph):
    rt = SQLReviewRuntime(sql="SELECT * FROM zz.ods_orders", lineage_graph=graph)
    out = json.loads(execute_review_tool("lineage_impact", {}, rt))
    assert "没有写入目标表" in out["error"]


def test_lineage_impact_missing_table(graph):
    rt = SQLReviewRuntime(sql="SELECT 1", lineage_graph=graph)
    out = json.loads(execute_review_tool(
        "lineage_impact", {"table": "zz.not_exists"}, rt
    ))
    assert out["impact"]["zz.not_exists"]["found"] is False


def test_lineage_impact_unconfigured_hint():
    rt = SQLReviewRuntime(sql="INSERT OVERWRITE TABLE zz.t SELECT 1")
    out = json.loads(execute_review_tool("lineage_impact", {}, rt))
    assert "LINEAGE_SQL_DIR" in out["error"]


# ---------------------------------------------------------------------------
# lineage_context lazy loader
# ---------------------------------------------------------------------------

def test_lineage_context_builds_and_caches(monkeypatch, tmp_path):
    (tmp_path / "job.sql").write_text(
        "INSERT OVERWRITE TABLE zz.dwd_a SELECT * FROM zz.ods_a;",
        encoding="utf-8",
    )
    monkeypatch.setenv("LINEAGE_SQL_DIR", str(tmp_path))
    lineage_context.reset_lineage_cache()
    g1, hint1 = lineage_context.get_lineage_graph()
    assert hint1 == "" and g1 is not None
    assert "zz.dwd_a" in g1.nodes and "zz.ods_a" in g1.nodes
    g2, _ = lineage_context.get_lineage_graph()
    assert g2 is g1


def test_lineage_context_set_graph(graph):
    lineage_context.set_lineage_graph(graph)
    g, hint = lineage_context.get_lineage_graph()
    assert g is graph and hint == ""


# ---------------------------------------------------------------------------
# Data Comparison: trace_common_upstream
# ---------------------------------------------------------------------------

def test_trace_common_upstream(graph):
    out = trace_common_upstream(
        "zz.dws_city_gmv_df", "zz.dws_shop_gmv_df", graph=graph
    )
    assert out["success"] is True
    names = [e["table"] for e in out["common_upstream"]]
    assert names == ["zz.dwd_order_detail", "zz.ods_orders", "zz.ods_users"]
    dwd = out["common_upstream"][0]
    assert dwd["depth_from_a"] == 1 and dwd["depth_from_b"] == 1


def test_trace_common_upstream_none(graph):
    out = trace_common_upstream("zz.ods_orders", "zz.ods_users", graph=graph)
    assert out["success"] is True
    assert out["common_upstream_count"] == 0
    assert "没有公共上游" in out["message"]


def test_trace_common_upstream_missing_table(graph):
    out = trace_common_upstream("zz.nope", "zz.ods_users", graph=graph)
    assert "不存在表 zz.nope" in out["error"]


def test_trace_common_upstream_unconfigured():
    out = trace_common_upstream("a.t1", "a.t2")
    assert "LINEAGE_SQL_DIR" in out["error"]


def test_execute_lineage_link_tool(graph):
    lineage_context.set_lineage_graph(graph)
    raw = execute_lineage_link_tool(
        "trace_common_upstream",
        {"table_a": "zz.dws_city_gmv_df", "table_b": "zz.dws_shop_gmv_df"},
    )
    out = json.loads(raw)
    assert out["success"] is True and out["common_upstream_count"] == 3
    unknown = json.loads(execute_lineage_link_tool("nope", {}))
    assert "Unknown tool" in unknown["error"]
    assert TOOL_DEFINITION["name"] == "trace_common_upstream"
