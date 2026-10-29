"""Chat/MCP tool entry point for the warehouse-hygiene agent.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations


def _lang(lang: str) -> str:
    return "en" if (lang or "zh").strip().lower().startswith("en") else "zh"


def warehouse_hygiene(sql: str, dialect: str = "hive", lang: str = "") -> str:
    """数仓卫生检查（确定性）：对 SQL/DDL 脚本做血缘驱动的死重报告——
    只写不读的孤儿表、表有人读但列无人取的死列、有 DDL 却不在任何血缘
    里的悬空定义。回答「哪些可以退役」。"""
    from seatunnel_agent.agents.data.lineage_hygiene import (
        analyze_sql_text,
        render_markdown,
    )

    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    try:
        report = analyze_sql_text(sql, dialect=dialect)
    except Exception as exc:
        return f"分析失败 / analysis failed: {exc}"
    return render_markdown(report, lang=_lang(lang))
