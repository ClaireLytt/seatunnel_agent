"""Chat/MCP tool entry point for the schedule advisor.

Declared in the manifest (``tools=``), discovered by the MCP toolbox and
the orchestrator catalog/router. String-in / markdown-out, deterministic.
"""

from __future__ import annotations

from seatunnel_agent.common.utils import normalize_lang


def schedule_advisor(plan: str, lang: str = "") -> str:
    """调度窗口优化（确定性）：粘贴一天的排程计划 JSON（day_start、
    tasks[] 的 name/duration_min/deps、可选 sla.task 与 sla.deadline），
    输出最早排程时间线、SLA 余量（薄/破线点名）、关键路径（想提前只能
    缩短它们）、每个任务相对 SLA 的松弛分钟、并行峰值窗口与可错峰任务
    清单。时长建议喂 p95。不连调度器。"""
    from seatunnel_agent.agents.data.schedule_advisor import (
        advise_schedule,
        parse_plan,
        render_markdown,
    )

    if not (plan or "").strip():
        return "计划不能为空 / plan must not be empty"
    try:
        result = advise_schedule(parse_plan(plan))
    except ValueError as exc:
        return f"输入有误 / bad input: {exc}"
    return render_markdown(result, lang=normalize_lang(lang))
