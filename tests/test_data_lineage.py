# -*- coding: utf-8 -*-
"""Tests for the data lineage module (graph, loaders, render, tools, CLI)."""

from __future__ import annotations

import json

import pytest

from seatunnel_agent.data_lineage.graph import (
    ColumnEdge,
    LineageGraph,
    norm_table,
)
from seatunnel_agent.data_lineage.loaders import (
    build_graph,
    from_hive_meta,
    from_sql_dir,
    from_sql_files,
    resolve_partition,
)
from seatunnel_agent.data_lineage.render import (
    mermaid_html,
    mermaid_id,
    render_column_mermaid,
    render_mermaid,
    render_report,
    render_tree,
)
from seatunnel_agent.data_lineage.report import LineageReport
from seatunnel_agent.data_lineage.rlog import LineageLogger
from seatunnel_agent.data_lineage.tools import (
    LineageRuntime,
    execute_lineage_tool,
)
from seatunnel_agent.data_lineage.agent import static_lineage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def linear_graph(*names: str) -> LineageGraph:
    """a -> b -> c -> ..."""
    g = LineageGraph()
    for src, dst in zip(names, names[1:]):
        g.add_edge(src, dst)
    return g


FIXTURE_DWD = (
    "INSERT OVERWRITE TABLE zz.dwd_orders_df "
    "SELECT o.order_id, o.user_id, o.amount, u.city "
    "FROM zz.ods_orders o JOIN zz.ods_users u ON o.user_id = u.user_id;"
)
FIXTURE_DWS = (
    "INSERT OVERWRITE TABLE zz.dws_city_gmv_df "
    "SELECT city, sum(amount) AS gmv "
    "FROM zz.dwd_orders_df GROUP BY city;"
)


@pytest.fixture
def sql_dir(tmp_path):
    (tmp_path / "dwd_orders.sql").write_text(FIXTURE_DWD, encoding="utf-8")
    (tmp_path / "dws_city.sql").write_text(FIXTURE_DWS, encoding="utf-8")
    return tmp_path


@pytest.fixture
def fixture_graph(sql_dir):
    graph, warnings = from_sql_dir(sql_dir)
    assert warnings == []
    return graph


# ---------------------------------------------------------------------------
# norm_table / graph mutation
# ---------------------------------------------------------------------------

def test_norm_table():
    assert norm_table(" `ZZ`.`Orders` ") == "zz.orders"
    assert norm_table('"t"') == "t"


def test_add_node_upsert_never_downgrades():
    g = LineageGraph()
    g.add_node("zz.t", layer="dwd", source_type="hive")
    g.add_node("zz.t", layer="", source_type="")  # empty must not clobber
    node = g.get("zz.t")
    assert node.layer == "dwd" and node.source_type == "hive"
    assert node.database == "zz" and node.table == "t"


def test_add_node_sla_or_merge_and_baseline_merge():
    g = LineageGraph()
    g.add_node("t", is_sla=True, baselines=["b1"])
    g.add_node("t", is_sla=False, baselines=["b1", "b2"])
    node = g.get("t")
    assert node.is_sla is True
    assert node.baselines == ["b1", "b2"]


def test_add_edge_skips_self_loop():
    g = LineageGraph()
    g.add_edge("t", "T")  # same table after normalization
    assert g.stats()["edges"] == 0


def test_add_column_edge_dedupes():
    g = LineageGraph()
    for _ in range(2):
        g.add_column_edge(ColumnEdge("a", "x", "b", "y"))
    assert g.stats()["column_edges"] == 1


def test_get_unique_bare_name_suffix_match():
    g = linear_graph("zz.orders", "zz.dwd_x")
    assert g.get("orders").name == "zz.orders"
    g.add_node("other.orders")
    assert g.get("orders") is None  # ambiguous now


def test_search_and_stats():
    g = linear_graph("zz.ods_a", "zz.dwd_b", "zz.dws_c")
    g.add_node("zz.dwd_b", layer="dwd")
    g.add_node("zz.dws_c", is_sla=True)
    assert [n.name for n in g.search("dw")] == ["zz.dwd_b", "zz.dws_c"]
    stats = g.stats()
    assert stats["tables"] == 3 and stats["edges"] == 2
    assert stats["sla_tables"] == 1
    assert stats["layers"]["dwd"] == 1


def test_merge_combines_nodes_edges_and_column_edges():
    g1 = linear_graph("a", "b")
    g2 = LineageGraph()
    g2.add_node("b", layer="dwd")
    g2.add_edge("b", "c")
    g2.add_column_edge(ColumnEdge("b", "x", "c", "y"))
    g1.merge(g2)
    stats = g1.stats()
    assert stats["tables"] == 3 and stats["edges"] == 2
    assert stats["column_edges"] == 1 and stats["sla_tables"] == 0
    assert stats["layers"] == {"unknown": 2, "dwd": 1}


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------

def test_trace_cycle_terminates():
    g = linear_graph("a", "b", "c")
    g.add_edge("c", "a")  # cycle
    chain = g.downstream_of("a", depth=10)
    assert set(chain.nodes) == {"a", "b", "c"}
    assert chain.downstream_count == 2


def test_trace_depth_limit_sets_truncated():
    g = linear_graph("a", "b", "c", "d")
    chain = g.downstream_of("a", depth=2)
    assert "d" not in chain.nodes
    assert chain.truncated is True
    full = g.downstream_of("a", depth=3)
    assert "d" in full.nodes and full.truncated is False


def test_trace_max_nodes_truncates():
    g = LineageGraph()
    for i in range(10):
        g.add_edge("root", f"t{i}")
    chain = g.downstream_of("root", depth=1, max_nodes=5)
    assert len(chain.nodes) == 5
    assert chain.truncated is True


def test_trace_missing_root():
    chain = LineageGraph().downstream_of("nope")
    assert chain.missing_root is True
    assert chain.nodes == {}


def test_full_chain_upstream_negative_depths():
    g = linear_graph("a", "b", "c")
    chain = g.full_chain("b")
    assert chain.depth_of == {"b": 0, "a": -1, "c": 1}
    assert chain.upstream_count == 1 and chain.downstream_count == 1
    assert ("a", "b") in chain.edges and ("b", "c") in chain.edges


def test_path_between_forward_and_reverse():
    g = linear_graph("a", "b", "c")
    assert g.path_between("a", "c") == ["a", "b", "c"]
    assert g.path_between("c", "a") == ["a", "b", "c"]  # reverse fallback
    g.add_node("island")
    assert g.path_between("a", "island") is None
    assert g.path_between("a", "missing") is None


def test_impact_of_column_multi_hop():
    g = linear_graph("a", "b", "c")
    g.add_column_edge(ColumnEdge("a", "x", "b", "y"))
    g.add_column_edge(ColumnEdge("b", "y", "c", "z", is_aggregation=True))
    impact = g.impact_of_column("a", "x")
    assert impact.degraded is False
    assert impact.impacted == ["b.y", "c.z"]


def test_impact_of_column_degrades_to_table_level():
    g = linear_graph("a", "b")
    impact = g.impact_of_column("a", "unknown_col")
    assert impact.degraded is True
    assert impact.table_fallback is not None
    assert "b" in impact.table_fallback.nodes


def test_impact_of_column_missing_root():
    impact = LineageGraph().impact_of_column("nope", "x")
    assert impact.missing_root is True


def test_impact_of_leaf_column_is_empty_not_degraded():
    g = linear_graph("a", "b")
    g.add_column_edge(ColumnEdge("a", "x", "b", "y"))
    impact = g.impact_of_column("b", "y")  # known leaf: consumed nowhere
    assert impact.degraded is False
    assert impact.impacted == []


# ---------------------------------------------------------------------------
# SQL loader
# ---------------------------------------------------------------------------

def test_from_sql_dir_fixture(fixture_graph):
    stats = fixture_graph.stats()
    assert stats["tables"] == 4
    assert stats["edges"] == 3
    assert stats["column_edges"] == 6
    assert "zz.dwd_orders_df" in fixture_graph.downstream["zz.ods_orders"]
    assert "zz.dws_city_gmv_df" in fixture_graph.downstream["zz.dwd_orders_df"]


def test_sql_loader_unqualified_column_attributed_to_sole_source(fixture_graph):
    # sum(amount) has no table qualifier; with one FROM table it is attributable
    impact = fixture_graph.impact_of_column("zz.ods_orders", "amount")
    assert impact.degraded is False
    assert impact.impacted == ["zz.dwd_orders_df.amount", "zz.dws_city_gmv_df.gmv"]
    assert any(e.is_aggregation for e in impact.edges)


def test_sql_loader_origin_recorded(fixture_graph):
    origins = fixture_graph.get("zz.dwd_orders_df").origins
    assert "sql:dwd_orders.sql" in origins


def test_sql_loader_cte_not_a_node(tmp_path):
    (tmp_path / "q.sql").write_text(
        "with base as (select id from zz.ods_t where pt='1') "
        "select * from base",
        encoding="utf-8",
    )
    graph, _ = from_sql_dir(tmp_path)
    assert graph.get("zz.ods_t") is not None
    assert "base" not in graph.nodes


def test_from_sql_files_missing_file_warns():
    graph, warnings = from_sql_files(["no/such/file.sql"])
    assert graph.stats()["tables"] == 0
    assert warnings and "无法读取" in warnings[0]


def test_from_sql_dir_empty_warns(tmp_path):
    graph, warnings = from_sql_dir(tmp_path)
    assert graph.stats()["tables"] == 0
    assert warnings and "没有找到" in warnings[0]


# ---------------------------------------------------------------------------
# Hive loader (DummyExecutor)
# ---------------------------------------------------------------------------

_META_COLS = [
    "source_type_name", "database_name", "table_name", "table_layer",
    "relation_source_type_name", "relation_database_name",
    "relation_table_name", "relation_layer",
    "is_relation_sla_type", "relation_sla_time",
    "relation_base_line_name_list",
]


class _Result:
    def __init__(self, columns, rows):
        self.columns = columns
        self.rows = rows


class DummyExecutor:
    def __init__(self, rows, max_partition="20260916"):
        self._rows = rows
        self._max_partition = max_partition
        self.queries = []

    def get_max_partition(self, table):
        return self._max_partition

    def run(self, sql, max_rows=None):
        self.queries.append(sql)
        if sql.strip().lower().startswith("select max(pt)"):
            return _Result(["_c0"], [(self._max_partition,)] if self._max_partition else [])
        return _Result(_META_COLS, self._rows)


def _meta_row(**kw):
    row = dict.fromkeys(_META_COLS, None)
    row.update(kw)
    return tuple(row[c] for c in _META_COLS)


def test_from_hive_meta_builds_downstream_edges():
    rows = [
        _meta_row(source_type_name="hive", database_name="zz",
                  table_name="dwd_a", table_layer="dwd",
                  relation_source_type_name="doris", relation_database_name="zz",
                  relation_table_name="ads_b", relation_layer="ads",
                  is_relation_sla_type=1, relation_sla_time="09:00",
                  relation_base_line_name_list="['核心基线','报表基线']"),
        # leaf row: NULL relation -> node only
        _meta_row(source_type_name="kafka", database_name="",
                  table_name="topic_x"),
    ]
    graph = from_hive_meta(DummyExecutor(rows), partition="20260916")
    assert graph.stats()["tables"] == 3
    assert "zz.ads_b" in graph.downstream["zz.dwd_a"]
    down = graph.get("zz.ads_b")
    assert down.is_sla is True and down.sla_time == "09:00"
    assert down.baselines == ["核心基线", "报表基线"]
    assert down.source_type == "doris" and down.layer == "ads"
    assert graph.get("topic_x").source_type == "kafka"


@pytest.mark.parametrize("raw,expected", [
    (1, True), ("1", True), ("true", True), ("是", True),
    (0, False), ("0", False), (None, False), ("no", False),
])
def test_hive_sla_bool_variants(raw, expected):
    rows = [_meta_row(database_name="a", table_name="t",
                      relation_database_name="a", relation_table_name="d",
                      is_relation_sla_type=raw)]
    graph = from_hive_meta(DummyExecutor(rows), partition="20260916")
    assert graph.get("a.d").is_sla is expected


@pytest.mark.parametrize("raw,expected", [
    ("['a','b']", ["a", "b"]),
    ("a,b", ["a", "b"]),
    ("[]", []),
    (None, []),
    ("null", []),
])
def test_hive_baseline_list_formats(raw, expected):
    rows = [_meta_row(database_name="a", table_name="t",
                      relation_database_name="a", relation_table_name="d",
                      relation_base_line_name_list=raw)]
    graph = from_hive_meta(DummyExecutor(rows), partition="20260916")
    assert graph.get("a.d").baselines == expected


def test_resolve_partition_show_partitions_first():
    ex = DummyExecutor([], max_partition="20260901")
    assert resolve_partition(ex, "zz.meta") == "20260901"
    assert ex.queries == []  # no SQL needed


def test_resolve_partition_max_pt_fallback():
    class NoShow(DummyExecutor):
        def get_max_partition(self, table):
            return None
    ex = NoShow([], max_partition="20260902")
    assert resolve_partition(ex, "zz.meta") == "20260902"
    assert "max(pt)" in ex.queries[0]


def test_resolve_partition_all_empty_raises():
    class NoShow(DummyExecutor):
        def get_max_partition(self, table):
            return None
    with pytest.raises(RuntimeError, match="最新分区"):
        resolve_partition(NoShow([], max_partition=None), "zz.meta")


def test_from_hive_meta_rejects_bad_names():
    with pytest.raises(ValueError, match="表名"):
        from_hive_meta(DummyExecutor([]), meta_table="zz.t; drop table x")
    with pytest.raises(ValueError, match="分区"):
        from_hive_meta(DummyExecutor([]), partition="1' or '1'='1")


def test_from_hive_meta_uses_latest_partition_in_where():
    ex = DummyExecutor([], max_partition="20260916")
    from_hive_meta(ex, meta_table="zz.meta")
    assert any("pt = '20260916'" in q for q in ex.queries)


def test_from_hive_meta_blank_partition_auto_resolves():
    ex = DummyExecutor([], max_partition="20260916")
    from_hive_meta(ex, meta_table="zz.meta", partition="  ")
    assert any("pt = '20260916'" in q for q in ex.queries)


# ---------------------------------------------------------------------------
# build_graph orchestration
# ---------------------------------------------------------------------------

def test_build_graph_hive_unconfigured_raises_without_sql(monkeypatch):
    monkeypatch.delenv("HIVE_HOST", raising=False)
    with pytest.raises(RuntimeError, match="HIVE_HOST"):
        build_graph(use_hive=True)


def test_build_graph_hive_unconfigured_degrades_with_sql(monkeypatch, sql_dir):
    monkeypatch.delenv("HIVE_HOST", raising=False)
    graph, warnings = build_graph(sql_dir=sql_dir, use_hive=True)
    assert graph.stats()["tables"] == 4
    assert any("HIVE_HOST" in w for w in warnings)


def test_build_graph_executor_creation_failure_degrades_with_sql(monkeypatch, sql_dir):
    import seatunnel_agent.data_lineage.loaders as loaders_mod

    def boom():
        raise ImportError("pyhive is not installed")

    monkeypatch.setattr(loaders_mod, "hive_executor_from_env", boom)
    graph, warnings = build_graph(sql_dir=sql_dir, use_hive=True)
    assert graph.stats()["tables"] == 4
    assert any("降级" in w and "pyhive" in w for w in warnings)


def test_build_graph_executor_creation_failure_raises_without_sql(monkeypatch):
    import seatunnel_agent.data_lineage.loaders as loaders_mod

    def boom():
        raise ImportError("pyhive is not installed")

    monkeypatch.setattr(loaders_mod, "hive_executor_from_env", boom)
    with pytest.raises(ImportError, match="pyhive"):
        build_graph(use_hive=True)


def test_build_graph_sql_only(sql_dir):
    graph, warnings = build_graph(sql_dir=sql_dir)
    assert warnings == []
    assert graph.stats()["edges"] == 3


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def test_mermaid_id_sanitized():
    assert mermaid_id("zz.dwd-a b") == "zz_dwd_a_b"
    assert mermaid_id("1table").startswith("t_")
    assert mermaid_id("") == "unknown"


def test_render_mermaid_structure():
    g = linear_graph("zz.ods_a", "zz.dwd_b", "zz.dws_c")
    g.add_node("zz.dwd_b", layer="dwd")
    g.add_node("zz.dws_c", is_sla=True, sla_time="08:30")
    src = render_mermaid(g.full_chain("zz.dwd_b"))
    assert src.startswith("flowchart LR")
    assert "zz_ods_a --> zz_dwd_b" in src
    assert "classDef layer_dwd" in src
    assert "classDef sla_mark" in src
    assert "classDef root_mark" in src
    assert "<b>" in src  # root label bold
    assert "⏰ SLA 08:30" in src


def test_render_mermaid_missing_root():
    src = render_mermaid(LineageGraph().downstream_of("nope"))
    assert "未找到表" in src


def test_render_mermaid_node_cap_notes_truncation():
    g = LineageGraph()
    for i in range(10):
        g.add_edge("root", f"t{i}")
    src = render_mermaid(g.downstream_of("root", depth=1), max_nodes=5)
    assert "已截断" in src
    assert src.count("-->") < 10


def test_render_mermaid_id_collision_kept_distinct():
    g = LineageGraph()
    g.add_edge("a.b-c", "a.b_c")  # both sanitize to a_b_c
    src = render_mermaid(g.downstream_of("a.b-c"))
    assert 'a_b_c["' in src and 'a_b_c_2["' in src
    assert "a_b_c --> a_b_c_2" in src or "a_b_c_2 --> a_b_c" in src


def test_render_column_mermaid_aggregation_label():
    g = linear_graph("a", "b")
    g.add_column_edge(ColumnEdge("a", "x", "b", "y", is_aggregation=True))
    src = render_column_mermaid(g.impact_of_column("a", "x"))
    assert "-->|聚合|" in src


def test_render_tree_directions_and_sla():
    g = linear_graph("a", "b", "c")
    g.add_node("c", is_sla=True)
    tree = render_tree(g.full_chain("b"))
    assert "⬆ `a`" in tree
    assert "**`b`**（当前表）" in tree
    assert "⬇ `c`" in tree and "⏰SLA" in tree


def test_render_tree_upstream_nearest_first_zero_indent():
    g = linear_graph("far", "near", "root")
    lines = render_tree(g.upstream_of("root", depth=5)).splitlines()
    assert lines[0] == "- ⬆ `near`"  # no leading spaces → never a code block
    assert lines[1] == "  - ⬆ `far`"


def test_render_report_sections(fixture_graph):
    report = static_lineage(fixture_graph, "zz.dwd_orders_df", "both", 3,
                            column="amount")
    md = render_report(report)
    for section in ("## 血缘分析报告：`zz.dwd_orders_df`", "### 血缘图",
                    "```mermaid", "### 链路概览", "### SLA 与基线",
                    "### 字段影响分析"):
        assert section in md


def test_render_report_sla_table():
    g = linear_graph("a", "b")
    g.add_node("b", is_sla=True, sla_time="09:00", baselines=["基线1"])
    report = static_lineage(g, "a", "downstream", 3)
    md = render_report(report)
    assert "| `b` |" in md and "09:00" in md and "基线1" in md


def test_render_report_degraded_impact_disclosed():
    g = linear_graph("a", "b")
    report = static_lineage(g, "a", "downstream", 3, column="ghost")
    md = render_report(report)
    assert "降级为**表级**" in md


def test_mermaid_html_escapes_source():
    doc = mermaid_html('flowchart LR\n  a["<b>x</b>"]')
    assert "mermaid.min.js" in doc
    assert "<b>x</b>" not in doc
    assert "&lt;b&gt;x&lt;/b&gt;" in doc


# ---------------------------------------------------------------------------
# LineageReport
# ---------------------------------------------------------------------------

def test_report_autofills_sla_and_baseline_nodes():
    g = linear_graph("a", "b")
    g.add_node("b", is_sla=True, baselines=["x"])
    report = LineageReport(root_table="a", chain=g.downstream_of("a"))
    assert [n.name for n in report.sla_nodes] == ["b"]
    assert [n.name for n in report.baseline_nodes] == ["b"]
    d = report.to_dict()
    assert d["stats"]["downstream"] == 1


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def _runtime(graph):
    return LineageRuntime(graph=graph)


def test_tool_unknown():
    out = json.loads(execute_lineage_tool("nope", {}, _runtime(LineageGraph())))
    assert "error" in out


def test_tool_get_downstream_payload(fixture_graph):
    rt = _runtime(fixture_graph)
    out = json.loads(execute_lineage_tool(
        "get_downstream", {"table": "zz.ods_orders", "depth": 3}, rt))
    assert out["downstream_count"] == 2
    assert "zz.dwd_orders_df" in out["tree"]
    assert rt.last_chain is not None


def test_tool_missing_table_error_with_suggestions(fixture_graph):
    out = json.loads(execute_lineage_tool(
        "get_upstream", {"table": "zz.dwd_nope_df"}, _runtime(fixture_graph)))
    assert "不在血缘图中" in out["error"]
    assert isinstance(out["suggestions"], list)


def test_tool_impact_analysis(fixture_graph):
    rt = _runtime(fixture_graph)
    out = json.loads(execute_lineage_tool(
        "impact_analysis", {"table": "zz.ods_orders", "column": "amount"}, rt))
    assert out["degraded"] is False
    assert "zz.dws_city_gmv_df.gmv" in out["impacted"]


def test_tool_impact_degraded_includes_fallback_tree(fixture_graph):
    rt = _runtime(fixture_graph)
    out = json.loads(execute_lineage_tool(
        "impact_analysis", {"table": "zz.ods_orders", "column": "ghost"}, rt))
    assert out["degraded"] is True
    assert "table_fallback_tree" in out
    assert rt.last_chain is not None  # fallback becomes the reportable chain


def test_tool_search_and_detail(fixture_graph):
    rt = _runtime(fixture_graph)
    out = json.loads(execute_lineage_tool(
        "search_tables", {"keyword": "orders"}, rt))
    assert out["count"] == 2
    detail = json.loads(execute_lineage_tool(
        "get_table_detail", {"table": "zz.dwd_orders_df"}, rt))
    assert detail["detail"]["表名"] == "dwd_orders_df"
    up_names = [e["table"] for e in detail["direct_upstream"]]
    assert "zz.ods_orders" in up_names
    down = detail["direct_downstream"]
    assert [e["table"] for e in down] == ["zz.dws_city_gmv_df"]


def test_tool_submit_requires_prior_query(fixture_graph):
    out = json.loads(execute_lineage_tool(
        "submit_lineage_report", {"root_table": "x", "summary": "s"},
        _runtime(fixture_graph)))
    assert "error" in out


def test_tool_submit_report_after_query(fixture_graph):
    rt = _runtime(fixture_graph)
    execute_lineage_tool("get_full_chain", {"table": "zz.dwd_orders_df"}, rt)
    out = json.loads(execute_lineage_tool(
        "submit_lineage_report",
        {"root_table": "zz.dwd_orders_df", "summary": "总体结论文本"}, rt))
    assert out["success"]
    assert "血缘分析报告" in out["report"]
    assert "总体结论文本" in out["report"]
    assert rt.last_report == out["report"]
    assert rt.last_mermaid.startswith("flowchart LR")


def test_tool_hive_load_unavailable():
    rt = LineageRuntime(hive_available=False)
    out = json.loads(execute_lineage_tool("load_lineage_from_hive", {}, rt))
    assert "Hive" in out["error"]


def test_tool_sql_load_without_dir():
    rt = LineageRuntime(sql_dir=None)
    out = json.loads(execute_lineage_tool("load_lineage_from_sql", {}, rt))
    assert "SQL 目录" in out["error"]


def test_tool_depth_clamped(fixture_graph):
    rt = _runtime(fixture_graph)
    out = json.loads(execute_lineage_tool(
        "get_downstream", {"table": "zz.ods_orders", "depth": 999}, rt))
    assert out["downstream_count"] == 2  # no crash, clamped internally


# ---------------------------------------------------------------------------
# static_lineage (no-LLM entry point)
# ---------------------------------------------------------------------------

def test_static_lineage_end_to_end(fixture_graph):
    report = static_lineage(fixture_graph, "zz.dwd_orders_df", "both", 3,
                            column="amount")
    assert report.chain.upstream_count == 2
    assert report.chain.downstream_count == 1
    assert report.column_impact is not None
    assert report.mermaid.startswith("flowchart LR")


def test_static_lineage_missing_root(fixture_graph):
    report = static_lineage(fixture_graph, "zz.nope", "both", 3)
    assert report.chain.missing_root is True
    assert "未在血缘图中找到表" in render_report(report)


# ---------------------------------------------------------------------------
# LineageLogger
# ---------------------------------------------------------------------------

def test_logger_log_and_recent(tmp_path):
    logger = LineageLogger(log_dir=tmp_path)
    logger.log(query="zz.t", direction="both", mode="static", source="cli",
               graph_stats={"tables": 4}, chain_stats={"upstream": 2},
               elapsed_ms=7)
    recs = logger.recent()
    assert len(recs) == 1
    r = recs[0]
    assert r["query"] == "zz.t" and r["mode"] == "static"
    assert r["graph_stats"]["tables"] == 4
    assert r["elapsed_ms"] == 7


def test_logger_skips_corrupt_lines(tmp_path):
    logger = LineageLogger(log_dir=tmp_path)
    logger.log(query="a")
    with open(logger.log_file, "a", encoding="utf-8") as f:
        f.write("{broken\n")
    logger.log(query="b")
    assert [r["query"] for r in logger.recent()] == ["a", "b"]


def test_logger_recent_empty(tmp_path):
    assert LineageLogger(log_dir=tmp_path / "none").recent() == []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

from click.testing import CliRunner

from seatunnel_agent.cli import cli as _cli_root


def _run_cli(args):
    return CliRunner().invoke(_cli_root, args)


def test_cli_lineage_markdown(sql_dir):
    r = _run_cli(["lineage", "-t", "zz.dwd_orders_df",
                  "--sql-dir", str(sql_dir)])
    assert r.exit_code == 0
    assert "血缘分析报告" in r.output


def test_cli_lineage_mermaid_format(sql_dir):
    r = _run_cli(["lineage", "-t", "zz.dwd_orders_df",
                  "--sql-dir", str(sql_dir), "-F", "mermaid"])
    assert r.exit_code == 0
    assert "flowchart LR" in r.output


def test_cli_lineage_json_format(sql_dir, tmp_path):
    # rich console wraps long stdout lines, so parse from a file instead
    out = tmp_path / "report.json"
    r = _run_cli(["lineage", "-t", "zz.dwd_orders_df",
                  "--sql-dir", str(sql_dir), "-F", "json", "-o", str(out)])
    assert r.exit_code == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["root_table"] == "zz.dwd_orders_df"


def test_cli_lineage_column_impact(sql_dir):
    r = _run_cli(["lineage", "-t", "zz.ods_orders", "-c", "amount",
                  "--sql-dir", str(sql_dir)])
    assert r.exit_code == 0
    assert "字段影响分析" in r.output
    assert "zz.dws_city_gmv_df.gmv" in r.output


def test_cli_lineage_missing_table_suggests(sql_dir):
    r = _run_cli(["lineage", "-t", "zz.city_gmv",
                  "--sql-dir", str(sql_dir)])
    assert r.exit_code == 1
    assert "zz.dws_city_gmv_df" in r.output  # suggestion listed


def test_cli_lineage_requires_source():
    r = _run_cli(["lineage", "-t", "zz.t"])
    assert r.exit_code != 0


def test_cli_lineage_requires_table_without_agent(sql_dir):
    r = _run_cli(["lineage", "--sql-dir", str(sql_dir)])
    assert r.exit_code != 0


def test_cli_lineage_output_file(sql_dir, tmp_path):
    out = tmp_path / "report.md"
    r = _run_cli(["lineage", "-t", "zz.dwd_orders_df",
                  "--sql-dir", str(sql_dir), "-o", str(out)])
    assert r.exit_code == 0
    assert "血缘分析报告" in out.read_text(encoding="utf-8")


def test_cli_lineage_stats_runs():
    r = _run_cli(["lineage-stats"])
    assert r.exit_code == 0


# ---------------------------------------------------------------------------
# Path query / SLA impact / health check
# ---------------------------------------------------------------------------

def _sla_graph() -> LineageGraph:
    g = linear_graph("zz.ods_a", "zz.dwd_b", "zz.dws_c", "zz.ads_d")
    g.add_node("zz.dws_c", is_sla=True, sla_time="05:30", layer="dws")
    g.add_node("zz.ads_d", baselines=["核心基线"], layer="ads")
    return g


def test_path_between_reverse_fallback():
    g = linear_graph("a", "b", "c")
    assert g.path_between("c", "a") == ["a", "b", "c"]


def test_find_cycles_detects_and_dag_clean():
    g = linear_graph("a", "b", "c")
    assert g.find_cycles() == []
    g.add_edge("c", "a")
    cycles = g.find_cycles()
    assert len(cycles) == 1
    assert cycles[0][0] == cycles[0][-1]
    assert set(cycles[0]) == {"a", "b", "c"}


def test_isolated_and_no_downstream_disjoint():
    g = linear_graph("a", "b")
    g.add_node("lonely")
    assert g.isolated_tables() == ["lonely"]
    assert g.tables_without_downstream() == ["b"]


def test_sla_impact_orders_by_hops_and_missing_root():
    g = _sla_graph()
    impact = g.sla_impact("zz.ods_a", delay_hours=2)
    assert [n.name for n, _ in impact.affected] == ["zz.dws_c", "zz.ads_d"]
    assert [h for _, h in impact.affected] == [2, 3]
    assert impact.delay_hours == 2
    missing = g.sla_impact("zz.nope")
    assert missing.missing_root is True


def test_render_sla_impact_chinese_labels():
    from seatunnel_agent.data_lineage.render import render_sla_impact

    text = render_sla_impact(_sla_graph().sla_impact("zz.ods_a", 2.5))
    assert "SLA 延迟影响分析" in text and "2.5 小时" in text
    assert "SLA产出时间" in text and "所在基线" in text
    assert "05:30" in text and "核心基线" in text


def test_render_health_sections():
    from seatunnel_agent.data_lineage.render import render_health

    g = linear_graph("a", "b")
    g.add_edge("b", "a")
    g.add_node("lonely")
    text = render_health(g.health_check())
    assert "环依赖（1 个）" in text
    assert "`lonely`" in text
    assert "血缘治理体检报告" in text


def test_render_path_and_mermaid():
    from seatunnel_agent.data_lineage.render import render_path, render_path_mermaid

    g = linear_graph("a", "b", "c")
    path = g.path_between("a", "c")
    md = render_path(path, "a", "c", g)
    assert "共 **2** 跳" in md
    mermaid = render_path_mermaid(path, g)
    assert "flowchart LR" in mermaid and "a --> b" in mermaid
    assert "没有找到血缘路径" in render_path(None, "a", "x", g)


def test_tool_find_path_and_missing_suggestions(fixture_graph):
    rt = LineageRuntime(graph=fixture_graph)
    out = json.loads(execute_lineage_tool(
        "find_path", {"src": "zz.ods_orders", "dst": "zz.dws_city_gmv_df"}, rt
    ))
    assert out["found"] is True and out["hops"] == 2
    bad = json.loads(execute_lineage_tool(
        "find_path", {"src": "zz.city_gmv", "dst": "zz.ods_orders"}, rt
    ))
    assert "error" in bad and "zz.dws_city_gmv_df" in bad["suggestions"]


def test_tool_sla_impact_payload():
    rt = LineageRuntime(graph=_sla_graph())
    out = json.loads(execute_lineage_tool(
        "sla_impact", {"table": "zz.ods_a", "delay_hours": 1}, rt
    ))
    assert out["delay_hours"] == 1
    assert [a["name"] for a in out["affected"]] == ["zz.dws_c", "zz.ads_d"]
    assert "SLA 延迟影响分析" in out["markdown"]


def test_tool_health_check_and_empty_graph():
    rt = LineageRuntime(graph=LineageGraph())
    assert "error" in json.loads(execute_lineage_tool("health_check", {}, rt))
    rt = LineageRuntime(graph=_sla_graph())
    out = json.loads(execute_lineage_tool("health_check", {}, rt))
    assert out["cycles"] == [] and "血缘治理体检报告" in out["markdown"]


def test_cli_lineage_path_to(sql_dir):
    r = _run_cli(["lineage", "-t", "zz.ods_orders", "--path-to",
                  "zz.dws_city_gmv_df", "--sql-dir", str(sql_dir)])
    assert r.exit_code == 0
    assert "共 **2** 跳" in r.output


def test_cli_lineage_sla_delay(sql_dir):
    r = _run_cli(["lineage", "-t", "zz.ods_orders", "--sla-delay", "3",
                  "--sql-dir", str(sql_dir)])
    assert r.exit_code == 0
    assert "SLA 延迟影响分析" in r.output


def test_cli_lineage_check(sql_dir):
    r = _run_cli(["lineage", "--check", "--sql-dir", str(sql_dir)])
    assert r.exit_code == 0
    assert "血缘治理体检报告" in r.output


# ---------------------------------------------------------------------------
# SeaTunnel config loader
# ---------------------------------------------------------------------------

from seatunnel_agent.data_lineage.seatunnel_loader import (
    collect_seatunnel_files,
    from_seatunnel_dir,
    from_seatunnel_files,
)

FIXTURE_ST_JDBC = '''
env {
  parallelism = 2  # execution comment
}
source {
  Jdbc {
    url = "jdbc:mysql://localhost:3306/test_db"
    query = """SELECT id, name FROM test_db.users WHERE id > 0"""
  }
}
transform {}
sink {
  Hive {
    table_name = "zz.dws_users_df"
  }
}
'''

FIXTURE_ST_CDC = '''
source {
  MySQL-CDC {
    database-name = "test_db"
    table-name = "orders"   // inline comment
  }
}
sink {
  Console {}
  Doris {
    database = "dw"
    table = "dwd_orders, dwd_orders_ext"
  }
}
'''


@pytest.fixture
def st_dir(tmp_path):
    d = tmp_path / "st_jobs"
    d.mkdir()
    (d / "job_jdbc.conf").write_text(FIXTURE_ST_JDBC, encoding="utf-8")
    (d / "job_cdc.config").write_text(FIXTURE_ST_CDC, encoding="utf-8")
    (d / "notes.txt").write_text("not a config", encoding="utf-8")
    return d


def test_collect_seatunnel_files_suffix_filter(st_dir):
    names = [p.name for p in collect_seatunnel_files(st_dir)]
    assert names == ["job_cdc.config", "job_jdbc.conf"]


def test_seatunnel_query_source_to_sink(st_dir):
    graph, warnings = from_seatunnel_files([st_dir / "job_jdbc.conf"])
    assert warnings == []
    assert graph.downstream["test_db.users"] == {"zz.dws_users_df"}
    assert graph.get("zz.dws_users_df").source_type == "Hive"
    assert "seatunnel:job_jdbc.conf" in graph.get("test_db.users").origins


def test_seatunnel_dash_keys_db_qualify_and_multi_table(st_dir):
    graph, warnings = from_seatunnel_files([st_dir / "job_cdc.config"])
    assert warnings == []
    assert graph.downstream["test_db.orders"] == {
        "dw.dwd_orders", "dw.dwd_orders_ext",
    }
    assert graph.get("test_db.orders").source_type == "MySQL-CDC"


def test_from_seatunnel_dir_merges_all_configs(st_dir):
    graph, warnings = from_seatunnel_dir(st_dir)
    assert warnings == []
    stats = graph.stats()
    assert stats["tables"] == 5
    assert stats["edges"] == 3


def test_from_seatunnel_dir_empty_warns(tmp_path):
    graph, warnings = from_seatunnel_dir(tmp_path)
    assert graph.stats()["tables"] == 0
    assert warnings and "SeaTunnel" in warnings[0]


def test_from_seatunnel_files_missing_file_warns():
    graph, warnings = from_seatunnel_files(["no/such/job.conf"])
    assert graph.stats()["tables"] == 0
    assert warnings and "无法读取" in warnings[0]


def test_build_graph_merges_sql_and_seatunnel(sql_dir, st_dir):
    graph, warnings = build_graph(sql_dir=sql_dir, seatunnel_dir=st_dir)
    assert warnings == []
    assert graph.get("zz.dwd_orders_df") is not None   # from SQL
    assert graph.get("zz.dws_users_df") is not None    # from SeaTunnel


def test_tool_load_from_seatunnel(st_dir):
    rt = LineageRuntime(graph=LineageGraph())
    out = json.loads(execute_lineage_tool("load_lineage_from_seatunnel", {}, rt))
    assert "error" in out
    rt = LineageRuntime(graph=LineageGraph(), seatunnel_dir=str(st_dir))
    out = json.loads(execute_lineage_tool("load_lineage_from_seatunnel", {}, rt))
    assert out["success"] is True
    assert out["graph"]["tables"] == 5


def test_cli_lineage_seatunnel_dir(st_dir):
    r = _run_cli(["lineage", "-t", "test_db.users",
                  "--seatunnel-dir", str(st_dir)])
    assert r.exit_code == 0
    assert "血缘分析报告" in r.output


# ---------------------------------------------------------------------------
# Hive graph local TTL cache
# ---------------------------------------------------------------------------

import os as _os
import time as _time

from seatunnel_agent.data_lineage.cache import (
    _cache_path,
    graph_from_dict,
    graph_to_dict,
    load_cached_graph,
    save_cached_graph,
)


def _rich_graph() -> LineageGraph:
    g = linear_graph("zz.a", "zz.b")
    g.add_node("zz.b", layer="dws", is_sla=True, sla_time="05:30",
               baselines=["核心基线"], origins={"hive_meta"})
    g.add_column_edge(ColumnEdge("zz.a", "x", "zz.b", "y", "sum(x)", True))
    return g


def test_cache_graph_roundtrip():
    restored = graph_from_dict(graph_to_dict(_rich_graph()))
    assert restored.stats() == _rich_graph().stats()
    node = restored.get("zz.b")
    assert node.is_sla and node.sla_time == "05:30"
    assert node.baselines == ["核心基线"] and "hive_meta" in node.origins
    edge = restored.column_down[("zz.a", "x")][0]
    assert edge.dst_column == "y" and edge.is_aggregation is True


def test_cache_save_and_load(tmp_path, monkeypatch):
    monkeypatch.delenv("LINEAGE_CACHE_TTL", raising=False)
    save_cached_graph(_rich_graph(), "zz.meta", "20260917", base=tmp_path)
    cached = load_cached_graph("zz.meta", "20260917", base=tmp_path)
    assert cached is not None and cached.stats()["tables"] == 2
    assert load_cached_graph("zz.meta", "20260916", base=tmp_path) is None


def test_cache_expires_after_ttl(tmp_path, monkeypatch):
    monkeypatch.delenv("LINEAGE_CACHE_TTL", raising=False)
    save_cached_graph(_rich_graph(), "zz.meta", "20260917", base=tmp_path)
    path = _cache_path("zz.meta", "20260917", base=tmp_path)
    old = _time.time() - 7200
    _os.utime(path, (old, old))
    assert load_cached_graph("zz.meta", "20260917", base=tmp_path) is None


def test_cache_ttl_zero_disables(tmp_path, monkeypatch):
    monkeypatch.setenv("LINEAGE_CACHE_TTL", "0")
    save_cached_graph(_rich_graph(), "zz.meta", "20260917", base=tmp_path)
    assert not _cache_path("zz.meta", "20260917", base=tmp_path).exists()
    monkeypatch.setenv("LINEAGE_CACHE_TTL", "3600")
    save_cached_graph(_rich_graph(), "zz.meta", "20260917", base=tmp_path)
    monkeypatch.setenv("LINEAGE_CACHE_TTL", "0")
    assert load_cached_graph("zz.meta", "20260917", base=tmp_path) is None


def test_cache_corrupt_file_ignored(tmp_path, monkeypatch):
    monkeypatch.delenv("LINEAGE_CACHE_TTL", raising=False)
    path = _cache_path("zz.meta", "20260917", base=tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    assert load_cached_graph("zz.meta", "20260917", base=tmp_path) is None


def test_build_graph_hive_cache_hit_needs_no_executor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LINEAGE_CACHE_TTL", raising=False)
    save_cached_graph(_rich_graph(), "zz.meta_lineage", "20260917")

    def _boom():
        raise AssertionError("executor must not be created on a cache hit")

    monkeypatch.setattr(
        "seatunnel_agent.data_lineage.loaders.hive_executor_from_env", _boom
    )
    graph, warnings = build_graph(
        use_hive=True, meta_table="zz.meta_lineage", partition="20260917",
    )
    assert graph.get("zz.a") is not None
    assert any("缓存" in w for w in warnings)


def test_build_graph_no_cache_forces_refresh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LINEAGE_CACHE_TTL", raising=False)
    save_cached_graph(_rich_graph(), "zz.meta_lineage", "20260917")
    monkeypatch.setattr(
        "seatunnel_agent.data_lineage.loaders.hive_executor_from_env",
        lambda: None,
    )
    with pytest.raises(Exception):
        build_graph(
            use_hive=True, meta_table="zz.meta_lineage",
            partition="20260917", use_cache=False,
        )


# ---------------------------------------------------------------------------
# sqlglot optional column lineage (extras: lineage)
# ---------------------------------------------------------------------------

from seatunnel_agent.data_lineage import sqlglot_lineage as _sgl
from seatunnel_agent.data_lineage.sqlglot_lineage import extract_column_edges

needs_sqlglot = pytest.mark.skipif(
    _sgl.sqlglot is None, reason="sqlglot 未安装（pip install .[lineage]）"
)


def test_extract_returns_none_without_sqlglot(monkeypatch):
    monkeypatch.setattr(_sgl, "sqlglot", None)
    assert extract_column_edges(FIXTURE_DWD, "zz.dwd_orders_df", []) is None


@needs_sqlglot
def test_sqlglot_join_alias_qualification():
    edges = extract_column_edges(
        FIXTURE_DWD.rstrip(";"), "zz.dwd_orders_df",
        ["zz.ods_orders", "zz.ods_users"],
    )
    assert edges is not None
    got = {(e.src_table, e.src_column, e.dst_column) for e in edges}
    assert ("zz.ods_orders", "order_id", "order_id") in got
    assert ("zz.ods_orders", "amount", "amount") in got
    assert ("zz.ods_users", "city", "city") in got
    assert all(not e.is_aggregation for e in edges)


@needs_sqlglot
def test_sqlglot_aggregation_and_sole_source():
    edges = extract_column_edges(
        FIXTURE_DWS.rstrip(";"), "zz.dws_city_gmv_df", ["zz.dwd_orders_df"]
    )
    assert edges is not None
    by_dst = {e.dst_column: e for e in edges}
    gmv = by_dst["gmv"]
    assert gmv.src_table == "zz.dwd_orders_df"
    assert gmv.src_column == "amount"
    assert gmv.is_aggregation is True
    assert by_dst["city"].is_aggregation is False


@needs_sqlglot
def test_sqlglot_union_branches():
    sql = (
        "INSERT OVERWRITE TABLE zz.dwd_all_df "
        "SELECT uid FROM zz.ods_app "
        "UNION ALL "
        "SELECT uid FROM zz.ods_web"
    )
    edges = extract_column_edges(sql, "zz.dwd_all_df", [])
    assert edges is not None
    got = {(e.src_table, e.src_column) for e in edges}
    assert got == {("zz.ods_app", "uid"), ("zz.ods_web", "uid")}


@needs_sqlglot
def test_sqlglot_parse_failure_falls_back():
    assert extract_column_edges("!!! not sql at all (((", "t", []) is None


def test_load_column_edges_regex_fallback(monkeypatch, sql_dir):
    """Without sqlglot the regex tracer must still produce column edges."""
    monkeypatch.setattr(_sgl, "sqlglot", None)
    graph, warnings = from_sql_dir(sql_dir)
    assert warnings == []
    edges = graph.column_up.get(("zz.dws_city_gmv_df", "gmv"), [])
    assert any(e.src_column == "amount" for e in edges)


@needs_sqlglot
def test_from_sql_dir_uses_sqlglot_edges(fixture_graph):
    edges = fixture_graph.column_up.get(("zz.dws_city_gmv_df", "gmv"), [])
    assert len(edges) == 1
    assert edges[0].src_table == "zz.dwd_orders_df"
    assert edges[0].is_aggregation is True


# ---------------------------------------------------------------------------
# MCP server tool functions (extras: mcp; callables work without the package)
# ---------------------------------------------------------------------------

import importlib.util as _importlib_util

from seatunnel_agent.data_lineage.mcp_server import (
    build_tool_functions,
    create_mcp_server,
)

_HAS_MCP = _importlib_util.find_spec("mcp") is not None


def test_mcp_tool_names():
    tools = build_tool_functions(graph=linear_graph("a", "b"))
    assert set(tools) == {
        "lineage_query", "lineage_path", "lineage_sla_impact",
        "lineage_health_check", "lineage_search", "lineage_reload",
    }


def test_mcp_query_report_and_missing(fixture_graph):
    tools = build_tool_functions(graph=fixture_graph)
    out = tools["lineage_query"]("zz.dwd_orders_df")
    assert "血缘分析报告" in out
    assert "不在血缘图中" in tools["lineage_query"]("zz.no_such_table")
    assert "direction 必须是" in tools["lineage_query"]("zz.dwd_orders_df", direction="sideways")


def test_mcp_path_and_search(fixture_graph):
    tools = build_tool_functions(graph=fixture_graph)
    path_md = tools["lineage_path"]("zz.ods_orders", "zz.dws_city_gmv_df")
    assert "zz.ods_orders" in path_md and "zz.dws_city_gmv_df" in path_md
    assert "不在血缘图中" in tools["lineage_path"]("zz.nope", "zz.dws_city_gmv_df")
    found = json.loads(tools["lineage_search"]("orders"))
    assert found["匹配数"] >= 1


def test_mcp_sla_and_health(fixture_graph):
    tools = build_tool_functions(graph=fixture_graph)
    assert "不在血缘图中" in tools["lineage_sla_impact"]("zz.nope")
    assert tools["lineage_sla_impact"]("zz.ods_orders", delay_hours=2.0)
    assert tools["lineage_health_check"]()


def test_mcp_lazy_build_and_reload(sql_dir):
    tools = build_tool_functions(sql_dir=str(sql_dir))
    out = tools["lineage_query"]("zz.dwd_orders_df")
    assert "血缘分析报告" in out
    stats = json.loads(tools["lineage_reload"]())
    assert stats["stats"]["tables"] >= 4


@pytest.mark.skipif(_HAS_MCP, reason="mcp 已安装，错误分支不可达")
def test_mcp_create_server_friendly_error():
    with pytest.raises(RuntimeError, match="mcp"):
        create_mcp_server(sql_dir=".")


@pytest.mark.skipif(not _HAS_MCP, reason="mcp 未安装（pip install .[mcp]）")
def test_mcp_create_server(sql_dir):
    server = create_mcp_server(sql_dir=str(sql_dir))
    assert server is not None


def test_cli_lineage_mcp_requires_source():
    r = _run_cli(["lineage-mcp"])
    assert r.exit_code != 0
    assert "至少指定一个血缘来源" in r.output


# ---------------------------------------------------------------------------
# Edge provenance & confidence
# ---------------------------------------------------------------------------

def test_edge_meta_sources_and_confidence():
    g = LineageGraph()
    g.add_edge("a", "b", source="seatunnel", confidence="medium")
    meta = g.edge_meta[("a", "b")]
    assert meta.sources == {"seatunnel"} and meta.confidence == "medium"
    # 同一条边再次由高置信度来源确认 -> 置信度取最高，来源合并
    g.add_edge("a", "b", source="sql", confidence="high")
    assert meta.sources == {"seatunnel", "sql"} and meta.confidence == "high"
    # 低置信度不能拉低已有的高置信度
    g.add_edge("a", "b", source="regex", confidence="low")
    assert meta.confidence == "high"


def test_stats_include_edge_sources_and_confidence():
    g = LineageGraph()
    g.add_edge("a", "b", source="sql", confidence="high")
    g.add_edge("b", "c", source="seatunnel", confidence="medium")
    stats = g.stats()
    assert stats["edge_sources"] == {"sql": 1, "seatunnel": 1}
    assert stats["edge_confidence"] == {"high": 1, "medium": 1}


def test_merge_preserves_edge_meta():
    g1 = LineageGraph()
    g2 = LineageGraph()
    g2.add_edge("a", "b", source="hive_meta", confidence="high")
    g1.merge(g2)
    meta = g1.edge_meta[("a", "b")]
    assert meta.sources == {"hive_meta"} and meta.confidence == "high"


def test_trace_carries_edge_meta_and_mermaid_dashes_low_confidence():
    from seatunnel_agent.data_lineage.render import render_mermaid

    g = LineageGraph()
    g.add_edge("a", "b", source="seatunnel", confidence="medium")
    g.add_edge("b", "c", source="sql", confidence="high")
    chain = g.full_chain("b")
    assert chain.edge_meta[("a", "b")].confidence == "medium"
    mermaid = render_mermaid(chain)
    assert "-.->" in mermaid and "低置信度" in mermaid


def test_cache_roundtrip_preserves_edge_meta(tmp_path, monkeypatch):
    from seatunnel_agent.data_lineage.cache import graph_from_dict, graph_to_dict

    g = LineageGraph()
    g.add_edge("a", "b", source="seatunnel", confidence="medium")
    g.add_column_edge(ColumnEdge("a", "x", "b", "y", source="sql", confidence="low"))
    restored = graph_from_dict(graph_to_dict(g))
    meta = restored.edge_meta[("a", "b")]
    assert meta.sources == {"seatunnel"} and meta.confidence == "medium"
    col = restored.column_down[("a", "x")][0]
    assert col.source == "sql" and col.confidence == "low"


def test_seatunnel_loader_marks_medium_confidence(tmp_path):
    from seatunnel_agent.data_lineage.seatunnel_loader import from_seatunnel_files

    conf = tmp_path / "job.conf"
    conf.write_text(
        'source { Jdbc { table_name = "db.src" } }\n'
        'sink { Jdbc { table_name = "db.dst" } }\n',
        encoding="utf-8",
    )
    graph, warnings = from_seatunnel_files([conf])
    assert not warnings
    meta = graph.edge_meta[("db.src", "db.dst")]
    assert meta.sources == {"seatunnel"} and meta.confidence == "medium"


def test_add_column_edge_higher_confidence_replaces():
    g = LineageGraph()
    g.add_column_edge(ColumnEdge("a", "x", "b", "y", confidence="low"))
    g.add_column_edge(ColumnEdge("a", "x", "b", "y", expression="e2", confidence="high"))
    edges = g.column_down[("a", "x")]
    assert len(edges) == 1
    assert edges[0].confidence == "high" and edges[0].expression == "e2"
    ups = g.column_up[("b", "y")]
    assert len(ups) == 1 and ups[0] is edges[0]
    # 同等或更低置信度不替换，保留先到的高置信度边
    g.add_column_edge(ColumnEdge("a", "x", "b", "y", expression="e3", confidence="high"))
    g.add_column_edge(ColumnEdge("a", "x", "b", "y", confidence="medium"))
    assert g.column_down[("a", "x")][0].expression == "e2"
    assert g.stats()["column_edges"] == 1


def test_agent_chat_resets_per_question_state(fixture_graph):
    from seatunnel_agent.data_lineage import agent as agent_mod

    ag = agent_mod.LineageAgent.__new__(agent_mod.LineageAgent)
    ag.runtime = _runtime(fixture_graph)
    ag.messages = [{"role": "user", "content": "第一问"}]
    ag.console = agent_mod.Console()
    ag._on_event = None
    ag._agent_loop = lambda: "ok"
    ag.runtime.last_chain = object()
    ag.runtime.last_impact = object()
    ag.runtime.last_report = "旧报告"
    ag.runtime.last_mermaid = "旧图"
    ag.runtime.report = object()

    assert ag.chat("追问") == "ok"
    # per-question 状态清空，避免上一轮的列级影响混进新报告
    assert ag.runtime.last_chain is None
    assert ag.runtime.last_impact is None
    assert ag.runtime.last_report == ""
    assert ag.runtime.last_mermaid == ""
    assert ag.runtime.report is None
    # 图与对话历史保留
    assert ag.runtime.graph is fixture_graph
    assert len(ag.messages) == 2
