"""Optional LLM capacity note from a forecast.

The deterministic forecaster computes the numbers; this layer turns
them into a paste-ready note for the platform channel.  Strictly opt-in
and bounded to one call per forecast.
"""

from __future__ import annotations

import json

from .forecaster import CapacityResult

__all__ = ["capacity_note"]

_SYSTEM_ZH = (
    "你是数据平台的容量负责人。根据给定的容量预测 JSON（配额、当前总量、"
    "日增速、预计耗尽日期、增长大户与在缩小的指标），起草一条发给平台群"
    "的容量通报：还剩多久、增长主要来自谁、先扩容还是先清理（清理可指向"
    "存储成本治理）、下一次复核时间。只输出通报正文 markdown，简洁，"
    "不要寒暄。")
_SYSTEM_EN = (
    "You are the capacity owner. From the given forecast JSON (quota, "
    "current total, daily growth, exhaustion date, top growers and "
    "shrinking metrics), draft a platform-channel note: how long is "
    "left, who drives the growth, expand or clean up first (cleanup via "
    "the storage-cost agent), and when to re-check. Markdown body only, "
    "terse.")


def capacity_note(result: CapacityResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready capacity note for this forecast."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("capacity_forecast", _SYSTEM_ZH, _SYSTEM_EN, payload,
                    lang)
