"""Optional LLM watermark review from a plan.

The deterministic planner measures and sizes; this layer drafts the
deployment review.  Strictly opt-in and bounded to one call per plan.
"""

from __future__ import annotations

import json

from .planner import WatermarkPlan

__all__ = ["watermark_note"]

_SYSTEM_ZH = (
    "你是流计算评审。给定一份水位线选型 JSON（乱序率、迟到分位、建议乱序"
    "容忍与残余比例、时钟漂移/重尾/掉队者发现），起草部署前评审：该界对"
    "延迟和正确性的取舍、allowed lateness 与侧输出怎么配、时钟漂移先修"
    "什么、何时需要重测。只输出评审 markdown 列表，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are a stream-processing reviewer. Given a watermark plan JSON "
    "(out-of-order share, lateness percentiles, suggested bound with "
    "residual share, clock-skew/heavy-tail/straggler findings), draft "
    "the pre-deploy review: the latency-vs-correctness trade at this "
    "bound, how to set allowed lateness and the side output, what to "
    "fix first for clock skew, when to re-measure. Markdown bullets "
    "only, terse.")


def watermark_note(plan: WatermarkPlan, lang: str = "zh") -> str:
    """One LLM call → a pre-deploy review for this bound."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(plan.to_dict(), ensure_ascii=False)
    return one_shot("watermark_plan", _SYSTEM_ZH, _SYSTEM_EN, payload,
                    lang)
