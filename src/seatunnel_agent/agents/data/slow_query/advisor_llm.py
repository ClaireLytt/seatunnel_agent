"""Optional LLM incident-note draft from a slow-query diagnosis.

The deterministic diagnoser says which rules fired and their share of
the slowdown; this layer turns that into a paste-ready note for the
ops channel.  Strictly opt-in and bounded to one call per diagnosis.
"""

from __future__ import annotations

import json

from .diagnoser import Diagnosis

__all__ = ["incident_note"]

_SYSTEM_ZH = (
    "你是数据平台值班工程师。根据给定的慢查询诊断 JSON（耗时、相对基线"
    "的回归倍数、按占比排序的根因与证据、每条根因的处方），起草一条发到"
    "值班群的慢查询通报：慢了多少、主因是什么、证据一句话、下一步排查/"
    "修复动作（按处方）。只输出通报正文 markdown，简洁、面向使用方，"
    "不要寒暄。")
_SYSTEM_EN = (
    "You are the on-call data-platform engineer. From the given slow-query "
    "diagnosis JSON (duration, regression vs the baseline, causes ranked "
    "by share with evidence and prescriptions), draft a note for the ops "
    "channel: how slow, the dominant cause, one-line evidence, next "
    "actions per the prescriptions. Markdown body only, terse, "
    "audience-facing.")


def incident_note(diag: Diagnosis, lang: str = "zh") -> str:
    """One LLM call → a paste-ready slow-query note for this diagnosis."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(diag.to_dict(), ensure_ascii=False)
    return one_shot("slow_query", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
