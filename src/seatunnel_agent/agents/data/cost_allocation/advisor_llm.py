"""Optional LLM billing note from a cost bill.

The deterministic allocator computes the numbers; this layer drafts the
note that goes with the bill.  Strictly opt-in and bounded to one call
per bill.
"""

from __future__ import annotations

import json

from .allocator import CostBill

__all__ = ["billing_note"]

_SYSTEM_ZH = (
    "你是数据平台财务对接人。给定一份成本分摊账单 JSON（逐归属方的存储/"
    "计算/合计与占比、各家成本大头、无主开销占比、分级发现），起草随账单"
    "发出的通报：各家本期大头是什么、无主条目怎么认领、哪里有明显的优化"
    "空间。只输出通报 markdown，按金额排序，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the data platform's finance liaison. Given a cost "
    "allocation bill JSON (per-owner storage/compute/total and share, "
    "each owner's top cost drivers, the unallocated share, graded "
    "findings), draft the note that travels with the bill: each "
    "owner's main driver, how unallocated items get claimed, where the "
    "obvious savings are. Markdown only, ordered by spend, terse.")


def billing_note(bill: CostBill, lang: str = "zh") -> str:
    """One LLM call → a billing note for this bill."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(bill.to_dict(), ensure_ascii=False)
    return one_shot("cost_allocation", _SYSTEM_ZH, _SYSTEM_EN, payload,
                    lang)
