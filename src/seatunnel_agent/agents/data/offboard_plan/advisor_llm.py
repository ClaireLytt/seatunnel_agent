"""Optional LLM retirement notice from an offboarding plan.

The deterministic planner stages the steps; this layer drafts the
notice that goes to the consumers.  Strictly opt-in and bounded to one
call per plan.
"""

from __future__ import annotations

import json

from .planner import OffboardPlan

__all__ = ["retirement_note"]

_SYSTEM_ZH = (
    "你是数据平台治理负责人。给定一份表下线方案 JSON（表名、公示期、是否"
    "被下游阻塞及消费方清单、公示/冻结/归档/删除四阶段步骤），起草发给"
    "消费方的下线通告：时间线、各方要做什么、归档在哪、逾期后果。只输出"
    "通告 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the data-platform governance lead. Given a table "
    "offboarding plan JSON (table, grace window, whether downstream "
    "consumers block it and who they are, the announce/freeze/archive/"
    "drop stages), draft the retirement notice for the consumers: the "
    "timeline, what each party must do, where the archive lives, what "
    "happens after the deadline. Markdown only, terse.")


def retirement_note(plan: OffboardPlan, lang: str = "zh") -> str:
    """One LLM call → a retirement notice for this plan."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(plan.to_dict(), ensure_ascii=False)
    return one_shot("offboard_plan", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
