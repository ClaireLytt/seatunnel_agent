"""Optional LLM ops note from a Kafka-lag diagnosis.

The deterministic analyzer says which rules fired; this layer turns the
findings into a paste-ready note for the ops channel.  Strictly opt-in
and bounded to one call per diagnosis.
"""

from __future__ import annotations

import json

from .analyzer import LagResult

__all__ = ["ops_note"]

_SYSTEM_ZH = (
    "你是实时平台值班工程师。根据给定的 Kafka 积压诊断 JSON（消费组、"
    "总积压、按严重度排序的发现：积压量/热点分区/追不上/停滞/追赶 ETA，"
    "每条带证据与处方；另有积压 Top 分区表），起草一条发到值班群的运维"
    "通报：积压多严重、主因是什么、第一动作是什么、预计多久恢复。只输出"
    "通报正文 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the realtime-platform on-call. From the given Kafka-lag "
    "diagnosis JSON (group, total lag, findings ranked by severity with "
    "evidence and prescriptions, plus the top lagging partitions), draft "
    "an ops-channel note: how bad the backlog is, the dominant cause, "
    "the first action, and the recovery estimate. Markdown body only, "
    "terse.")


def ops_note(result: LagResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready ops note for this diagnosis."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("kafka_lag", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
