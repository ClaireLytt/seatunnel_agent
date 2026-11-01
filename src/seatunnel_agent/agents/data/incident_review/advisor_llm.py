"""Optional LLM postmortem draft from an incident review.

The deterministic reviewer computes the timeline and the numbers; this
layer drafts the postmortem document around them.  Strictly opt-in and
bounded to one call per review.
"""

from __future__ import annotations

import json

from .reviewer import IncidentReview

__all__ = ["postmortem_note"]

_SYSTEM_ZH = (
    "你是事故复盘主持人。给定一份事故时间线 JSON（逐条事件、发现/响应/"
    "恢复用时、静默窗口等分级发现），起草复盘文档：事故摘要、时间线要点、"
    "三个用时各自暴露的问题、改进项（每条写清负责人占位与验收标准）。"
    "只输出文档 markdown，简洁，不要寒暄，不要追责语气。")
_SYSTEM_EN = (
    "You are the postmortem facilitator. Given an incident timeline "
    "JSON (events, detection/response/recovery durations, silent-window "
    "findings), draft the postmortem: summary, timeline highlights, "
    "what each duration exposes, and action items (each with an owner "
    "placeholder and an acceptance check). Markdown only, terse, "
    "blameless.")


def postmortem_note(review: IncidentReview, lang: str = "zh") -> str:
    """One LLM call → a postmortem draft for this incident."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(review.to_dict(), ensure_ascii=False)
    return one_shot("incident_review", _SYSTEM_ZH, _SYSTEM_EN, payload,
                    lang)
