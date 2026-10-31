"""Optional LLM incident-note draft from a rerun plan.

The deterministic plan says what failed, what re-runs, in which order
and how long it takes; this layer turns that into a paste-ready ops
notification.  Strictly opt-in and bounded to one call per plan.
"""

from __future__ import annotations

import json

from .planner import RerunPlan

__all__ = ["incident_note"]

_SYSTEM_ZH = (
    "你是数据平台值班工程师。根据给定的任务重跑计划 JSON（失败任务、"
    "重跑批次、影响面、预计耗时、可独立恢复分组），起草一条发到运维群的"
    "事故通告：影响范围、恢复动作与顺序、预计恢复时间、不受影响的说明。"
    "只输出通告正文 markdown，简洁、面向使用方，不要寒暄。")
_SYSTEM_EN = (
    "You are the on-call data-platform engineer. From the given rerun-plan "
    "JSON (failed tasks, batches, blast radius, ETA, recovery groups), "
    "draft an incident note for the ops channel: impact, recovery actions "
    "and order, ETA, what is unaffected. Markdown body only, terse, "
    "audience-facing.")


def incident_note(plan: RerunPlan, lang: str = "zh") -> str:
    """One LLM call → a paste-ready incident note for this plan."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(plan.to_dict(), ensure_ascii=False)
    return one_shot("rerun_plan", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
