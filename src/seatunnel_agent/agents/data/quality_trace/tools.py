"""Chat/MCP tool entry point for the quality root-cause tracer.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def quality_trace(sql: str, table: str, column: str = "",
                  symptom: str = "", lang: str = "") -> str:
    """数据质量根因追踪（确定性）：粘贴建表/加工 SQL 脚本 + 出问题的表
    （可选列与症状），沿 SQL 血缘上溯为每个上游打嫌疑分 — 距离越近越高、
    列级污染路径 +40、存在变换表达式（SUM/CAST/CASE…）+10，不在污染
    路径上的降权；每个嫌疑附变换点与可直接运行的验证 SQL。不连数据库。"""
    from seatunnel_agent.agents.data.quality_trace import (
        build_graph_from_sql,
        render_markdown,
        trace_quality,
    )

    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    if not (table or "").strip():
        return "表名不能为空 / table must not be empty"
    try:
        graph, warnings = build_graph_from_sql(sql)
        result = trace_quality(graph, warnings, table,
                               column=column, symptom=symptom)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
