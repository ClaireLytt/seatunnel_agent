"""Optional LLM data-review note from a sample profile.

The deterministic profiler says which columns look wrong; this layer
turns the findings into a paste-ready note for the data-owner channel.
Strictly opt-in and bounded to one call per profile.
"""

from __future__ import annotations

import json

from .profiler import ProfileResult

__all__ = ["review_note"]

_SYSTEM_ZH = (
    "你是数据平台的数据质量值班。根据给定的抽样剖析 JSON（每列的类型/"
    "空值率/唯一率/格式桶，以及按严重度排序的发现），起草一条发给数据"
    "负责人的体检通报：哪些列有什么问题、影响是什么、建议的下一步"
    "（修数/改上游/补约束）。只输出通报正文 markdown，简洁、面向使用方，"
    "不要寒暄。")
_SYSTEM_EN = (
    "You are the data-quality on-call. From the given sample-profile JSON "
    "(per-column kind, null/unique rates, format buckets, findings ranked "
    "by severity), draft a note for the data owners: which columns are "
    "wrong, the impact, and the next step (fix data / fix upstream / add "
    "a constraint). Markdown body only, terse, audience-facing.")


def review_note(result: ProfileResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready data-review note for this profile."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("sample_profile", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
