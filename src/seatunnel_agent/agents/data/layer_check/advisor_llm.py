"""Optional LLM layering note from a layer-check result.

The deterministic checker lists the violations; this layer turns them
into a paste-ready refactoring note for the modeling channel.  Strictly
opt-in and bounded to one call per check.
"""

from __future__ import annotations

import json

from .checker import LayerResult

__all__ = ["layering_note"]

_SYSTEM_ZH = (
    "你是数仓建模负责人。根据给定的分层体检 JSON（表数/血缘边数/分层"
    "分布/按严重度排序的违规：跨层引用、反向依赖、同层叠加、未知分层），"
    "起草一条发给建模群的整改通报：哪几条边必须改、建议补建或复用哪张"
    "中间表、整改顺序。只输出通报正文 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the warehouse-modeling owner. From the given layering-check "
    "JSON (tables, edges, layer distribution, violations ranked by "
    "severity — layer skips, reverse dependencies, same-layer chaining, "
    "unknown layers), draft a modeling-channel note: which edges must "
    "change, which intermediate table to build or reuse, and the "
    "refactoring order. Markdown body only, terse.")


def layering_note(result: LayerResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready layering note for this check."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("layer_check", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
