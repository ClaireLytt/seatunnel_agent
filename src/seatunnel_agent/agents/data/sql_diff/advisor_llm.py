"""Optional LLM change review from a SQL semantic diff.

The deterministic differ names what changed; this layer drafts the
review a careful colleague would leave on the merge request.  Strictly
opt-in and bounded to one call per diff.
"""

from __future__ import annotations

import json

from .differ import SqlDiffReport

__all__ = ["change_note"]

_SYSTEM_ZH = (
    "你是数仓代码评审。给定两版取数 SQL 的语义差异 JSON（按写入目标分组"
    "的破坏/风险/提示级差异：删列、口径变更、过滤与聚合变化、源表进出、"
    "INSERT 模式翻转），起草一条 MR 评审意见：哪些差异会改变下游看到的"
    "数、哪些要先通知消费方、哪些只是正常演进。只输出评审 markdown，"
    "按严重级排序，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are a warehouse code reviewer. Given the semantic diff JSON of "
    "two pipeline SQL versions (breaking/risk/info findings per write "
    "target: dropped columns, expression changes, filter and "
    "aggregation changes, source tables in/out, INSERT mode flips), "
    "draft the merge-request review: which differences change what "
    "consumers see, which need a heads-up first, which are routine. "
    "Markdown only, ordered by severity, terse.")


def change_note(report: SqlDiffReport, lang: str = "zh") -> str:
    """One LLM call → a merge-request review for this diff."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(report.to_dict(), ensure_ascii=False)
    return one_shot("sql_diff", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
