# -*- coding: utf-8 -*-
"""MCP server exposing lineage tools over stdio (install extras: ``mcp``).

Start with ``seatunnel-agent lineage-mcp --sql-dir ...`` and register it in an
MCP client (Claude Desktop / Claude Code / Cline). The tool callables are
plain functions built by :func:`build_tool_functions`, so they are usable and
testable without the ``mcp`` package; ``create_mcp_server`` only wires them
into a FastMCP instance.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from .agent import static_lineage
from .config import DIRECTIONS, MAX_DEPTH, load_lineage_config
from .loaders import build_graph
from .render import render_health, render_path, render_report, render_sla_impact

_INSTRUCTIONS = (
    "数据表全链路血缘分析：上下游链路、字段级影响、最短路径、SLA 延迟影响、"
    "治理体检、变更影响分析（对比两份 SQL 的上线影响面）。"
    "表名用 库名.表名（如 zz.dwd_orders_df）。"
)


def build_tool_functions(
    sql_dir: str | None = None,
    seatunnel_dir: str | None = None,
    use_hive: bool = False,
    meta_table: str | None = None,
    partition: str | None = None,
    graph: Any = None,
    sql_dialect: str = "hive",
) -> dict[str, Callable[..., str]]:
    """Lineage tool callables keyed by name; the graph is built lazily once."""
    state: dict[str, Any] = {"graph": graph, "warnings": []}

    def _graph():
        if state["graph"] is None:
            built, warnings = build_graph(
                sql_dir=sql_dir, seatunnel_dir=seatunnel_dir, use_hive=use_hive,
                meta_table=meta_table, partition=partition,
                sql_dialect=sql_dialect,
            )
            state["graph"], state["warnings"] = built, warnings
        return state["graph"]

    def _missing(g, table: str) -> str:
        names = g.suggest(table)
        hint = f"，相近的表：{', '.join(names)}" if names else ""
        return f"表 '{table}' 不在血缘图中{hint}"

    def lineage_query(
        table: str, direction: str = "both", depth: int = 3,
        column: str | None = None,
    ) -> str:
        """查询表的上下游血缘链路，返回中文 Markdown 报告（含 mermaid 图）。
        direction: upstream / downstream / both；column 可选，做字段级影响分析。"""
        if direction not in DIRECTIONS:
            return f"direction 必须是 {', '.join(DIRECTIONS)} 之一"
        g = _graph()
        report = static_lineage(
            g, table, direction, depth, column=column, config=load_lineage_config()
        )
        if report.chain and report.chain.missing_root:
            return _missing(g, table)
        return render_report(report)

    def lineage_path(src: str, dst: str) -> str:
        """查询两张表之间的最短血缘路径（src → dst），返回中文 Markdown。"""
        g = _graph()
        for name in (src, dst):
            if g.get(name) is None:
                return _missing(g, name)
        return render_path(g.path_between(src, dst), src, dst, g)

    def lineage_sla_impact(
        table: str, delay_hours: float = 0.0, depth: int = MAX_DEPTH
    ) -> str:
        """SLA 延迟影响分析：假设某表延迟 N 小时，列出受影响的下游 SLA/基线任务。"""
        g = _graph()
        impact = g.sla_impact(table, delay_hours, depth)
        if impact.missing_root:
            return _missing(g, table)
        return render_sla_impact(impact)

    def lineage_health_check() -> str:
        """血缘治理体检：环依赖 / 孤立表 / 无下游可下线表，返回中文 Markdown。"""
        return render_health(_graph().health_check())

    def lineage_search(keyword: str) -> str:
        """按关键词搜索血缘图中的表，返回 JSON（中文属性标签）。"""
        nodes = _graph().search(keyword)
        return json.dumps(
            {"匹配数": len(nodes), "表": [n.to_dict() for n in nodes]},
            ensure_ascii=False, indent=2,
        )

    def lineage_change_impact(
        old_dir: str = "", base: str = "", depth: int = 3,
    ) -> str:
        """变更影响分析：对比基线与当前 sql_dir 的血缘，输出上线影响面
        （变更了哪些表、下游波及、error/warn/info 严重度），中文 Markdown。
        基线二选一：old_dir（旧 SQL 目录）或 base（git 基线，如 HEAD~1、
        origin/main）。纯静态分析，不连接数据库、不执行 SQL。"""
        import shutil

        from .impact import (
            analyze_dirs, materialize_git_ref, render_impact_markdown,
        )

        if bool(old_dir) == bool(base):
            return "请二选一提供 old_dir（旧 SQL 目录）或 base（git 基线，如 HEAD~1）"
        if not sql_dir:
            return "MCP server 未配置 --sql-dir，无法确定当前（新）SQL 目录"
        tmp = None
        try:
            if base:
                try:
                    tmp = materialize_git_ref(base, sql_dir)
                except RuntimeError as exc:
                    return f"git 基线模式失败: {exc}（非 git 仓库请改用 old_dir）"
                baseline = tmp
            else:
                baseline = old_dir
            try:
                result = analyze_dirs(baseline, sql_dir, depth=depth,
                                      sql_dialect=sql_dialect)
            except ValueError as exc:
                return str(exc)
            from .impact import ImpactLogger
            ImpactLogger().log_impact(
                result, mode="git" if base else "dirs", source="mcp",
                baseline=base or old_dir)
            report = render_impact_markdown(result)
            if tmp is not None and (tmp / ".impact_empty_baseline").exists():
                report = (f"> ⚠️ 基线 {base} 下没有 *.sql —— "
                          f"所有文件都报告为新增\n\n{report}")
            return report
        finally:
            if tmp is not None:
                shutil.rmtree(tmp, ignore_errors=True)

    def lineage_reload() -> str:
        """重新加载血缘图（重读 SQL/SeaTunnel 目录、重查 Hive），返回图统计。"""
        state["graph"] = None
        g = _graph()
        return json.dumps(
            {"stats": g.stats(), "warnings": state["warnings"]},
            ensure_ascii=False, indent=2,
        )

    tools = (
        lineage_query, lineage_path, lineage_sla_impact,
        lineage_health_check, lineage_search, lineage_change_impact,
        lineage_reload,
    )
    return {fn.__name__: fn for fn in tools}


def create_mcp_server(
    sql_dir: str | None = None,
    seatunnel_dir: str | None = None,
    use_hive: bool = False,
    meta_table: str | None = None,
    partition: str | None = None,
    sql_dialect: str = "hive",
):
    """FastMCP server (stdio) wrapping the lineage tools."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "未安装 mcp 依赖，请先执行: pip install 'seatunnel-agent[mcp]'"
        ) from exc

    server = FastMCP("seatunnel-lineage", instructions=_INSTRUCTIONS)
    functions = build_tool_functions(
        sql_dir=sql_dir, seatunnel_dir=seatunnel_dir, use_hive=use_hive,
        meta_table=meta_table, partition=partition, sql_dialect=sql_dialect,
    )
    for fn in functions.values():
        server.tool()(fn)
    return server
