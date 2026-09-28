# -*- coding: utf-8 -*-
"""MCP server exposing the data-skew static analyzer over stdio.

Start with ``seatunnel-agent skew-mcp`` and register it in an MCP client
(Claude Desktop / Claude Code / Cline).  Mirrors the lineage MCP server's
shape: the tool callables are plain functions built by
:func:`build_tool_functions`, usable and testable without the ``mcp``
package; :func:`create_mcp_server` only wires them into FastMCP.

The static scan is deterministic, executes nothing and needs no LLM or
database, which makes it a safe tool to hand to an external agent.
"""

from __future__ import annotations

from typing import Callable

from .detector import DIALECTS, _DIALECT_ALIASES
from .history import default_history

_INSTRUCTIONS = (
    "SQL 数据倾斜静态分析：识别 COUNT(DISTINCT) 单点、NULL 关联键、全局排序/去重、"
    "JOIN 键函数、动态分区未打散等倾斜写法，输出严重度分级的中文/英文 Markdown 报告"
    "与引擎参数建议。支持 Spark SQL / MaxCompute SQL / Hive SQL。纯静态规则，"
    "不执行 SQL、不调用 LLM。"
)


def build_tool_functions(
    default_dialect: str = "spark",
    default_lang: str = "zh",
) -> dict[str, Callable[..., str]]:
    """Skew tool callables keyed by name."""
    history = default_history()

    def skew_check(sql: str, dialect: str = "", lang: str = "") -> str:
        """静态分析 SQL 的数据倾斜风险，返回 Markdown 报告（严重度分级 + 优化建议
        + 引擎参数）。dialect: spark / maxcompute / hive；lang: zh / en。"""
        from .agent import static_skew_report
        from .report import render_report

        sql = (sql or "").strip()
        if not sql:
            return "SQL 不能为空 / SQL must not be empty"
        # normalize_dialect() silently falls back to "spark", which would
        # hide a caller's typo — resolve aliases by hand and reject unknowns.
        raw = (dialect or default_dialect).strip().lower().replace(" ", "")
        d = _DIALECT_ALIASES.get(raw, raw)
        if d not in DIALECTS:
            return f"dialect 必须是 {', '.join(DIALECTS)} 之一"
        lg = (lang or default_lang).strip().lower()
        report = static_skew_report(sql, d, lg)
        history.log(sql, report, mode="static", source="mcp")
        return render_report(report, lg)

    def skew_check_file(path: str, dialect: str = "", lang: str = "") -> str:
        """静态分析一个 SQL 文件的数据倾斜风险（参数同 skew_check，path 为文件路径）。"""
        from pathlib import Path

        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"读取文件失败 / cannot read file: {exc}"
        return skew_check(text, dialect=dialect, lang=lang)

    return {"skew_check": skew_check, "skew_check_file": skew_check_file}


def create_mcp_server(default_dialect: str = "spark", default_lang: str = "zh"):
    """FastMCP server (stdio) wrapping the skew tools."""
    from ..mcp_compat import fastmcp_class

    server = fastmcp_class()("seatunnel-dataskew", instructions=_INSTRUCTIONS)
    functions = build_tool_functions(
        default_dialect=default_dialect, default_lang=default_lang)
    for fn in functions.values():
        server.tool()(fn)
    return server
