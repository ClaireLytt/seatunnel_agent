"""Optional LLM normalization note from a timezone audit.

The deterministic auditor names the inconsistencies; this layer drafts
the ingestion-side normalization plan.  Strictly opt-in and bounded to
one call per audit.
"""

from __future__ import annotations

import json

from .auditor import TimezoneAudit

__all__ = ["normalization_note"]

_SYSTEM_ZH = (
    "你是数据接入评审。给定一份时间戳体检 JSON（逐列形态/时区标记/哨兵/"
    "小时双峰与分级发现），起草接入侧归一方案：各列统一到什么时区与单位、"
    "转换表达式长什么样、历史数据要不要回刷、双峰嫌疑怎么与生产方核实。"
    "只输出方案 markdown 列表，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are a data-ingestion reviewer. Given a timestamp audit JSON "
    "(per-column kinds, offsets, sentinels, hour bimodality and graded "
    "findings), draft the ingestion-side normalization plan: the target "
    "zone and unit per column, the conversion expressions, whether "
    "history needs a backfill, and how to verify the bimodal suspicion "
    "with the producers. Markdown bullets only, terse.")


def normalization_note(audit: TimezoneAudit, lang: str = "zh") -> str:
    """One LLM call → a normalization plan for this audit."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(audit.to_dict(), ensure_ascii=False)
    return one_shot("timezone_audit", _SYSTEM_ZH, _SYSTEM_EN, payload,
                    lang)
