"""Optional LLM consolidation plan from a duplicate-pipeline report.

The deterministic detector names the overlaps; this layer drafts the
consolidation plan — who merges into whom, and in what order.  Strictly
opt-in and bounded to one call per report.
"""

from __future__ import annotations

import json

from .detector import DupReport

__all__ = ["consolidation_note"]

_SYSTEM_ZH = (
    "你是数仓治理负责人。给定一份重复建设检测 JSON（同源双建、子集派生"
    "候选、源表高扇出），起草收敛方案：哪两条链路合并、保留哪张表、下游"
    "怎么迁移、高扇出的源该沉淀什么中间层。只输出方案 markdown 列表，"
    "按节省收益排序，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the warehouse governance lead. Given a duplicate-pipeline "
    "report JSON (same-source double builds, subset-derivation "
    "candidates, high fan-out sources), draft the consolidation plan: "
    "which pipelines merge, which table survives, how consumers "
    "migrate, and what middle layer the hot sources deserve. Markdown "
    "bullets only, ordered by savings, terse.")


def consolidation_note(report: DupReport, lang: str = "zh") -> str:
    """One LLM call → a consolidation plan for this report."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(report.to_dict(), ensure_ascii=False)
    return one_shot("dup_pipeline", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
