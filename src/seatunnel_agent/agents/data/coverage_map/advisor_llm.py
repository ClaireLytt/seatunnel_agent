"""Optional LLM coverage review from a coverage map.

The deterministic mapper draws the map; this layer drafts the gap-
closing plan.  Strictly opt-in and bounded to one call per map.
"""

from __future__ import annotations

import json

from .mapper import CoverageMap

__all__ = ["coverage_note"]

_SYSTEM_ZH = (
    "你是数据质量平台负责人。给定一份质量覆盖地图 JSON（逐表的 DQC 检查"
    "类型计数与契约有无、裸奔表与死闸清单、总体覆盖率），起草补洞计划："
    "按风险排序先补哪些表、每张该先上哪类检查、死闸怎么处置。只输出计划 "
    "markdown 列表，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the data-quality platform lead. Given a coverage map JSON "
    "(per-table DQC check counts and contract presence, unguarded "
    "tables and dead gates, overall share), draft the gap-closing plan: "
    "which tables to protect first by risk, which check each should "
    "start with, what to do with the dead gates. Markdown bullets only, "
    "terse.")


def coverage_note(cmap: CoverageMap, lang: str = "zh") -> str:
    """One LLM call → a gap-closing plan for this map."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(cmap.to_dict(), ensure_ascii=False)
    return one_shot("coverage_map", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
