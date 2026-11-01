"""Optional LLM alignment note from a schema alignment.

The deterministic aligner judges the mappings; this layer turns the
findings into a paste-ready note for the sync-job review.  Strictly
opt-in and bounded to one call per alignment.
"""

from __future__ import annotations

import json

from .aligner import AlignResult

__all__ = ["alignment_note"]

_SYSTEM_ZH = (
    "你是同步作业评审人。根据给定的 schema 对齐 JSON（源表/目标表/按"
    "严重度排序的发现：缺列、NOT NULL 陷阱、类型收窄、危险转换、时间"
    "截断），起草一条发给作业负责人的评审意见：哪几列必须先改目标端、"
    "哪几列在 transform 里处理、能不能先上线。只输出意见正文 markdown，"
    "简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the sync-job reviewer. From the given schema-alignment JSON "
    "(source/sink tables, findings ranked by severity — missing columns, "
    "NOT NULL traps, narrowings, risky conversions, temporal "
    "truncation), draft a review for the job owner: which columns need "
    "the sink changed first, which to handle in the transform, and "
    "whether it can ship. Markdown body only, terse.")


def alignment_note(result: AlignResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready alignment review."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("schema_align", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
