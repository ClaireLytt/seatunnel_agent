"""Chat/MCP tool entry point for the watermark planner.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def watermark_plan(events: str, lang: str = "") -> str:
    """水位线选型（确定性）：粘贴观测事件（CSV 带表头或 JSONL,列
    event_time/arrival_time）,测出乱序率与迟到 p50/p95/p99/最大,给出
    乱序容忍建议（常规 p99 + 25% 余量,超一小时掉队者剔除防小样本退化）,
    附 Flink SQL WATERMARK 子句与 forBoundedOutOfOrderness 片段;时钟
    漂移/重尾/掉队者分级点名。不连集群。"""
    from seatunnel_agent.agents.data.sample_profile import parse_rows
    from seatunnel_agent.agents.data.watermark_plan import (
        plan_watermark,
        render_markdown,
    )

    if not (events or "").strip():
        return "事件不能为空 / events must not be empty"
    try:
        headers, rows = parse_rows(events)
        plan = plan_watermark(headers, rows)
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(plan, lang=normalize_lang(lang))
