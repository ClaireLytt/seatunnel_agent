"""Optional LLM digest note from an alert-storm analysis.

The deterministic analyzer clusters and judges the channel; this layer
turns it into a paste-ready digest for the on-call handover.  Strictly
opt-in and bounded to one call per analysis.
"""

from __future__ import annotations

import json

from .analyzer import StormResult

__all__ = ["digest_note"]

_SYSTEM_ZH = (
    "你是值班交接人。根据给定的告警风暴摘要 JSON（总条数/真实事件数/"
    "降噪倍数/聚类清单/风暴窗口/横跳签名/吵闹来源），起草一条交接摘要："
    "这个班真实发生了几件事、各是什么、哪些告警建议加抑制、交给下个班"
    "注意什么。只输出摘要正文 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are writing the on-call handover. From the given alert-storm "
    "JSON (pages, distinct events, dedup ratio, clusters, storm windows, "
    "flapping signatures, noisy sources), draft the handover digest: how "
    "many real things happened this shift and what they were, which "
    "alerts deserve suppression, and what the next shift should watch. "
    "Markdown body only, terse.")


def digest_note(result: StormResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready handover digest."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("alert_storm", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
