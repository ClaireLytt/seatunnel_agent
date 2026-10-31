"""Optional LLM schedule note from a schedule advice.

The deterministic advisor computes the timeline; this layer turns the
numbers into a paste-ready note for the platform channel.  Strictly
opt-in and bounded to one call per plan.
"""

from __future__ import annotations

import json

from .advisor import ScheduleResult

__all__ = ["schedule_note"]

_SYSTEM_ZH = (
    "你是调度平台的排程负责人。根据给定的调度建议 JSON（SLA 任务与"
    "余量、关键路径、并行峰值、可错峰任务与各任务时间线），起草一条发给"
    "平台群的排程通报：SLA 稳不稳、瓶颈链是谁、建议把谁挪到什么时候、"
    "余量薄的话先缩短哪一步。只输出通报正文 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the scheduling owner. From the given schedule-advice JSON "
    "(SLA task and margin, critical path, peak parallelism, movable "
    "tasks and the per-task timeline), draft a platform-channel note: "
    "whether the SLA holds, the bottleneck chain, who to move where, and "
    "what to shorten first when the margin is thin. Markdown body only, "
    "terse.")


def schedule_note(result: ScheduleResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready schedule note for this plan."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("schedule_advisor", _SYSTEM_ZH, _SYSTEM_EN, payload,
                    lang)
