# -*- coding: utf-8 -*-
"""Common-upstream tracing for the Data Comparison agent.

When two tables disagree, their shared upstream tables are the first place to
look for the root cause. This module answers "哪些上游表同时喂给这两张表" via
the data-lineage graph. The comparison module itself has no LLM tool loop, so
the capability is exposed as a plain function plus an Anthropic-style tool
definition (``TOOL_DEFINITION`` / ``execute_lineage_link_tool``) ready to be
registered wherever a tool loop exists (UI action or a future agent).

The graph comes from the process-wide lazy cache shared with SQL Review
(``sql_review.lineage_context``: env vars ``LINEAGE_SQL_DIR`` /
``LINEAGE_SEATUNNEL_DIR``); unavailability degrades to a Chinese hint.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ..sql_review.lineage_context import get_lineage_graph

if TYPE_CHECKING:
    from ..data_lineage.graph import LineageGraph

_MAX_LISTED = 50

TOOL_DEFINITION: dict[str, Any] = {
    "name": "trace_common_upstream",
    "description": (
        "Find the common upstream tables of two tables via the data-lineage "
        "graph. When a comparison shows the two tables disagree, their shared "
        "upstream tables are the first candidates for the root cause of the "
        "inconsistency. Degrades to a hint when lineage is not configured."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "table_a": {"type": "string", "description": "第一张表，如 zz.dws_city_gmv_df"},
            "table_b": {"type": "string", "description": "第二张表"},
            "depth": {"type": "integer", "description": "上游追溯层数，默认 5"},
        },
        "required": ["table_a", "table_b"],
    },
}


def trace_common_upstream(
    table_a: str,
    table_b: str,
    depth: int = 5,
    graph: "LineageGraph | None" = None,
) -> dict[str, Any]:
    """Common upstream of two tables, or an ``error`` dict when unavailable."""
    table_a = (table_a or "").strip()
    table_b = (table_b or "").strip()
    if not table_a or not table_b:
        return {"error": "需要提供两张表名（table_a / table_b）"}

    if graph is None:
        graph, hint = get_lineage_graph()
        if graph is None:
            return {"error": hint}

    try:
        depth = max(1, min(int(depth), 10))
    except (TypeError, ValueError):
        depth = 5

    up_a = graph.upstream_of(table_a, depth=depth)
    if up_a.missing_root:
        return {"error": f"血缘图中不存在表 {table_a}"}
    up_b = graph.upstream_of(table_b, depth=depth)
    if up_b.missing_root:
        return {"error": f"血缘图中不存在表 {table_b}"}

    common = sorted((set(up_a.nodes) & set(up_b.nodes)) - {up_a.root, up_b.root})
    entries = []
    for name in common[:_MAX_LISTED]:
        node = up_a.nodes[name]
        entries.append({
            "table": name,
            "layer": node.layer,
            "is_sla": node.is_sla,
            "depth_from_a": abs(up_a.depth_of.get(name, 0)),
            "depth_from_b": abs(up_b.depth_of.get(name, 0)),
        })

    result: dict[str, Any] = {
        "success": True,
        "table_a": up_a.root,
        "table_b": up_b.root,
        "depth": depth,
        "common_upstream_count": len(common),
        "common_upstream": entries,
        "truncated": up_a.truncated or up_b.truncated,
    }
    if not common:
        result["message"] = (
            f"在 {depth} 层内两表没有公共上游；数据不一致的原因更可能在各自链路或写入逻辑"
        )
    elif len(common) > _MAX_LISTED:
        result["note"] = f"公共上游过多，仅列出前 {_MAX_LISTED} 个"
    return result


def execute_lineage_link_tool(name: str, tool_input: dict[str, Any]) -> str:
    if name != TOOL_DEFINITION["name"]:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
    try:
        result = trace_common_upstream(
            str(tool_input.get("table_a") or ""),
            str(tool_input.get("table_b") or ""),
            depth=tool_input.get("depth") or 5,
        )
    except Exception as exc:  # noqa: BLE001 — tool errors go back as JSON
        result = {"error": f"trace_common_upstream failed: {exc}"}
    return json.dumps(result, ensure_ascii=False, default=str)
