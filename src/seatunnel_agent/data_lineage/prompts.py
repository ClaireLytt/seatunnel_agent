"""System prompt for the data lineage agent."""

from __future__ import annotations

from pathlib import Path

from .config import LineageConfig
from .graph import LineageGraph

_RESOURCE_DIR = Path(__file__).parent / "resources"


def _load_resource(name: str) -> str:
    path = _RESOURCE_DIR / name
    return path.read_text(encoding="utf-8") if path.is_file() else ""


_BASE_PROMPT = """\
You are a data-warehouse lineage analyst (数据表全链路血缘分析专家). You answer
questions like "这个表的上下游是什么" and "改这个字段影响哪些下游表" using the
lineage tools, and produce a structured Chinese report.

## How You Work (ReAct Pattern)

1. THINK: Identify the target table/column and the direction the user cares
   about (上游/下游/双向, 表级/字段级).
2. ACT: Query with the lineage tools. If the graph is empty or missing the
   table, load data first ({load_hint}), then query. Use search_tables when
   the exact table name is uncertain.
3. SUBMIT: Call **submit_lineage_report** exactly once with the root table,
   direction and a Chinese summary. The tool renders the final report from
   your last query results.
4. FINISH: Output the rendered report returned by submit_lineage_report
   VERBATIM as your final answer. Do not add anything before or after it.

## Session State

- Graph already loaded: {graph_stats}
- Hive metadata source: {hive_state}
- SQL directory source: {sql_state}
- SeaTunnel config source: {seatunnel_state}
- Default depth {default_depth}, max depth {max_depth}, max nodes {max_nodes}.
{graph_context}
## Guide

{guide}
"""


_MAX_CONTEXT_CHARS = 2000
_TOP_TABLES = 20


def build_graph_context(graph: LineageGraph | None) -> str:
    """Graph overview injected into the system prompt: stats + hot tables.

    Saves the LLM a round of health_check/search_tables calls. Empty graph →
    empty string so the base prompt is unchanged.
    """
    if graph is None or not graph.nodes:
        return ""
    stats = graph.stats()
    lines = [
        "## Graph Overview (已加载图概况，可直接引用下列表名，无需先 search)",
        "",
        (
            f"- 表数 {stats['tables']} · 边数 {stats['edges']} · "
            f"字段级边 {stats['column_edges']} · SLA 表 {stats['sla_tables']}"
        ),
    ]
    for key, label in (("layers", "分层分布"), ("edge_sources", "边来源"),
                       ("edge_confidence", "边置信度")):
        counts = stats.get(key) or {}
        if counts:
            lines.append(
                f"- {label}: " + " / ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
            )
    lines.append(f"- 热点表 Top {_TOP_TABLES}（按上下游度数排序）:")

    def degree(name: str) -> int:
        return len(graph.upstream.get(name, ())) + len(graph.downstream.get(name, ()))

    ranked = sorted(graph.nodes.values(), key=lambda n: (-degree(n.name), n.name))
    used = sum(len(line) + 1 for line in lines)
    for node in ranked[:_TOP_TABLES]:
        up = len(graph.upstream.get(node.name, ()))
        down = len(graph.downstream.get(node.name, ()))
        sla = ", SLA" if node.is_sla else ""
        entry = f"  - {node.name}({node.layer or 'unknown'}, 上游{up}/下游{down}{sla})"
        if used + len(entry) > _MAX_CONTEXT_CHARS:
            lines.append("  - …（热点表列表已截断）")
            break
        lines.append(entry)
        used += len(entry) + 1
    return "\n".join(lines)


def build_lineage_prompt(
    graph: LineageGraph | None = None,
    config: LineageConfig | None = None,
    hive_available: bool = False,
    sql_dir: str | None = None,
    seatunnel_dir: str | None = None,
) -> str:
    config = config or LineageConfig()
    stats = graph.stats() if graph is not None else {}
    if stats.get("tables"):
        graph_stats = (
            f"{stats.get('tables', 0)} tables, {stats.get('edges', 0)} edges, "
            f"{stats.get('column_edges', 0)} column edges"
        )
    else:
        graph_stats = "EMPTY — load data before querying"

    hive_state = (
        f"available (meta table {config.meta_table}, latest pt partition by default)"
        if hive_available
        else "NOT configured — do not call load_lineage_from_hive"
    )
    sql_state = (
        f"available ({sql_dir})" if sql_dir
        else "not provided — do not call load_lineage_from_sql"
    )
    seatunnel_state = (
        f"available ({seatunnel_dir})" if seatunnel_dir
        else "not provided — do not call load_lineage_from_seatunnel"
    )

    load_hints = []
    if hive_available:
        load_hints.append("load_lineage_from_hive")
    if sql_dir:
        load_hints.append("load_lineage_from_sql")
    if seatunnel_dir:
        load_hints.append("load_lineage_from_seatunnel")
    load_hint = " / ".join(load_hints) or "no loader available; tell the user"

    context = build_graph_context(graph)
    return _BASE_PROMPT.format(
        load_hint=load_hint,
        graph_stats=graph_stats,
        graph_context=f"\n{context}\n" if context else "",
        hive_state=hive_state,
        sql_state=sql_state,
        seatunnel_state=seatunnel_state,
        default_depth=config.default_depth,
        max_depth=config.max_depth,
        max_nodes=config.max_nodes,
        guide=_load_resource("lineage_guide.md"),
    )
