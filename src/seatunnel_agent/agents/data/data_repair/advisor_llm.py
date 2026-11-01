"""Optional LLM repair note from a consistency-repair plan.

The deterministic planner writes the SQL; this layer turns the plan into
a paste-ready change note for the data-owner channel.  Strictly opt-in
and bounded to one call per plan.
"""

from __future__ import annotations

import json

from .planner import RepairPlan

__all__ = ["repair_note"]

_SYSTEM_ZH = (
    "你是数据平台的数据质量值班。根据给定的一致性修复方案 JSON（表名、"
    "扫描行数、按级别排序的修复动作：去重/空值回填/标准化/数值转换/"
    "格式修复，每条带依据与 SQL 模板），起草一条发给数据负责人的修复"
    "变更说明：要修什么、为什么、执行顺序与注意事项（占位符需先决策、"
    "先在 staging 演练）。只输出正文 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the data-quality on-call. From the given repair-plan JSON "
    "(table, rows scanned, actions ranked by severity — dedup, null "
    "backfill, standardization, numeric casts, format fixes, each with "
    "rationale and a SQL template), draft a change note for the data "
    "owners: what gets fixed and why, the execution order, and the "
    "cautions (decide the placeholders first, rehearse in staging). "
    "Markdown body only, terse.")


def repair_note(plan: RepairPlan, lang: str = "zh") -> str:
    """One LLM call → a paste-ready change note for this plan."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(plan.to_dict(), ensure_ascii=False)
    return one_shot("data_repair", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
