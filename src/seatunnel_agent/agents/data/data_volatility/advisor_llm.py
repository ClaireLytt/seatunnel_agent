"""Optional LLM volatility note from a series analysis.

The deterministic analyzer says which metrics moved and how; this layer
turns the findings into a paste-ready note for the metric-owner channel.
Strictly opt-in and bounded to one call per analysis.
"""

from __future__ import annotations

import json

from .analyzer import VolResult

__all__ = ["volatility_note"]

_SYSTEM_ZH = (
    "你是数据平台的指标值班。根据给定的波动分析 JSON（各指标点数、按"
    "严重度排序的发现：突增/突降（日期、幅度）、水平位移、走平、日期"
    "断档），起草一条发给指标负责人的波动通报：哪些指标在哪天动了、动了"
    "多少、最可能的解释方向（业务事件/上游故障/口径变更）、建议的下一步"
    "（确认业务侧/沿血缘追根因）。只输出通报正文 markdown，简洁，"
    "不要寒暄。")
_SYSTEM_EN = (
    "You are the metrics on-call. From the given volatility JSON (points "
    "per metric; findings ranked by severity: surges/drops with dates and "
    "magnitudes, level shifts, flatlines, date gaps), draft a note for "
    "the metric owners: which metrics moved on which dates and by how "
    "much, the likely explanation to check (business event / upstream "
    "failure / definition change), and the next step. Markdown body "
    "only, terse.")


def volatility_note(result: VolResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready volatility note for this analysis."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("data_volatility", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
