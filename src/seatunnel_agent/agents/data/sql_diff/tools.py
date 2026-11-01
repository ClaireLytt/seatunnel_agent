"""Chat/MCP tool entry point for the SQL semantic differ.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def sql_diff(old_sql: str, new_sql: str, dialect: str = "hive",
             lang: str = "") -> str:
    """SQL 语义对比（确定性）：粘贴两版取数/加工 SQL，按写入目标配对后
    报告真正的语义差异并分级——删输出列/INSERT 模式翻转（破坏）、列
    表达式/过滤/聚合口径变更、源表进出（风险）、新增语句或列（提示）。
    纯格式化、别名与顺序变化不计入。不连数据库。"""
    from seatunnel_agent.agents.data.sql_diff import (
        diff_sql,
        render_markdown,
    )

    if not (old_sql or "").strip() or not (new_sql or "").strip():
        return "两版 SQL 都不能为空 / both SQL versions are required"
    try:
        report = diff_sql(old_sql, new_sql, dialect=dialect)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(report, lang=normalize_lang(lang))
