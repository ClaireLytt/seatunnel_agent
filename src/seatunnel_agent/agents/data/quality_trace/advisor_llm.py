"""Optional LLM trace note from a quality root-cause trace.

The deterministic tracer ranks the suspects; this layer turns the
ranking into a paste-ready note for the incident channel.  Strictly
opt-in and bounded to one call per trace.
"""

from __future__ import annotations

import json

from .tracer import TraceResult

__all__ = ["trace_note"]

_SYSTEM_ZH = (
    "你是数据平台的质量值班。根据给定的根因追踪 JSON（质量事件：表/列/"
    "症状；按分数排序的嫌疑上游：距离、被污染列、变换点、验证 SQL），"
    "起草一条发到事故群的追踪通报：症状一句话、首要嫌疑及其证据（变换点"
    "表达式）、建议的验证顺序（先跑哪条验证 SQL）、如果首要嫌疑排除后"
    "下一个查谁。只输出通报正文 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the data-quality on-call. From the given root-cause trace "
    "JSON (the quality event: table/column/symptom; suspects ranked by "
    "score with distance, tainted columns, mutation points and "
    "verification SQL), draft an incident-channel note: the symptom in "
    "one line, the prime suspect with its evidence, the verification "
    "order, and who to check next if the prime suspect clears. Markdown "
    "body only, terse.")


def trace_note(result: TraceResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready trace note for this event."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("quality_trace", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
