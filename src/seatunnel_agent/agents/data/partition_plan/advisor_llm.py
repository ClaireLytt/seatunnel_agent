"""Optional LLM plan review from a partition plan.

The deterministic planner scores the candidates; this layer drafts the
review a storage engineer would give before the DDL lands.  Strictly
opt-in and bounded to one call per plan.
"""

from __future__ import annotations

import json

from .planner import PartitionPlan

__all__ = ["plan_note"]

_SYSTEM_ZH = (
    "你是存储引擎评审。给定一份分区键选型 JSON（候选列的基数/WHERE 命中/"
    "得分/结论、推荐的 PARTITIONED BY 与可选 CLUSTERED BY、分级发现），"
    "起草落 DDL 前的评审：推荐键的增长预估与风险、要不要二级分区、分桶数"
    "是否合适、负载窗口有没有盲区。只输出评审 markdown 列表，简洁，"
    "不要寒暄。")
_SYSTEM_EN = (
    "You are a storage-engine reviewer. Given a partition-plan JSON "
    "(candidate cardinalities, WHERE hits, scores and verdicts, the "
    "recommended PARTITIONED BY and optional CLUSTERED BY, graded "
    "findings), draft the pre-DDL review: growth outlook and risks of "
    "the recommended key, whether a secondary partition earns its keep, "
    "whether the bucket count fits, and blind spots in the workload "
    "window. Markdown bullets only, terse.")


def plan_note(plan: PartitionPlan, lang: str = "zh") -> str:
    """One LLM call → a pre-DDL review for this plan."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(plan.to_dict(), ensure_ascii=False)
    return one_shot("partition_plan", _SYSTEM_ZH, _SYSTEM_EN, payload,
                    lang)
