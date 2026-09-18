# -*- coding: utf-8 -*-
"""Tests for graph context injection into the lineage agent system prompt."""

from __future__ import annotations

from seatunnel_agent.data_lineage.graph import LineageGraph
from seatunnel_agent.data_lineage.prompts import (
    _MAX_CONTEXT_CHARS,
    build_graph_context,
    build_lineage_prompt,
)


def _make_graph() -> LineageGraph:
    g = LineageGraph()
    # hub has degree 4 (2 up + 2 down); every other table has degree 1 or 2
    g.add_edge("ods.a", "dwd.hub", source="sql", confidence="high")
    g.add_edge("ods.b", "dwd.hub", source="sql", confidence="high")
    g.add_edge("dwd.hub", "dws.x", source="seatunnel", confidence="medium")
    g.add_edge("dwd.hub", "ads.y", source="sql", confidence="low")
    g.add_node("ads.y", layer="ads", is_sla=True, sla_time="08:00")
    return g


def test_empty_graph_returns_empty_context():
    assert build_graph_context(None) == ""
    assert build_graph_context(LineageGraph()) == ""


def test_empty_graph_prompt_unchanged():
    prompt = build_lineage_prompt(LineageGraph())
    assert "EMPTY — load data before querying" in prompt
    assert "Graph Overview" not in prompt


def test_context_contains_stats_and_hot_tables():
    g = _make_graph()
    ctx = build_graph_context(g)
    assert "表数 5" in ctx
    assert "边数 4" in ctx
    assert "SLA 表 1" in ctx
    assert "边来源" in ctx and "sql:3" in ctx and "seatunnel:1" in ctx
    assert "边置信度" in ctx and "high:2" in ctx and "medium:1" in ctx and "low:1" in ctx
    assert "dwd.hub" in ctx
    assert "ads.y(ads, 上游1/下游0, SLA)" in ctx


def test_context_injected_into_prompt():
    g = _make_graph()
    prompt = build_lineage_prompt(g)
    assert "Graph Overview" in prompt
    assert "dwd.hub" in prompt
    assert "## Guide" in prompt


def test_hot_tables_sorted_by_degree_desc():
    g = _make_graph()
    ctx = build_graph_context(g)
    entries = [line for line in ctx.splitlines() if line.startswith("  - ")]
    assert entries[0].startswith("  - dwd.hub(")
    # degree ties break alphabetically
    names = [line.split("- ")[1].split("(")[0] for line in entries]
    assert names.index("dwd.hub") == 0


def test_top20_limit():
    g = LineageGraph()
    for i in range(30):
        g.add_edge(f"ods.t{i:02d}", "dwd.hub")
    ctx = build_graph_context(g)
    entries = [line for line in ctx.splitlines() if line.startswith("  - ")]
    assert len(entries) == 20
    assert entries[0].startswith("  - dwd.hub(")


def test_long_context_truncates_hot_table_list():
    g = LineageGraph()
    long_names = [f"db_{'x' * 200}.table_{i}" for i in range(20)]
    for name in long_names:
        g.add_edge(name, "dwd.hub")
    ctx = build_graph_context(g)
    assert "热点表列表已截断" in ctx
    assert len(ctx) <= _MAX_CONTEXT_CHARS + 250
