"""Optional LLM rollout note from a topic-schema diff.

The deterministic differ grades the changes; this layer drafts the note
that goes to the topic's producers and consumers.  Strictly opt-in and
bounded to one call per diff.
"""

from __future__ import annotations

import json

from .differ import SchemaDiffReport

__all__ = ["rollout_note"]

_SYSTEM_ZH = (
    "你是消息平台治理负责人。给定一份 topic Schema 兼容性对比 JSON"
    "（兼容模式、结论、逐字段变更与破坏的模式），起草发给生产方与消费方"
    "的发布通报：哪些变更会被注册中心拒绝及怎么改（补默认值/加 null/"
    "先双写）、消费方要不要升级、发布顺序。只输出通报 markdown，简洁，"
    "不要寒暄。")
_SYSTEM_EN = (
    "You are the messaging-platform governance lead. Given a topic "
    "schema compatibility diff JSON (mode, verdict, per-field changes "
    "with the modes they break), draft the rollout note for producers "
    "and consumers: which changes the registry will reject and the fix "
    "(add a default, widen with null, dual-write first), whether "
    "consumers must upgrade, and the publish order. Markdown only, "
    "terse.")


def rollout_note(report: SchemaDiffReport, lang: str = "zh") -> str:
    """One LLM call → a rollout note for this schema change."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(report.to_dict(), ensure_ascii=False)
    return one_shot("topic_schema", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
