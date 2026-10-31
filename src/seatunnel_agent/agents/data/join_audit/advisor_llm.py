"""Optional LLM join review from a join-audit report.

The deterministic auditor measures the join; this layer drafts the
review a senior engineer would leave on the JOIN before it ships.
Strictly opt-in and bounded to one call per audit.  Only metrics and
orphan-key samples are sent — never the rows.
"""

from __future__ import annotations

import json

from .auditor import JoinAuditReport

__all__ = ["join_note"]

_SYSTEM_ZH = (
    "你是数仓评审。给定一份关联质量审计 JSON（两侧行数与匹配率、关联后"
    "行数与爆炸系数、多对多键样例、孤儿键样例、空键占比），起草 JOIN "
    "上线前的评审意见：行数会怎么变、哪侧会丢数、该用什么 join 类型或先"
    "去重、空键怎么处理。只输出意见 markdown，按风险排序，简洁，不要"
    "寒暄。")
_SYSTEM_EN = (
    "You are a warehouse reviewer. Given a join-audit JSON (row counts "
    "and match rates per side, joined rows and explosion factor, "
    "many-to-many key samples, orphan keys, null-key share), draft the "
    "pre-ship review of this JOIN: how row counts will change, which "
    "side loses data, what join type or pre-dedup to use, how to treat "
    "null keys. Markdown only, ordered by risk, terse.")


def join_note(report: JoinAuditReport, lang: str = "zh") -> str:
    """One LLM call → a pre-ship review; rows never leave the process."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(report.to_dict(), ensure_ascii=False)
    return one_shot("join_audit", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
