"""Optional LLM compaction review from a plan.

The deterministic planner ranks the merges; this layer drafts the
execution review.  Strictly opt-in and bounded to one call per plan.
"""

from __future__ import annotations

import json

from .planner import CompactPlan

__all__ = ["compaction_note"]

_SYSTEM_ZH = (
    "你是存储治理评审。给定一份小文件治理计划 JSON（合并候选分区、收敛"
    "文件数、极端分区与表级占比发现），起草执行评审：合并批次怎么排"
    "（低峰/并发上限）、CONCATENATE 与 INSERT OVERWRITE 各适用哪些表、"
    "跑完怎么核对、产生小文件的根因（写入并发/flush 配置）该在哪改。"
    "只输出评审 markdown 列表，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are a storage-governance reviewer. Given a compaction plan "
    "JSON (merge candidates, files freed, extreme partitions, per-table "
    "shares), draft the execution review: batch ordering (off-peak, "
    "concurrency caps), where CONCATENATE vs INSERT OVERWRITE applies, "
    "post-merge verification, and where the small-file root cause "
    "(writer parallelism, flush settings) should be fixed. Markdown "
    "bullets only, terse.")


def compaction_note(plan: CompactPlan, lang: str = "zh") -> str:
    """One LLM call → an execution review for this plan."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(plan.to_dict(), ensure_ascii=False)
    return one_shot("compact_plan", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
