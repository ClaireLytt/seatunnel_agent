"""Optional LLM incident note from a CDC diagnosis.

The deterministic diagnoser says which rules fired; this layer turns the
findings into a paste-ready note for the ops channel.  Strictly opt-in
and bounded to one call per diagnosis.
"""

from __future__ import annotations

import json

from .diagnoser import CdcDiagnosis

__all__ = ["incident_note"]

_SYSTEM_ZH = (
    "你是数据同步值班工程师。根据给定的 CDC 诊断 JSON（按严重度排序的"
    "发现：binlog 落后/字节落后/事件停滞/保留期风险/错误分类/断点错乱，"
    "每条带证据与处方），起草一条发到值班群的事故通报：同步现在什么"
    "状态、有没有丢数风险与时间窗口、第一动作是什么。只输出通报正文 "
    "markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the data-sync on-call. From the given CDC diagnosis JSON "
    "(findings ranked by severity — binlog files behind, byte lag, event "
    "stall, retention risk, classified errors, broken resume point, each "
    "with evidence and a prescription), draft an ops-channel note: the "
    "sync's state, the data-loss risk and its deadline, and the first "
    "action. Markdown body only, terse.")


def incident_note(diag: CdcDiagnosis, lang: str = "zh") -> str:
    """One LLM call → a paste-ready incident note for this diagnosis."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(diag.to_dict(), ensure_ascii=False)
    return one_shot("cdc_diag", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
