"""Optional LLM dedup note from a duplicate-check result.

The deterministic detector says which groups duplicate and which columns
differ; this layer turns that into a paste-ready note for the data-owner
channel.  Strictly opt-in and bounded to one call per check.
"""

from __future__ import annotations

import json

from .detector import DupResult

__all__ = ["dedup_note"]

_SYSTEM_ZH = (
    "你是数据平台的数据质量值班。根据给定的重复检测 JSON（总行数、各层"
    "多余重复行数、重复组清单：层/键值/行数/首末行/差异列），起草一条发给"
    "数据负责人的处置通报：重复有多严重、差异列指向的最可能来源（重跑/"
    "上游多路写入/缺少去重窗口）、建议的清理与防复发动作。只输出通报"
    "正文 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the data-quality on-call. From the given duplicate-check "
    "JSON (total rows, extra duplicate rows per layer, duplicate groups "
    "with layer/key/count/first-last rows/differing columns), draft a "
    "note for the data owners: how bad the duplication is, the likely "
    "source the differing columns point at (retried load / upstream "
    "fan-out / missing dedup window), and the cleanup plus prevention "
    "steps. Markdown body only, terse.")


def dedup_note(result: DupResult, lang: str = "zh") -> str:
    """One LLM call → a paste-ready dedup note for this check."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    return one_shot("dup_check", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
