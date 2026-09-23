"""Tool definitions and execution for the lineage agent.

The runtime carries the lineage graph (session state) plus the last chain /
column-impact results so ``submit_lineage_report`` can assemble the final
report deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..utils import safe_json
from .config import COLUMN_IMPACT_DEPTH, LineageConfig
from .graph import ChainResult, ColumnImpactResult, LineageGraph
from .render import (
    render_health,
    render_path,
    render_report,
    render_sla_impact,
    render_tree,
    select_mermaid,
)
from .report import LineageReport, baseline_nodes_of, sla_nodes_of

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "load_lineage_from_hive",
        "description": (
            "Load the full-chain lineage from the Hive metadata table "
            "(zz.dwm_meta_table_lineage_df by default, latest pt partition) "
            "and merge it into the session graph. relation_* columns record "
            "DOWNSTREAM lineage; the upstream index is built automatically. "
            "Only available when Hive is configured."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "partition": {
                    "type": "string",
                    "description": "Override the pt partition (default: latest)",
                },
            },
        },
    },
    {
        "name": "load_lineage_from_sql",
        "description": (
            "Parse every *.sql file under the session's SQL directory and "
            "merge table- and column-level lineage into the session graph. "
            "Only available when the session was given a SQL directory."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "load_lineage_from_seatunnel",
        "description": (
            "Parse every SeaTunnel job config (*.conf/*.config/*.json) under "
            "the session's SeaTunnel directory and merge source→sink table "
            "lineage into the session graph. Only available when the session "
            "was given a SeaTunnel config directory."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_upstream",
        "description": "Get upstream tables (data sources) of a table, up to `depth` hops.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "Full name, e.g. zz.dwm_orders_df"},
                "depth": {"type": "integer", "description": "Hops to traverse (default 3)"},
            },
            "required": ["table"],
        },
    },
    {
        "name": "get_downstream",
        "description": (
            "Get downstream tables (consumers) of a table, up to `depth` hops. "
            "Includes SLA/baseline flags for impact assessment."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string"},
                "depth": {"type": "integer", "description": "Hops to traverse (default 3)"},
            },
            "required": ["table"],
        },
    },
    {
        "name": "get_full_chain",
        "description": "Get the full chain (both upstream and downstream) around a table.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string"},
                "up_depth": {"type": "integer", "description": "Upstream hops (default 3)"},
                "down_depth": {"type": "integer", "description": "Downstream hops (default 3)"},
            },
            "required": ["table"],
        },
    },
    {
        "name": "impact_analysis",
        "description": (
            "Column-level impact analysis: which downstream tables/columns are "
            "affected if this column changes. Falls back to table-level "
            "downstream (flagged `degraded`) when no column lineage exists."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string"},
                "column": {"type": "string"},
                "depth": {"type": "integer", "description": "Hops to traverse (default 5)"},
            },
            "required": ["table", "column"],
        },
    },
    {
        "name": "find_path",
        "description": (
            "Find the shortest lineage path between two tables (tries "
            "src→dst first, then dst→src). Answers 'how is A connected to B'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "Start table"},
                "dst": {"type": "string", "description": "End table"},
            },
            "required": ["src", "dst"],
        },
    },
    {
        "name": "sla_impact",
        "description": (
            "SLA delay impact: list every downstream SLA/baseline task "
            "reachable from a table, ordered by hop distance and SLA time. "
            "Optionally pass the assumed delay in hours for the report."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string"},
                "delay_hours": {"type": "number", "description": "假设延迟小时数（可选）"},
                "depth": {"type": "integer", "description": "Hops to traverse (default 10)"},
            },
            "required": ["table"],
        },
    },
    {
        "name": "health_check",
        "description": (
            "Governance health check over the whole loaded graph: circular "
            "dependencies, isolated tables (no lineage at all) and tables "
            "without any consumer (decommission candidates)."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_tables",
        "description": "Fuzzy-search tables in the loaded graph by keyword.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "get_table_detail",
        "description": (
            "Get one table's attributes (类型/库名/表名/表分层/是否在SLA/"
            "SLA产出时间/所在基线) plus direct upstream/downstream neighbours."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string"},
            },
            "required": ["table"],
        },
    },
    {
        "name": "save_lineage_snapshot",
        "description": (
            "Save the current session lineage graph as a named snapshot "
            "(logs/.lineage_snapshots/) for later change detection."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "快照名（可选）"},
            },
        },
    },
    {
        "name": "diff_lineage_snapshot",
        "description": (
            "Compare lineage graphs for change detection: pass `snapshot` to "
            "diff it against the CURRENT session graph, or pass `old` and "
            "`new` snapshot names to diff two snapshots. Reports added/removed "
            "tables and edges plus confidence changes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "snapshot": {
                    "type": "string",
                    "description": "快照名或文件名，与当前图对比",
                },
                "old": {"type": "string", "description": "旧快照名（与 new 搭配）"},
                "new": {"type": "string", "description": "新快照名（与 old 搭配）"},
            },
        },
    },
    {
        "name": "submit_lineage_report",
        "description": (
            "Submit the final lineage analysis. Uses the LAST chain/impact "
            "query results from this session plus your summary to build the "
            "rendered report, which you must output verbatim as your final "
            "answer. Call a query tool first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "root_table": {"type": "string", "description": "分析的目标表"},
                "direction": {
                    "type": "string",
                    "enum": ["upstream", "downstream", "both"],
                },
                "summary": {
                    "type": "string",
                    "description": "总体结论（中文），包含影响范围与 SLA/基线风险提示",
                },
            },
            "required": ["root_table", "summary"],
        },
    },
]


@dataclass
class LineageRuntime:
    graph: LineageGraph = field(default_factory=LineageGraph)
    config: LineageConfig = field(default_factory=LineageConfig)
    sql_dir: str | None = None
    sql_dialect: str = "hive"
    seatunnel_dir: str | None = None
    hive_available: bool = False
    meta_table: str | None = None
    partition: str | None = None
    warnings: list[str] = field(default_factory=list)
    last_chain: ChainResult | None = None
    last_impact: ColumnImpactResult | None = None
    # Which query ran most recently ("chain" / "impact") — the report's
    # mermaid follows the latest result instead of always preferring impact.
    last_kind: str = ""
    last_report: str = ""
    last_mermaid: str = ""
    report: LineageReport | None = None

    def reset_question_state(self) -> None:
        """Drop per-question results so an old chain/impact never leaks into
        the next report. The loaded graph is kept."""
        self.last_chain = None
        self.last_impact = None
        self.last_kind = ""
        self.last_report = ""
        self.last_mermaid = ""
        self.report = None


def _missing_table(graph: LineageGraph, name: str) -> dict[str, Any]:
    return {
        "error": f"表 '{name}' 不在血缘图中",
        "suggestions": graph.suggest(name),
    }


def _depth(inp: dict[str, Any], key: str, default: int, cap: int) -> int:
    try:
        value = int(inp.get(key, default))
    except (TypeError, ValueError):
        return default
    return max(1, min(value, cap))


def _chain_payload(rt: LineageRuntime, chain: ChainResult) -> dict[str, Any]:
    if chain.missing_root:
        return _missing_table(rt.graph, chain.root)
    rt.last_chain = chain
    rt.last_kind = "chain"
    return {
        "root": chain.root,
        "direction": chain.direction,
        "upstream_count": chain.upstream_count,
        "downstream_count": chain.downstream_count,
        "truncated": chain.truncated,
        "tree": render_tree(chain),
        "sla_tables": [n.to_dict() for n in sla_nodes_of(chain)],
        "baseline_tables": [n.to_dict() for n in baseline_nodes_of(chain)],
    }


def _tool_load_from_hive(inp: dict[str, Any], rt: LineageRuntime) -> dict[str, Any]:
    if not rt.hive_available:
        return {"error": "本会话未配置 Hive 连接（HIVE_HOST），无法加载元数据血缘"}
    # Reuse the TTL-cached loader (same one the CLI/API/UI use) — a full
    # metadata scan can take minutes and must not be repeated per call.
    from .loaders import _hive_graph_cached

    partition = str(inp.get("partition") or "").strip() or rt.partition
    sub, pt, from_cache = _hive_graph_cached(
        rt.meta_table, partition, use_cache=True
    )
    rt.graph.merge(sub)
    return {
        "success": True,
        "loaded": sub.stats(),
        "graph": rt.graph.stats(),
        "partition": pt,
        "from_cache": from_cache,
    }


def _tool_load_from_sql(inp: dict[str, Any], rt: LineageRuntime) -> dict[str, Any]:
    if not rt.sql_dir:
        return {"error": "本会话未指定 SQL 目录"}
    from .loaders import from_sql_dir

    sub, warnings = from_sql_dir(rt.sql_dir, dialect=rt.sql_dialect)
    rt.graph.merge(sub)
    rt.warnings.extend(warnings)
    return {
        "success": True,
        "loaded": sub.stats(),
        "graph": rt.graph.stats(),
        "warnings": warnings,
    }


def _tool_load_from_seatunnel(inp: dict[str, Any], rt: LineageRuntime) -> dict[str, Any]:
    if not rt.seatunnel_dir:
        return {"error": "本会话未指定 SeaTunnel 配置目录"}
    from .seatunnel_loader import from_seatunnel_dir

    sub, warnings = from_seatunnel_dir(rt.seatunnel_dir)
    rt.graph.merge(sub)
    rt.warnings.extend(warnings)
    return {
        "success": True,
        "loaded": sub.stats(),
        "graph": rt.graph.stats(),
        "warnings": warnings,
    }


def _tool_get_upstream(inp: dict[str, Any], rt: LineageRuntime) -> dict[str, Any]:
    depth = _depth(inp, "depth", rt.config.default_depth, rt.config.max_depth)
    chain = rt.graph.upstream_of(
        str(inp.get("table", "")), depth, rt.config.max_nodes
    )
    return _chain_payload(rt, chain)


def _tool_get_downstream(inp: dict[str, Any], rt: LineageRuntime) -> dict[str, Any]:
    depth = _depth(inp, "depth", rt.config.default_depth, rt.config.max_depth)
    chain = rt.graph.downstream_of(
        str(inp.get("table", "")), depth, rt.config.max_nodes
    )
    return _chain_payload(rt, chain)


def _tool_get_full_chain(inp: dict[str, Any], rt: LineageRuntime) -> dict[str, Any]:
    up = _depth(inp, "up_depth", rt.config.default_depth, rt.config.max_depth)
    down = _depth(inp, "down_depth", rt.config.default_depth, rt.config.max_depth)
    chain = rt.graph.full_chain(
        str(inp.get("table", "")), up, down, rt.config.max_nodes
    )
    return _chain_payload(rt, chain)


def _tool_impact_analysis(inp: dict[str, Any], rt: LineageRuntime) -> dict[str, Any]:
    depth = _depth(inp, "depth", COLUMN_IMPACT_DEPTH, rt.config.max_depth)
    impact = rt.graph.impact_of_column(
        str(inp.get("table", "")), str(inp.get("column", "")),
        depth, rt.config.max_nodes,
    )
    if impact.missing_root:
        return _missing_table(rt.graph, impact.root_table)
    rt.last_impact = impact
    rt.last_kind = "impact"
    payload = impact.to_dict()
    if impact.degraded and impact.table_fallback:
        rt.last_chain = impact.table_fallback
        payload["table_fallback_tree"] = render_tree(impact.table_fallback)
    return payload


def _tool_find_path(inp: dict[str, Any], rt: LineageRuntime) -> dict[str, Any]:
    src = str(inp.get("src", "")).strip()
    dst = str(inp.get("dst", "")).strip()
    for name in (src, dst):
        if rt.graph.get(name) is None:
            return _missing_table(rt.graph, name)
    path = rt.graph.path_between(src, dst)
    return {
        "found": path is not None,
        "path": path or [],
        "hops": len(path) - 1 if path else None,
        "markdown": render_path(path, src, dst, rt.graph),
    }


def _tool_sla_impact(inp: dict[str, Any], rt: LineageRuntime) -> dict[str, Any]:
    depth = _depth(inp, "depth", rt.config.max_depth, rt.config.max_depth)
    try:
        delay = float(inp.get("delay_hours") or 0)
    except (TypeError, ValueError):
        delay = 0.0
    impact = rt.graph.sla_impact(
        str(inp.get("table", "")), delay, depth, rt.config.max_nodes
    )
    if impact.missing_root:
        return _missing_table(rt.graph, impact.root)
    payload = impact.to_dict()
    payload["markdown"] = render_sla_impact(impact)
    return payload


def _tool_health_check(inp: dict[str, Any], rt: LineageRuntime) -> dict[str, Any]:
    if not rt.graph.nodes:
        return {"error": "血缘图为空，请先加载数据源"}
    report = rt.graph.health_check()
    payload = report.to_dict()
    payload["markdown"] = render_health(report)
    return payload


def _tool_search_tables(inp: dict[str, Any], rt: LineageRuntime) -> dict[str, Any]:
    matches = rt.graph.search(str(inp.get("keyword", "")))
    return {"count": len(matches), "tables": [n.to_dict() for n in matches]}


def _tool_get_table_detail(inp: dict[str, Any], rt: LineageRuntime) -> dict[str, Any]:
    name = str(inp.get("table", ""))
    node = rt.graph.get(name)
    if node is None:
        return _missing_table(rt.graph, name)
    def _neighbours(names: set[str], as_src: bool) -> list[dict[str, Any]]:
        out = []
        for n in sorted(names):
            key = (n, node.name) if as_src else (node.name, n)
            meta = rt.graph.edge_meta.get(key)
            entry: dict[str, Any] = {"table": n}
            if meta is not None:
                entry.update(meta.to_dict())
            out.append(entry)
        return out

    return {
        "detail": node.to_dict(),
        "direct_upstream": _neighbours(rt.graph.upstream.get(node.name, set()), as_src=True),
        "direct_downstream": _neighbours(rt.graph.downstream.get(node.name, set()), as_src=False),
    }


def _tool_save_snapshot(inp: dict[str, Any], rt: LineageRuntime) -> dict[str, Any]:
    if not rt.graph.nodes:
        return {"error": "血缘图为空，请先加载数据源"}
    from .snapshot import save_snapshot

    path = save_snapshot(rt.graph, name=str(inp.get("name") or ""))
    return {"success": True, "file": path.name, "graph": rt.graph.stats()}


def _tool_diff_snapshot(inp: dict[str, Any], rt: LineageRuntime) -> dict[str, Any]:
    from .snapshot import diff_graphs, load_snapshot, render_diff_markdown

    old_name = str(inp.get("old") or "").strip()
    new_name = str(inp.get("new") or "").strip()
    if old_name and new_name:
        old_graph = load_snapshot(old_name)
        if old_graph is None:
            return {"error": f"找不到快照 '{old_name}'"}
        new_graph = load_snapshot(new_name)
        if new_graph is None:
            return {"error": f"找不到快照 '{new_name}'"}
    else:
        snap = str(inp.get("snapshot") or "").strip()
        if not snap:
            return {"error": "请提供 snapshot（与当前图对比）或 old/new 两个快照名"}
        if not rt.graph.nodes:
            return {"error": "血缘图为空，请先加载数据源"}
        old_graph = load_snapshot(snap)
        if old_graph is None:
            return {"error": f"找不到快照 '{snap}'"}
        new_graph = rt.graph
    diff = diff_graphs(old_graph, new_graph)
    diff["markdown"] = render_diff_markdown(diff)
    return diff


def _tool_submit_report(inp: dict[str, Any], rt: LineageRuntime) -> dict[str, Any]:
    if rt.last_chain is None and rt.last_impact is None:
        return {"error": "还没有任何查询结果，请先调用血缘查询工具"}
    root = str(inp.get("root_table") or "").strip()
    if not root and rt.last_chain:
        root = rt.last_chain.root
    if not root and rt.last_impact:
        root = rt.last_impact.root_table

    # The mermaid follows the most recent query: a chain query after an
    # impact_analysis must not be shadowed by the older column graph.
    mermaid = select_mermaid(
        rt.last_chain, rt.last_impact, rt.config.max_mermaid_nodes,
        prefer_impact=rt.last_kind == "impact" or rt.last_chain is None,
    )

    report = LineageReport(
        root_table=root,
        direction=str(inp.get("direction") or (rt.last_chain.direction if rt.last_chain else "both")),
        chain=rt.last_chain,
        column_impact=rt.last_impact,
        summary=str(inp.get("summary") or "").strip(),
        mermaid=mermaid,
    )
    rt.report = report
    rt.last_mermaid = mermaid
    rt.last_report = render_report(report)
    return {"success": True, "report": rt.last_report}


_TOOL_HANDLERS = {
    "load_lineage_from_hive": _tool_load_from_hive,
    "load_lineage_from_sql": _tool_load_from_sql,
    "load_lineage_from_seatunnel": _tool_load_from_seatunnel,
    "get_upstream": _tool_get_upstream,
    "get_downstream": _tool_get_downstream,
    "get_full_chain": _tool_get_full_chain,
    "impact_analysis": _tool_impact_analysis,
    "find_path": _tool_find_path,
    "sla_impact": _tool_sla_impact,
    "health_check": _tool_health_check,
    "search_tables": _tool_search_tables,
    "get_table_detail": _tool_get_table_detail,
    "save_lineage_snapshot": _tool_save_snapshot,
    "diff_lineage_snapshot": _tool_diff_snapshot,
    "submit_lineage_report": _tool_submit_report,
}


def execute_lineage_tool(
    name: str, tool_input: dict[str, Any], runtime: LineageRuntime
) -> str:
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        return safe_json({"error": f"Unknown tool: {name}"})
    try:
        result = handler(tool_input, runtime)
    except Exception as exc:  # noqa: BLE001 — tool errors go back to the model
        result = {"error": f"Tool '{name}' failed: {exc}"}
    return safe_json(result)
