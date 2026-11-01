"""Optional LLM governance note from a storage-cost analysis.

The deterministic analyzer lists the actions; this layer turns them into
a paste-ready note for the platform channel.  Strictly opt-in and
bounded to one call per analysis.
"""

from __future__ import annotations

import json

from .analyzer import CostResult

__all__ = ["governance_note"]

_SYSTEM_ZH = (
    "你是数据平台的成本治理值班。根据给定的存储治理 JSON（总量、可释放"
    "量、按收益排序的动作：迁冷/清理过期分区/小文件合并，每条带证据），"
    "起草一条发给平台群的治理通报：能省多少、先做哪三件事、执行前的"
    "确认项（下游消费方、备份）。只输出通报正文 markdown，简洁，"
    "不要寒暄。")
_SYSTEM_EN = (
    "You are the platform cost-governance on-call. From the given "
    "storage JSON (total GB, reclaimable GB, actions ranked by win — "
    "cold-tier moves, expired-partition drops, small-file compaction, "
    "each with evidence), draft a platform-channel note: the savings, "
    "the top three moves, and the pre-flight checks (downstream "
    "consumers, backups). Markdown body only, terse.")


def governance_note(result: CostResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready governance note."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("storage_cost", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
