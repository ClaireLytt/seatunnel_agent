"""Optional LLM rollout narrative for a strategy report.

The deterministic advisor picks the strategy per table with reasons and
risks; this layer writes the ops-readable rollout plan — why each
choice, cutover order and steps, what to monitor.  Strictly opt-in and
bounded to one call per fleet.
"""

from __future__ import annotations

import json

from .advisor import StrategyReport

__all__ = ["rollout_narrative"]

_SYSTEM_ZH = (
    "你是数据同步平台负责人。根据给定的逐表同步策略推荐 JSON（策略、"
    "理由、风险、调度、行数与节省），写一份落地推进方案：选型解读、"
    "切换顺序与步骤、每张表上线后要盯的监控点、回退预案。只输出 "
    "markdown，务实、面向执行，不要寒暄。")
_SYSTEM_EN = (
    "You own the data-sync platform. From the per-table strategy "
    "recommendation JSON (strategy, reasons, risks, schedule, rows and "
    "savings), write the rollout plan: rationale, cutover order and "
    "steps, monitoring points per table, rollback plan. Markdown only, "
    "pragmatic, execution-facing.")


def rollout_narrative(report: StrategyReport, lang: str = "zh") -> str:
    """One LLM call → the rollout narrative for this fleet."""
    from seatunnel_agent.common.llm import one_shot

    data = report.to_dict()
    for rec in data["recommendations"]:
        rec.pop("config", None)  # configs are long and not needed here
    payload = json.dumps(data, ensure_ascii=False)
    return one_shot("sync_strategy", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
