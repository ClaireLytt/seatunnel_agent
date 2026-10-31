"""Optional LLM latency note from an end-to-end analysis.

The deterministic analyzer locates the dominant hop and the outliers;
this layer turns the numbers into a paste-ready note for the ops
channel.  Strictly opt-in and bounded to one call per analysis.
"""

from __future__ import annotations

import json

from .analyzer import LatencyResult

__all__ = ["latency_note"]

_SYSTEM_ZH = (
    "你是实时平台值班工程师。根据给定的端到端延迟 JSON（各段与端到端的 "
    "p50/p95/max、主导段、离群事件与其最慢段、SLA 破线数），起草一条发到"
    "值班群的延迟通报：延迟花在哪一段、是普遍慢还是个别事件慢（看离群"
    "清单）、建议的下一步（主导段对应的排查方向）。只输出通报正文 "
    "markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the realtime-platform on-call. From the given end-to-end "
    "latency JSON (per-hop and e2e p50/p95/max, the dominant hop, "
    "outlier events with their worst hop, SLA breaches), draft an "
    "ops-channel note: where the time goes, whether it is uniformly slow "
    "or a few outliers, and the next step for the dominant hop. "
    "Markdown body only, terse.")


def latency_note(result: LatencyResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready latency note for this analysis."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("rt_latency", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
