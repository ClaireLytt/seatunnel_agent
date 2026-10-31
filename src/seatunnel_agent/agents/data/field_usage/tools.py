"""Chat/MCP tool entry point for the field-usage analyzer.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def field_usage(ddl: str, queries: str, lang: str = "") -> str:
    """字段使用率盘点（确定性）：粘贴表的 CREATE TABLE DDL + 一批查询 SQL
    （当日调度脚本/日志导出）,逐列统计 SELECT/WHERE/JOIN/GROUP BY 引用数
    （按语句解析别名归属,无歧义才计）——从未被读的表（下线候选）、从未被
    引用的列（裁剪候选）、SELECT * 盲区、最热列 TOP。不连数据库。"""
    from seatunnel_agent.agents.data.field_usage import (
        analyze_usage,
        render_markdown,
    )

    if not (ddl or "").strip() or not (queries or "").strip():
        return "DDL 与查询都不能为空 / both DDL and queries are required"
    try:
        report = analyze_usage(ddl, queries)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(report, lang=normalize_lang(lang))
