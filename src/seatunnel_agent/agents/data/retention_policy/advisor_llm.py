"""Optional LLM retention review from a retention report.

The deterministic advisor computes the TTLs; this layer drafts the
cleanup proposal the team signs off on.  Strictly opt-in and bounded to
one call per report.
"""

from __future__ import annotations

import json

from .advisor import RetentionReport

__all__ = ["retention_note"]

_SYSTEM_ZH = (
    "你是存储治理负责人。给定一份生命周期建议 JSON（逐表建议 TTL、冷数据"
    "量、可归档/可清理分区、可释放空间、分级发现），起草给表 owner 签字"
    "的清理提案：各表建议的保留策略、预计释放多少、先归档再清理的顺序、"
    "月度任务等例外该怎么豁免。只输出提案 markdown，按释放收益排序，"
    "简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the storage governance lead. Given a retention-advice JSON "
    "(per-table suggested TTLs, cold sizes, archive/purge candidates, "
    "reclaimable space, graded findings), draft the cleanup proposal "
    "the table owners sign: each table's keep policy, the space freed, "
    "the archive-then-purge order, and how monthly-job exceptions get "
    "waived. Markdown only, ordered by savings, terse.")


def retention_note(report: RetentionReport, lang: str = "zh") -> str:
    """One LLM call → a cleanup proposal for this report."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(report.to_dict(), ensure_ascii=False)
    return one_shot("retention_policy", _SYSTEM_ZH, _SYSTEM_EN, payload,
                    lang)
