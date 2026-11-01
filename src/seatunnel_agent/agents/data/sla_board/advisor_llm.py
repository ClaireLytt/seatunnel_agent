"""Optional LLM SLA review from a board.

The deterministic board measures the promise; this layer drafts the
weekly SLA review the team sends upward.  Strictly opt-in and bounded
to one call per board.
"""

from __future__ import annotations

import json

from .board import SlaBoard

__all__ = ["sla_note"]

_SYSTEM_ZH = (
    "你是数据平台值班负责人。给定一份 SLA 达成看板 JSON（总达成率与目标、"
    "逐任务达成率/迟到分位/连续破线、分级发现），起草周度 SLA 通报：整体"
    "结论、最差的任务与各自的破线形态（慢性迟到还是连续失守）、建议的"
    "处置顺序。只输出通报 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the data-platform on-call lead. Given an SLA board JSON "
    "(overall attainment vs target, per-task rates, lateness "
    "percentiles, live miss streaks, graded findings), draft the weekly "
    "SLA update: the headline, the worst tasks and the shape of each "
    "miss (chronic lateness vs a live streak), and the order to act. "
    "Markdown only, terse.")


def sla_note(board: SlaBoard, lang: str = "zh") -> str:
    """One LLM call → a weekly SLA update for this board."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(board.to_dict(), ensure_ascii=False)
    return one_shot("sla_board", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
