"""Chat/MCP tool entry point for the partition planner.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def partition_plan(sample: str, queries: str, lang: str = "") -> str:
    """分区键选型（确定性）：粘贴表的数据样例（CSV 带表头或 JSONL）+ 将要
    打在这张表上的查询 SQL,逐列按 WHERE 过滤频率 × 时间形 × 基数甜区
    （2..5000）打分排名,给出 PARTITIONED BY 推荐;高基数热过滤的 id 列
    改配 CLUSTERED BY 分桶。为还没分区的表选键,已有分区的找分区体检。
    不连数据库。"""
    from seatunnel_agent.agents.data.partition_plan import (
        plan_partitions,
        render_markdown,
    )
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    if not (sample or "").strip() or not (queries or "").strip():
        return "样例与查询都不能为空 / both sample and queries are required"
    try:
        headers, rows = parse_rows(sample)
        plan = plan_partitions(headers, rows, queries)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(plan, lang=normalize_lang(lang))
