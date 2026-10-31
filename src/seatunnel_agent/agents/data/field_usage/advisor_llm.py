"""Optional LLM usage review from a field-usage report.

The deterministic analyzer counts the references; this layer drafts the
trim/offboard advice.  Strictly opt-in and bounded to one call per
report.
"""

from __future__ import annotations

import json

from .analyzer import FieldUsageReport

__all__ = ["usage_note"]

_SYSTEM_ZH = (
    "你是数据资产治理评审。给定一份字段使用率盘点 JSON（逐表被读次数、"
    "SELECT * 次数、从未被引用的列、最热列、分级发现），给出处置建议："
    "哪些表该走下线流程、哪些列可裁剪、SELECT * 的任务该怎么改写、统计"
    "窗口是否需要拉宽。只输出建议 markdown 列表，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are a data-asset governance reviewer. Given a field-usage "
    "inventory JSON (per-table reads, SELECT * counts, never-referenced "
    "columns, hottest columns, graded findings), give the disposition "
    "advice: which tables should enter offboarding, which columns can "
    "be trimmed, how SELECT * jobs should be rewritten, whether the "
    "sampling window needs widening. Markdown bullets only, terse.")


def usage_note(report: FieldUsageReport, lang: str = "zh") -> str:
    """One LLM call → disposition advice for this inventory."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(report.to_dict(), ensure_ascii=False)
    return one_shot("field_usage", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
