"""Optional LLM drift note from a distribution comparison.

The deterministic comparator says which columns drifted and how much;
this layer turns the findings into a paste-ready note for the data-owner
channel.  Strictly opt-in and bounded to one call per comparison.
"""

from __future__ import annotations

import json

from .comparator import DriftResult

__all__ = ["drift_note"]

_SYSTEM_ZH = (
    "你是数据平台的数据质量值班。根据给定的分布漂移 JSON（基线/当前行数、"
    "按严重度排序的漂移发现：schema 变化、均值漂移、空值率/唯一率突变、"
    "类别占比漂移、主类型变化），起草一条发给数据负责人的漂移通报：哪些"
    "列漂了、漂了多少、最可能的业务/上游解释方向、建议的下一步（确认"
    "上游变更/修数/更新基线）。只输出通报正文 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the data-quality on-call. From the given distribution-drift "
    "JSON (baseline/current rows; findings ranked by severity: schema "
    "changes, mean shifts, null/unique-rate jumps, category share drift, "
    "kind changes), draft a note for the data owners: which columns "
    "drifted and by how much, the likely upstream explanation to check, "
    "and the next step (confirm upstream change / fix data / refresh the "
    "baseline). Markdown body only, terse.")


def drift_note(result: DriftResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready drift note for this comparison."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("dist_anomaly", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
