"""Optional LLM ops note from a Flink diagnosis.

The deterministic diagnoser says which rules fired; this layer turns the
findings into a paste-ready note for the ops channel.  Strictly opt-in
and bounded to one call per diagnosis.
"""

from __future__ import annotations

import json

from .diagnoser import FlinkDiagnosis

__all__ = ["ops_note"]

_SYSTEM_ZH = (
    "你是实时平台值班工程师。根据给定的 Flink 作业诊断 JSON（按严重度"
    "排序的发现：checkpoint 失败/暴涨/对齐主导、背压算子、watermark "
    "滞后、频繁重启，每条带证据与处方），起草一条发到值班群的运维通报："
    "作业现在什么状态、根因链是什么（谁压住谁）、第一动作是什么。只输出"
    "通报正文 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the realtime-platform on-call. From the given Flink "
    "diagnosis JSON (findings ranked by severity — checkpoint failures/"
    "blow-ups/alignment, backpressured operators, watermark lag, restart "
    "churn, each with evidence and a prescription), draft an ops-channel "
    "note: the job's state, the causal chain (what pressures what), and "
    "the first action. Markdown body only, terse.")


def ops_note(diag: FlinkDiagnosis, lang: str = "zh") -> str:
    """One LLM call → a paste-ready ops note for this diagnosis."""
    from seatunnel_agent.common.llm import one_shot

    payload = json.dumps(diag.to_dict(), ensure_ascii=False)
    return one_shot("flink_diag", _SYSTEM_ZH, _SYSTEM_EN, payload, lang)
