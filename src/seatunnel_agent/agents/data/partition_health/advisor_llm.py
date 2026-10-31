"""Optional LLM partition note from a health check.

The deterministic analyzer lists the findings; this layer turns them
into a paste-ready note for the ops channel.  Strictly opt-in and
bounded to one call per check.
"""

from __future__ import annotations

import json

from .analyzer import PartitionHealthResult

__all__ = ["partition_note"]

_SYSTEM_ZH = (
    "你是数据平台值班工程师。根据给定的分区体检 JSON（表数/分区数/按"
    "严重度排序的发现：日期断档、空分区、大小倾斜、最新分区暴涨或缩水，"
    "每条带证据与处方），起草一条发到值班群的分区通报：哪些表要先处理、"
    "各自第一动作、哪些只需观察。只输出通报正文 markdown，简洁，"
    "不要寒暄。")
_SYSTEM_EN = (
    "You are the data-platform on-call. From the given partition-health "
    "JSON (tables, partitions, findings ranked by severity — date gaps, "
    "empty partitions, size skew, a surging or shrunken latest "
    "partition, each with evidence and a prescription), draft an "
    "ops-channel note: which tables to fix first, the first action for "
    "each, and which just need watching. Markdown body only, terse.")


def partition_note(result: PartitionHealthResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready partition note for this check."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("partition_health", _SYSTEM_ZH, _SYSTEM_EN, payload,
                    lang)
