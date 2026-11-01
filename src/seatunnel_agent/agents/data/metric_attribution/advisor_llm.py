"""Optional LLM attribution note from a dimensional decomposition.

The deterministic attributor computes the exact contributions; this
layer turns them into a paste-ready answer for the business channel.
Strictly opt-in and bounded to one call per attribution.
"""

from __future__ import annotations

import json

from .attributor import AttributionResult

__all__ = ["attribution_note"]

_SYSTEM_ZH = (
    "你是数据团队的指标负责人。根据给定的异动归因 JSON（指标前后值与"
    "变动、各维度的逐值贡献分解、头号贡献/集中度/结构漂移判定），起草"
    "一条回复业务方的归因说明：变动主要来自哪个维度的哪个值、是单点"
    "事故还是结构性漂移、建议的下一步核实动作。只输出说明正文 "
    "markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the metric owner. From the given attribution JSON (metric "
    "before/after, per-dimension per-value contributions, top-contributor"
    "/concentration/mix-shift verdicts), draft the reply to the business "
    "side: which value on which dimension drove the move, whether it is "
    "a single-value incident or a mix shift, and the next verification "
    "step. Markdown body only, terse.")


def attribution_note(result: AttributionResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready attribution reply."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("metric_attribution", _SYSTEM_ZH, _SYSTEM_EN, payload,
                    lang)
