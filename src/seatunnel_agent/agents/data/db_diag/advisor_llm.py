"""Optional LLM incident note from a database diagnosis.

The deterministic diagnoser says which rules fired; this layer turns the
findings into a paste-ready note for the ops channel.  Strictly opt-in
and bounded to one call per diagnosis.
"""

from __future__ import annotations

import json

from .diagnoser import DbDiagnosis

__all__ = ["incident_note"]

_SYSTEM_ZH = (
    "你是数据库值班 DBA。根据给定的运行诊断 JSON（按严重度排序的发现："
    "连接池吃紧、线程风暴、长锁等待、死锁、慢查询热点、CPU 饱和，每条带"
    "证据与处方），起草一条发到值班群的事故通报：现在数据库怎么了、首要"
    "动作是什么、谁的事务/查询需要处理。只输出通报正文 markdown，简洁，"
    "不要寒暄。")
_SYSTEM_EN = (
    "You are the on-call DBA. From the given runtime-diagnosis JSON "
    "(findings ranked by severity — pool pressure, thread storms, lock "
    "waits, deadlocks, slow-query hotspots, CPU saturation, each with "
    "evidence and a prescription), draft an ops-channel incident note: "
    "what the database is doing right now, the first action, and whose "
    "transaction or query needs attention. Markdown body only, terse.")


def incident_note(diag: DbDiagnosis, lang: str = "zh") -> str:
    """One LLM call → a paste-ready incident note for this diagnosis."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(diag.to_dict(), ensure_ascii=False)
    return one_shot("db_diag", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
