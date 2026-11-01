"""Optional LLM rollback note from a rollback plan.

The deterministic planner orders the steps; this layer turns the plan
into a paste-ready incident update.  Strictly opt-in and bounded to one
call per plan.
"""

from __future__ import annotations

import json

from .planner import RollbackPlan

__all__ = ["rollback_note"]

_SYSTEM_ZH = (
    "你是数据事故指挥。根据给定的回滚编排 JSON（坏表与分区、恢复方式、"
    "下游分层重跑步骤、涉及表数、关键路径估时），起草一条发到事故群的"
    "进展通报：影响面多大、按什么顺序恢复、预计多久、消费方何时能用。"
    "只输出通报正文 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the incident commander. From the given rollback-plan JSON "
    "(bad table and partitions, restore mode, leveled downstream re-run "
    "steps, tables touched, critical-path estimate), draft an "
    "incident-channel update: the blast radius, the recovery order, the "
    "ETA, and when consumers can trust the data again. Markdown body "
    "only, terse.")


def rollback_note(plan: RollbackPlan, lang: str = "zh") -> str:
    """One LLM call → a paste-ready incident update for this plan."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(plan.to_dict(), ensure_ascii=False)
    return one_shot("rollback_plan", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
