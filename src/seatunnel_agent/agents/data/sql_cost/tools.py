"""Chat/MCP tool entry point for the SQL cost estimator.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def sql_cost(sql: str, stats: str, lang: str = "") -> str:
    """SQL 资源消耗预测（确定性）：给一条 SQL 和表统计清单（JSON/CSV，
    字段 table/rows/bytes/partitions/partition_col/columns），自底向上
    估算扫描量（分区与列裁剪折扣）、join/聚合的 shuffle 字节、输出行数、
    任务内存峰值、核·秒与建议并行度下 0.5x–2x 的耗时区间；所有建模假设
    随结果一起列出。清单里没有的表会被点名并排除，不乱猜。不连数据库。"""
    from seatunnel_agent.agents.data.sql_cost import (
        estimate,
        parse_stats,
        render_markdown,
    )

    if not (sql or "").strip():
        return "SQL 不能为空 / SQL must not be empty"
    if not (stats or "").strip():
        return "表统计清单不能为空 / stats inventory must not be empty"
    try:
        card = estimate(sql, parse_stats(stats))
    except Exception as exc:  # bad values or malformed JSON
        return f"输入有误 / bad input: {exc}"
    return render_markdown(card, lang=normalize_lang(lang))
